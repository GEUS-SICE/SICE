#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

# Document usage options
print_usage() {
  echo "./dhusget_wrapper.sh "\
       "-d [YYYY-MM-DD | YYYY-DOY] "\
       "[-f <footprint>] "\
       "[-l <local Sentinel-3 folder (e.g. CRIODIAS)>] "\
       "-o <output_folder> "\
       "-p <password> "\
       "-u <username> "\
       "[dhusget.sh options]"
  echo ""
  echo "  -d|--date YYYY-MM-DD or YYY-DOY"
  echo "  [-f|--footprint Greenland|Iceland|<footprint code> [DEFAULT: Greenland]]"
  echo "  [-l|--local /path/to/Sentinel-3 (e.g. /o3data/Sentinel-3)]"
  echo "  [           {SLSTR,OLCI}/YYYY/MM/DD subfolders required]"
  echo "  -o|--output-folder /path/to/folder"
  echo "  -p|--password SciHub Password"
  echo "  -u|--user SciHub Username"
  echo "  All other options passed to ./dhusget.sh."
  echo "      see ./dhusget.sh --help for more information"
}

red='\033[0;31m'; orange='\033[0;33m'; green='\033[0;32m'; nc='\033[0m' # No Color
log_info() { echo -e "${green}[$(date --iso-8601=seconds)] [INFO] ${@}${nc}"; }
log_warn() { echo -e "${orange}[$(date --iso-8601=seconds)] [WARN] ${@}${nc}"; }
log_err() { echo -e "${red}[$(date --iso-8601=seconds)] [ERR] ${@}${nc}" >&2; }

trap ctrl_c INT # trap ctrl-c and call ctrl_c()
ctrl_c() {
    log_err "CTRL-C. Cleaning up..."
    rm -f products-list.csv OSquery-result.xml
    rm -fR logs
}

debug() { if [[ ${debug:-} == 1 ]]; then log_warn "debug:"; echo $@; fi; }


# Parse input arguments
positional=("") # "" is for bash 4.3 bug fixs
while [[ $# -gt 0 ]]; do
  key="$1"
  case "${key}" in
    -h|--help)
      print_usage; exit 1;;
    -d|--date)
      date="$2"
      shift # past argument
      shift # past value
      ;;
    -f|--footprint)
      footprint="$2"; shift; shift;;
    -l|--local)
      local_files="$2"; shift; shift;;
    -o|--output-folder)
      outfolder="$2"; shift; shift;;
    -p|--password)
      password="$2"; shift; shift;;
    -u|--user)
      username="$2"; shift; shift;;
    --debug)
      debug=1; shift;;
    -v|--verbose)
      set -o xtrace; shift;;
    *)    # unknown option
      positional+=("$1") # save it in an array for later. Pass on to dhusget.sh
      shift;;
  esac
done
set -- "${positional[@]}" # restore positional parameters

# check inputs
missing_arg() { log_err "$@ not set"; print_usage; exit 1; }
if [[ -z ${date:-} ]]; then missing_arg "--date"; fi
if [[ -z ${outfolder:-} ]]; then missing_arg "--output"; fi
if [[ -z ${footprint:-} ]]; then 
  footprint=Greenland; log_warn "Footprint not set. Setting to Greenland"
else
  log_warn "Footprint set to ${footprint}"
fi

# process arguments
if [[ ${date} =~ 20[1,2][0-9]-[0-9][0-9]?[0-9]?$ ]]; then # YYYY-DOY format
  year=${date:0:4}
  doy=${date:5:9}
  date=$(date -d "${year}-01-01 +$(( 10#${doy}-1 )) days" "+%Y-%m-%d")
fi
datestr0="${date}T00:00:00.0000Z"
datestr1="${date}T23:59:59.9999Z"
debug "Date search from: ${datestr0} to ${datestr1}"

# NOTE: Fetching SLSTR and OLCI for the same YYYY-MM-DD day. However,
# SLSTR scenes are delayed by 4 seconds. Because we aim for descending
# node (day time) it doesn't matter, but a more general version of
# this code would occasionally fetch an OLCI scene <4 before midnight,
# and then no SLSTR scene. Or a SLSTR scene <4 seconds after midnight,
# and no OLCI scene.

if [[ ${footprint} == "Greenland" ]]; then
  footprint="footprint:\"Intersects(POLYGON((-53.6565 82.4951,-59.9608 82.1309,-67.7892 80.5602,-67.9606 80.0218,-67.6072 79.3014,-72.7375 78.5894,-73.5413 78.1636,-72.9428 77.3837,-69.0700 76.0128,-66.6509 75.7624,-60.3956 75.8231,-58.4311 74.8854,-55.1967 69.6980,-53.8565 68.8368,-54.2986 67.0754,-53.5562 65.6109,-52.3863 64.7989,-52.3228 64.0074,-50.2076 62.1010,-48.6300 60.7381,-45.0522 59.7674,-43.2890 59.6436,-42.4957 60.3093,-41.8486 61.5655,-41.6969 62.6486,-40.1106 63.5452,-39.9111 64.7944,-38.0777 65.4068,-36.9899 65.1987,-31.2165 67.7166,-25.8502 68.6303,-21.6517 70.0839,-20.9932 70.7880,-21.2829 72.9254,-16.9050 74.9601,-17.1213 79.6158,-10.2883 81.4244,-14.0398 81.9745,-17.8112 82.0131,-28.5252 83.7013,-40.1075 83.6651,-53.6565 82.4951)))\""
elif [[ ${FOOTPRINT} == "debug" ]]; then
  footprint="footprint:\"Intersects(POLYGON((-45 63,-45 64,-44 64,-44 63,-45 63)))\""
elif [[ ${footprint} == "Iceland" ]]; then
  log_err "Not yet implemented"; exit 1
elif [[ ${footprint} == "Svalbard" ]]; then
  log_err "Not yet implemented"; exit 1
fi
debug "Footprint: ${footprint}"


log_info "***********************************************************"
log_info "***                                                     ***"
log_info "***               DHUSGET.SH begin                      ***"
log_info "***                                                     ***"
log_info "***********************************************************"
# Get the list of file names and product UUIDs
# Could download (with "-o" and maybe "-D -O outfolder"), but what if we have them already?
# For now, just get file list. We'll check if we have them and download missing files below.
./dhusget.sh $@ -u ${username} -p ${password} \
	     -m Sentinel-3 -l 100 \
	     -i "(OLCI OR SLSTR)" \
	     -S ${datestr0} -E ${datestr1} \
	     -F 'filename:(*EFR* OR *RBT*) AND orbitdirection:descending AND ( '"${footprint}"' )'
log_info "***********************************************************"
log_info "***                                                     ***"
log_info "***                DHUSGET.SH end                       ***"
log_info "***                                                     ***"
log_info "***********************************************************"


# If no local file path provided, then we download.
mkdir -p ${outfolder}
if [[ -z ${local_files:-} ]]; then
  # find files in products-list.csv that are not already in ${OUTFOLDER}
  for line in $(cat products-list.csv); do
    uuid=$(echo ${line} | cut -d"'" -f2)
    filename=$(echo ${line} | cut -d"," -f1)
    if [[ -d ${outfolder}/${filename}.SEN3 ]]; then
      log_warn "${outfolder}/${filename}.SEN3 already exists. No Download"
      continue
    fi
    log_info "Downloading ${filename}..."
    # From https://scihub.copernicus.eu/userguide/BatchScripting
    wget --show-progress -nc --continue \
	 --user=${username} --password=${password} \
	 "https://scihub.copernicus.eu/dhus/odata/v1/Products('${uuid}')/\$value" \
	 -O ${outfolder}/${filename}.zip
    [[ -z ${outfolder} ]] || (cd "${outfolder}"; unzip ${filename}.zip; rm ${filename}.zip)
  done
else
  # Source for SEN3 is a locally mounted path.
  
  # rather than downloading, use the products-list.csv from the
  # dhusget.sh command and search for the files at the given path.
  log_info "linking local files into ${outfolder}"
  mkdir -p ${outfolder}
  year=${date:0:4}; month=${date:5:2}; day=${date:8:2}
  for product in $(cut -d, -f1 products-list.csv); do
    local_subfolder="UNKNOWN_INSTRUMENT"
    [[ ${product:4:8} == "OL_1_EFR" ]] && local_subfolder="OLCI/OL_1_EFR"
    [[ ${product:4:8} == "SL_1_RBT" ]] && local_subfolder="SLSTR/SL_1_RBT"
    
    local_fullpath=${local_files}/${local_subfolder}/${year}/${month}/${day}/${product}.SEN3
    [[ -z ${local_fullpath} ]] || log_err "Not found: ${local_fullpath}"
    (cd ${outfolder}; ln -fs ${local_fullpath})
  done
fi

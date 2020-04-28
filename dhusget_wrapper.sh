#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -x

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
  echo "  [-f|--footprint Greenland|Iceland|Svalbard|NovayaZemlya|SevernayaZemlya|FransJosefLand|NorthernArcticCanada (Devon Island included)|SouthernArcticCanada|JanMayen|Norway|Beaufort (sea ice)|AlaskaYukon  [DEFAULT: Greenland] [ELSE: footprint coordinates (.geojson, .csv: decimal lon/lat]]"
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
  footprint_poly="footprint:\"Intersects(POLYGON((-53.6565 82.4951,-59.9608 82.1309,-67.7892 80.5602,-67.9606 80.0218,-67.6072 79.3014,-72.7375 78.5894,-73.5413 78.1636,-72.9428 77.3837,-69.0700 76.0128,-66.6509 75.7624,-60.3956 75.8231,-58.4311 74.8854,-55.1967 69.6980,-53.8565 68.8368,-54.2986 67.0754,-53.5562 65.6109,-52.3863 64.7989,-52.3228 64.0074,-50.2076 62.1010,-48.6300 60.7381,-45.0522 59.7674,-43.2890 59.6436,-42.4957 60.3093,-41.8486 61.5655,-41.6969 62.6486,-40.1106 63.5452,-39.9111 64.7944,-38.0777 65.4068,-36.9899 65.1987,-31.2165 67.7166,-25.8502 68.6303,-21.6517 70.0839,-20.9932 70.7880,-21.2829 72.9254,-16.9050 74.9601,-17.1213 79.6158,-10.2883 81.4244,-14.0398 81.9745,-17.8112 82.0131,-28.5252 83.7013,-40.1075 83.6651,-53.6565 82.4951)))\""
elif [[ ${footprint} == "debug" ]]; then
  footprint_poly="footprint:\"Intersects(POLYGON((-45 63,-45 64,-44 64,-44 63,-45 63)))\""
elif [[ ${footprint} == "Svalbard" ]]; then
  footprint_poly="footprint:\"Intersects(POLYGON((21.533203125 80.77471572295197,33.2666015625 80.43033003417169,34.32128906249999 80.18620666179095,30.761718749999996 78.9039293885709,23.5546875 77.12782546469762,16.5673828125 76.28954161916205,11.074218749999998 78.02557363284087,9.7119140625 79.17133464081945,9.667968749999998 79.92823592380245,14.809570312499998 80.2608276489869,20.1708984375 80.85189079086516,21.005859375 80.80285378098482,21.533203125 80.77471572295197)))\""
elif [[ ${footprint} == "NovayaZemlya" ]]; then
  footprint_poly="footprint:\"Intersects(POLYGON((70.400390625 76.7403972505508,69.521484375 75.97355295343336,61.87499999999999 74.79890566232942,58.00781249999999 72.91963546581484,56.865234375 71.66366293141732,58.35937499999999 70.8446726342528,57.919921875 70.25945200030638,55.01953125 70.19999407534661,51.50390625 70.69995129442536,49.833984375 71.66366293141732,52.470703125 74.59010800882325,56.42578125 76.37261948220728,63.896484375 76.78065491639973,67.8515625 77.42782352730109,69.697265625 76.9999351181161,70.400390625 76.7403972505508)))\""
elif [[ ${footprint} == "SevernayaZemlya" ]]; then
      footprint_poly="footprint:\"Intersects(POLYGON((89.380324 79.519637,90.435012 80.170257,91.489699 80.458579,91.841262 80.759714,89.248488 80.982809,88.940871 81.234111,91.577590 81.347232,93.159621 81.078726,95.225051 81.373637,96.411575 81.300829,98.345168 80.850999,98.828567 80.653263,97.993606 80.363415,99.751418 80.185251,102.476028 79.599272,104.014114 79.309753,106.035598 78.766699,105.903762 78.374874,103.047317 77.997024,99.443801 77.729090,98.301223 77.978732,97.729934 78.637561,93.115676 78.919754,90.039504 79.162021,89.380324 79.519637)))\""
elif [[ ${footprint} == "Iceland" ]]; then
  footprint_poly="footprint:\"Intersects(POLYGON((-14.4580078125 66.21373941545203,-14.21630859375 65.89268028960205,-13.24951171875 65.5766364488888,-13.29345703125 65.25670649344259,-13.4912109375 64.74601725111455,-14.3701171875 64.28275952823394,-15.292968749999998 64.00486735371551,-15.6884765625 63.98559971175696,-16.611328125 63.597447665602004,-17.42431640625 63.57789956676574,-18.017578125 63.27318217465046,-19.599609375 63.28306240110864,-20.63232421875 63.30281270313518,-21.33544921875 63.61698233975829,-22.56591796875 63.65601144183318,-23.291015625 63.80189351770543,-22.785644531249996 64.29229248039543,-22.8076171875 64.5389958071547,-24.3017578125 64.58618480339979,-24.235839843749996 65.12763795652116,-24.76318359375 65.46738586205099,-24.43359375 65.99121175911041,-23.53271484375 66.41674787052298,-23.1591796875 66.60067571342496,-22.12646484375 66.58321725728175,-21.15966796875 66.21373941545203,-20.830078125 65.9195901580262,-20.456542968749996 66.22260000154931,-15.99609375 66.68778386116203,-14.589843749999998 66.65297740055279,-14.4580078125 66.21373941545203)))\""
elif [[ ${footprint} == "FransJosefLand" ]]; then
  footprint_poly="footprint:\"Intersects(POLYGON((60.90820312499999 81.99694184598178,65.0390625 81.8487556310786,66.4453125 81.02491605035449,62.9296875 80.23850054635392,60.90820312499999 79.52864723963516,53.876953125 79.6240562918881,48.427734375 79.67143789507548,44.736328125 80.10346957375634,43.154296875 80.61842419685506,46.7578125 81.22826656005543,52.55859375 81.53122538741061,57.568359375 82.04574006217713,59.94140624999999 81.99694184598178,60.90820312499999 81.99694184598178)))\""
elif [[ ${footprint} == "NorthernArcticCanada" ]]; then
  footprint_poly="footprint:\"Intersects(POLYGON((-79.253265 74.270476,-88.921234 74.174886,-94.883208 74.362167,-109.479823 74.252221,-114.252200 74.080079,-125.873886 75.942222,-114.127904 78.881581,-99.025927 80.923105,-91.025715 82.750890,-78.483296 83.641180,-63.560119 83.249056,-58.295980 82.417344,-61.646954 81.983368,-65.302563 81.087367,-68.856626 80.239541,-73.324591 78.642292,-76.269387 76.529933,-77.234061 75.525102,-79.253265 74.270476)))\""
elif [[ ${footprint} == "SouthernArcticCanada" ]]; then
      footprint_poly="footprint:\"Intersects(POLYGON((-86.404868 74.164835,-78.349014 74.104221,-75.836179 73.485523,-67.410791 70.962600,-63.937166 68.616174,-60.020100 66.736387,-62.459028 64.126813,-64.380608 61.104304,-70.387440 61.692568,-74.672767 63.519345,-77.432193 64.142859,-79.635784 64.404771,-78.517119 65.765854,-81.065189 69.559702,-86.039977 69.916812,-88.543574 69.767181,-91.315083 71.529287,-90.760781 72.981353,-87.471924 74.131538,-86.404868 74.164835)))\""
elif [[ ${footprint} == "JanMayen" ]]; then
      footprint_poly="footprint:\"Intersects(POLYGON((-9.087081 70.895861,-9.012923 70.913831,-8.947005 70.929093,-8.878341 70.947930,-8.806930 70.962270,-8.738265 70.981970,-8.639388 70.992707,-8.554244 70.998074,-8.506710 71.015434,-8.473556 71.049937,-8.418029 71.089144,-8.323308 71.128272,-8.171427 71.160996,-8.062008 71.174702,-7.926458 71.175756,-7.890529 71.147807,-7.947689 71.070080,-7.942789 71.018622,-8.016280 70.990980,-8.338006 70.957440,-8.484988 70.963300,-8.645034 70.935048,-8.711992 70.903015,-8.783850 70.865579,-8.968393 70.814122,-9.076180 70.815732,-9.120274 70.853262,-9.087081 70.895861)))\""
elif [[ ${footprint} == "Norway" ]]; then
          footprint_poly="footprint:\"Intersects(POLYGON((6.360509 62.951828,5.636290 62.626962,4.738299 62.266442,4.280832 61.540340,4.213059 61.207532,4.484150 60.531225,4.839958 59.729643,4.929492 59.464417,9.193077 59.562844,9.620502 62.539475,6.360509 62.951828)))\""
elif [[ ${footprint} == "Beaufort" ]]; then
        footprint_poly="footprint:\"Intersects(POLYGON((-145.8544921875 70.05059634999759,-134.75830078125 74.69485438254536,-123.22265625000001 74.38442852287905,-128.03466796875 68.9189095799366,-135.41748046875 68.68053347928972,-145.7666015625 70.02809362050226,-145.8544921875 70.05059634999759)))\""
elif [[ ${footprint} == "AlaskaYukon" ]]; then
        footprint_poly="footprint:\"Intersects(POLYGON((-153.443453 59.371565,-155.758468 59.983386,-155.849887 62.149612,-149.612619 64.317909,-144.046921 64.090493,-132.520688 60.004403,-127.994321 55.260251,-130.140189 54.742974,-134.865137 57.917908,-137.747917 58.366708,-140.962528 59.595609,-145.794814 60.095665, -150.979670 58.572775, -153.443453 59.371565)))\""
else
  boundary=$(boundary_from_file.py ${footprint})
  footprint_poly="footprint:\"Intersects(POLYGON((${boundary})))\""
fi
debug "Footprint ${footprint} is: ${footprint_poly}"

log_warn "Setting mask.tif to masks/${footprint}.tif"
rm -f mask.tif
ln -s ./masks/${footprint}.tif mask.tif 

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
	     -F 'filename:(S3A*EFR* OR S3A*RBT*) AND orbitdirection:descending AND ( '"${footprint_poly}"' )'
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
    (cd ${outfolder}; ln -fs ${local_fullpath})
  done
fi

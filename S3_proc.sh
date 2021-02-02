#!/usr/bin/env bash 

set -o errexit
set -o nounset
set -o pipefail
set -x

function print_usage() {
  echo ""
  echo "./S3_proc.sh -i inpath -o outpath -X file.xml [-h -v -t]"
  echo "  -i: Path to folder containing S3?_*_EFR_*_002.SEN3 (unzipped S3 EFR) files"
  echo "  -o: Path where to store ouput"
  echo "  -X: Specify XML file"
  echo "  -v: Print verbose messages during processing"
  echo "  -t: Print timing messages during processing"
  echo "  -h: print this help"
  echo ""
}

red='\033[0;31m'; orange='\033[0;33m'; green='\033[0;32m'; nc='\033[0m' # No Color
log_info() { echo -e "${green}[$(date --iso-8601=seconds)] [INFO] ${@}${nc}"; }
log_warn() { echo -e "${orange}[$(date --iso-8601=seconds)] [WARN] ${@}${nc}"; }
log_err() { echo -e "${red}[$(date --iso-8601=seconds)] [ERR] ${@}${nc}" 1>&2; }

trap ctrl_c INT # trap ctrl-c and call ctrl_c()
ctrl_c() {
  log_err "CTRL-C caught"
  log_err "Removing gpt progress..."
  [[ -d ${dest} ]] && (cd ${dest}; rm *_x.tif)
}

debug() { if [[ ${debug:-} == 1 ]]; then log_warn "debug:"; echo $@; fi; }

readonly t_0=`date +%s`
declare t_last=`date +%s`
timing() { 
  if [[ ${timing:-} ]]; then
    log_info "Timing...";
    local t_now=$(date +%s)
    echo "    Time since start:" $(( ${t_now} - ${t_0} ))"s"
    echo "    Time since last:" $(( ${t_now} - ${t_last} ))"s"
    t_last=$(date +%s)
  fi
}

while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -h|--help)
      print_usage; exit 1;;
    -i)
      inpath="$2"
      shift # past argument
      shift # past value
      ;;
    -o)
      outpath="$2"; shift; shift;;
    -X)
      xml="$2"; shift; shift;;
    -v|--verbose)
      verbose=1; set -o xtrace; shift;;
    -t)
      timing=1; shift;;
    *)    # unknown option
      positional+=("$1") # save it in an array for later. Pass on to dhusget.sh
      shift;;
  esac
done

if [[ -z ${inpath:-} ]]; then log_err "-i not set"; print_usage; exit 1; fi
if [[ -z ${outpath:-} ]]; then log_err "-o not set"; print_usage; exit 1; fi
if [[ -z ${xml:-} ]]; then log_err "-X not set"; print_usage; exit 1; fi

for folder in $(ls ${inpath} | grep S3._OL_1_EFR); do
  olci_folder=$(basename "${folder}")
  olci_dts=$(echo "${olci_folder}" | rev | cut -d_ -f11 | rev)
  dest=${outpath}/${olci_dts}

  # if [[ -d "${dest}" ]]; then continue; fi
  
  # find nearest SLSTR folder. Timestamp is same or next minute.
  olci_date=${olci_dts:0:8}
  olci_time=${olci_dts:9:4}
  olci_time1=$(date -d "${olci_date} ${olci_time} + 1 minute" "+%H%M")  
  olci_time2=$(date -d "${olci_date} ${olci_time} - 1 minute" "+%H%M")
  fileroot="S3._SL_1_RBT____........T" # grep for acquisition not ingest time
  # pick first nearby slstr
  slstr_folder=$(ls ${inpath} | grep -E "${fileroot}${olci_time}|${fileroot}${olci_time1}|${fileroot}${olci_time2}" |head -n1 || true)
  if [[ -z ${slstr_folder} ]]; then log_err "No nearby SLSTR scene found"; continue; fi
  log_info "${olci_folder}"
  log_info "${slstr_folder}"
  
  log_info "Generating ${dest}"
  mkdir -p "${dest}"
  
  log_info "gpt: Start"
  timing
  [[ $(which gpt) ]] || (log_err "gpt not found"; exit 1)
  LD_LIBRARY_PATH=. gpt ${xml} \
		 -POLCIsource="${inpath}/${olci_folder}" \
		 -PSLSTRsource="${inpath}/${slstr_folder}" \
		 -PtargetFolder="${dest}" \
		 -Ds3tbx.reader.olci.pixelGeoCoding=true \
		 -Ds3tbx.reader.slstrl1b.pixelGeoCodings=true \
		 -Dsnap.log.level=ERROR \
		 -e || (log_err "gpt error"; exit 1)
  log_info "gpt: Finished"

  # # Discard out bad folders (defined as size > 10 GB)
  # (cd ${dest}/../; du -sm * | awk '$1 > 10000 {print $2}' | xargs rm -fr)
  if [[ ! -d "${dest}" ]]; then continue; fi # if we removed the directory, break out of the loop

  resize=1000
  log_info "Resampling to ${resize} m resolution..."
  log_info "Aligning SLSTR to OLCI..."
  grass -c ./mask.tif ${dest}/G_align --exec ./G_align.sh ${dest} ./mask.tif ${resize}
  (cd ${dest} && rm *_x.tif)
  (cd ${dest} && rm -fR G_align)
done

log_info "Finished: ${outpath}"
timing


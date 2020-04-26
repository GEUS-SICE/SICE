#!/usr/bin/env bash

# Wrapper for running SICE pipeline

set -o errexit
set -o nounset
set -o pipefail
set -x

red='\033[0;31m'; orange='\033[0;33m'; green='\033[0;32m'; nc='\033[0m' # No Color
log_info() { echo -e "${green}[$(date --iso-8601=seconds)] [INFO] ${@}${nc}"; }
log_warn() { echo -e "${orange}[$(date --iso-8601=seconds)] [WARN] ${@}${nc}"; }
log_err() { echo -e "${red}[$(date --iso-8601=seconds)] [ERR] ${@}${nc}" 1>&2; }

# CREODIAS
SEN3_local=/eodata/Sentinel-3
SEN3_source=/sice-data/SICE/S3
proc_root=/sice-data/SICE/proc
mosaic_root=/sice-data/SICE/mosaic

### dev
# SEN3_source=./SEN3
# proc_root=./out
# mosaic_root=./mosaic

LD_LIBRARY_PATH=. # SNAP requirement

for year in 2018 2019; do
  for doy in $(seq -w 74 274); do

### DEBUG
# for year in 2018; do
#   for doy in 227; do  # 2017-08-15=227

    date=$(date -d "${year}-01-01 +$(( 10#${doy}-1 )) days" "+%Y-%m-%d")
    
    if [[ -d "${mosaic_root}/${date}" ]] && [[ -e "${mosaic_root}/${date}/conc.tif" ]]; then
      log_warn "${mosaic_root}/${date} already exists, date skipped"
      continue
    fi
    
    ### Fetch one day of OLCI & SLSTR scenes over Greenland
    ## Use local files (PTEP, DIAS, etc.)
    ./dhusget_wrapper.sh -d ${date} -l ${SEN3_local} -o ${SEN3_source}/${year}/${date} \
    			 -f Svalbard -u <user> -p <password>
    ## Download files
    # ./dhusget_wrapper.sh -d ${date} -o ${SEN3_source}/${year}/${date} \
    # 			 -f Svalbard -u <user> -p <password>
    
    # SNAP: Reproject, calculate reflectance, extract bands, etc.
    ./S3_proc.sh -i ${SEN3_source}/${year}/${date} -o ${proc_root}/${date} -X S3.xml -t
    
    # Run the Simple Cloud Detection Algorithm (SCDA)
    python ./SCDA.py ${proc_root}/${date}
    
    # Mosaic
    ./dm.sh ${date} ${proc_root}/${date} ${mosaic_root}

    # SICE
    python ./sice.py ${mosaic_root}/${date}
    
  done
done

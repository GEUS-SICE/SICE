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


### dev
SEN3_source=./SEN3
proc_root=./out
mosaic_root=./mosaic

LD_LIBRARY_PATH=. # SNAP requirement

 for year in 2017 2018 2019 2020; do
  for doy in $(seq -w 74 274); do

    date=$(date -d "${year}-01-01 +$(( 10#${doy}-1 )) days" "+%Y-%m-%d")
    
    ### Fetch one day of OLCI & SLSTR scenes over Greenland
    ## Use local files (PTEP, DIAS, etc.)
    ./get-product-list-dhusget.sh -d ${date} -l ${SEN3_local} -f Greenland -u baptistevdx -p geus1234

    
  done
done

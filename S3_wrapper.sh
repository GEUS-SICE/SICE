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

# scihub login information
IFS=$' \t\r\n' read -r username password < scihub_login_info.txt
password=${password%$'\r'}

# source and destination folder
SEN3_local=/eodata/Sentinel-3 # where the '.SEN3' files are
SEN3_source=/eodata/Sentinel-3 
proc_root=~/sice-data/proc # where the scenes' geotiff will be saved
mosaic_root=~/sice-data/mosaic # where the output tiff will be saved

# Geographic area
area=Svalbard
# list: Svalbard, Greenland, NovayaZemlya, SevernayaZemlya, Iceland, FransJosefLand, NorthernArcticCanada, SouthernArcticCanada, JanMayen, Norway, Beaufort, AlaskaYukon

# Slope correction 
slopey=false

# Error handling
error=false

# Fast processing:
fast=true

if [ "$fast" = true ] ; then
  # so far the only speed up done is to not extract all bands
  xml_file=S3_fast.xml
else
  xml_file=S3.xml
fi

LD_LIBRARY_PATH=. # SNAP requirement

# for year in 2017 ; do
#     for doy in $(seq -w 91 276); do

### DEBUG
for year in 2021; do
  for doy in 246; do  # 2017-08-15=227

    date=$(date -d "${year}-01-01 +$(( 10#${doy}-1 )) days" "+%Y-%m-%d")
    
    if [[ -d "${mosaic_root}/${date}" ]] && [[ -e "${mosaic_root}/${date}/conc.tif" ]]; then
      log_warn "${mosaic_root}/${date} already exists, date skipped"
      continue
    fi
    
    ### Fetch one day of OLCI & SLSTR scenes over Greenland
    ## Use local files (PTEP, DIAS, etc.)
     ./dhusget_wrapper.sh -d ${date} -l ${SEN3_local} -o ${SEN3_source}/${year}/${date} -f ${area} -u $username -p $password || error=true
    ## Download files
    # ./dhusget_wrapper.sh -d ${date} -o ${SEN3_source}/${year}/${date}  -f ${area} -u $username -p $password || error=true
    
    # SNAP: Reproject, calculate reflectance, extract bands, etc.
    ./S3_proc.sh -i ${SEN3_source}/${year}/${date} -o ${proc_root}/${date} -X ${xml_file} || error=true -t
    
    # Run the Simple Cloud Detection Algorithm (SCDA)
    python ./SCDA.py ${proc_root}/${date} || error=true
    
    # Mosaic
    ./dm.sh ${date} ${proc_root}/${date} ${mosaic_root} || error=true
    
    if [ "$slopey" = true ] ; then
      # Run the slopey correction
      python ./get_ITOAR.py ${mosaic_root}/${date}/ ./ArcticDEM/  || error=true
      # saving uncorrected files
      cp -f ${mosaic_root}/${date}/SZA.tif ${mosaic_root}/${date}/SZA_org.tif      
      cp -f ${mosaic_root}/${date}/OZA.tif ${mosaic_root}/${date}/OZA_org.tif
      cp -f ${mosaic_root}/${date}/r_TOA_17.tif ${mosaic_root}/${date}/r_TOA_17_org.tif
      cp -f ${mosaic_root}/${date}/r_TOA_21.tif ${mosaic_root}/${date}/r_TOA_21_org.tif

      # overwriting with corrected files
      cp -f ${mosaic_root}/${date}/SZA_eff.tif ${mosaic_root}/${date}/SZA.tif      
      cp -f ${mosaic_root}/${date}/OZA_eff.tif ${mosaic_root}/${date}/OZA.tif
      cp -f ${mosaic_root}/${date}/ir_TOA_17.tif ${mosaic_root}/${date}/r_TOA_17.tif
      cp -f ${mosaic_root}/${date}/ir_TOA_21.tif ${mosaic_root}/${date}/r_TOA_21.tif
    fi

    # SICE
    python ./sice.py ${mosaic_root}/${date} || error=true
    
    if [ "$slopey" = true ] ; then
      # restoring uncorrected files
      cp -f ${mosaic_root}/${date}/SZA_org.tif ${mosaic_root}/${date}/SZA.tif      
      cp -f ${mosaic_root}/${date}/OZA_org.tif ${mosaic_root}/${date}/OZA.tif
      cp -f ${mosaic_root}/${date}/r_TOA_17_org.tif ${mosaic_root}/${date}/r_TOA_17.tif
      cp -f ${mosaic_root}/${date}/r_TOA_21_org.tif ${mosaic_root}/${date}/r_TOA_21.tif
      rm ${mosaic_root}/${date}/SZA.tif ${mosaic_root}/${date}/OZA.tif ${mosaic_root}/${date}/r_TOA_17.tif ${mosaic_root}/${date}/r_TOA_21.tif
    fi
  done
done

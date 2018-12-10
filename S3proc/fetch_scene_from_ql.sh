#!/usr/bin/env bash

RED='\033[0;31m'
ORANGE='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
MSG_OK() { printf "${GREEN}${1}${NC}\n"; }
MSG_WARN() { printf "${ORANGE}WARNING: ${1}${NC}\n"; }
MSG_ERR() { printf "${RED}ERROR: ${1}${NC}\n"; }

if [ "$#" -ne 2 ]; then
  MSG_ERR "Usage: $0 <quicklook_folder> <destination_folder>" >&2
  exit 1
fi
if ! [ -e "$1" ]; then
  MSG_ERR "$1 not found" >&2
  exit 1
fi

IN=$1
OUT=$2
mkdir -p ${OUT}
for file in $(ls ${IN}); do
    id=$(echo $(basename $file .jpg) | cut -d"_" -f2)  # product ID from QL filename
    PRODUCTURL="https://scihub.copernicus.eu/s3/odata/v1/Products('${id}')/"
    # wget "${PRODUCTURL}" --user=s3guest --password=s3guest -nc -c -nd -O ${OUT}/${id}.xml
    curl --silent -u s3guest:s3guest -o ${OUT}/${id}.xml "${PRODUCTURL}"
    PRODUCT_NAME=$(grep -o "<d:Name>.*" ${OUT}/${id}.xml | cut -d">" -f2 | cut -d"<" -f1)
    rm ${2}/${id}.xml
    # wget "${PRODUCTURL}\$value" --user=s3guest --password=s3guest -nc -O ${OUT}/${PRODUCT_NAME}.zip    #--continue
    if [[ -d ${OUT}/${PRODUCT_NAME}.SEN3 ]]; then
	MSG_WARN "Skipping: ${PRODUCT_NAME}"
    else	
	MSG_OK "Fetching: ${PRODUCT_NAME}"
	curl -o ${OUT}/${PRODUCT_NAME}.zip -u s3guest:s3guest "${PRODUCTURL}\$value"
	(cd ${OUT}; unzip ${PRODUCT_NAME}.zip)
	rm ${OUT}/${PRODUCT_NAME}.zip
    fi
done

#!/usr/bin/env bash

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <quicklook_folder> <destination_folder>" >&2
  exit 1
fi
if ! [ -e "$1" ]; then
  echo "$1 not found" >&2
  exit 1
fi

mkdir -p $2
for file in $(ls $1); do
  id=$(basename $file .jpg)
  PRODUCTURL="https://scihub.copernicus.eu/s3/odata/v1/Products('${id}')/"
  echo $PRODUCTURL
  wget "${PRODUCTURL}" --user=s3guest --password=s3guest -nc -c -nd -O ${2}/${id}.xml
  PRODUCT_NAME=$(grep -o "file name.*" ${2}/${id}.xml |cut -d\" -f2)
  DATAURL="https://scihub.copernicus.eu/s3/odata/v1/Products('${id}')/\$value"
  wget "${DATAURL}" --user=s3guest --password=s3guest -nc -c -nd -O ${2}/${PRODUCT_NAME}
done

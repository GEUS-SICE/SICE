#!/usr/bin/env bash

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <quicklook_folder> <destination_folder>" >&2
  exit 1
fi
if ! [ -e "$1" ]; then
  echo "$1 not found" >&2
  exit 1
fi

IN=$1
OUT=$2
mkdir -p ${OUT}
for file in $(ls ${IN}); do
    id=$(echo $(basename $file .jpg) | cut -d"_" -f2)  # product ID from QL filename
    PRODUCTURL="https://scihub.copernicus.eu/s3/odata/v1/Products('${id}')/"
    wget "${PRODUCTURL}" --user=s3guest --password=s3guest -nc -c -nd -O ${OUT}/${id}.xml
    PRODUCT_NAME=$(grep -o "<d:Name>.*" ${OUT}/${id}.xml | cut -d">" -f2 | cut -d"<" -f1)
    rm ${2}/${id}.xml
    wget "${PRODUCTURL}\$value" --user=s3guest --password=s3guest --continue -nd -O ${OUT}/${PRODUCT_NAME}.zip
done

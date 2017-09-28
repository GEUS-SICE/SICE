#!/usr/bin/env bash

mkdir -p quicklook
for ID in $(grep EFR product_IDs.txt | sort -k1,9 -t_ --stable --uniq | cut -d$'\t' -f2-); do
  echo $ID
  URL="https://scihub.copernicus.eu/s3/odata/v1/Products('${ID}')/Products('Quicklook')/\$value"
  wget "${URL}" --user=s3guest --password=s3guest -nc -c -nd -P ./quicklook -O ./quicklook/${ID}.jpg
done

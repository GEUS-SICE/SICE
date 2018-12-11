#!/usr/bin/env bash

# ./dm.sh 20170801 ./tmp ./mosaic

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <yyyymmdd> <infolder> <outfolder>" >&2
  exit 1
fi

DATE=$1
INFOLDER=$2
OUTFOLDER=$3

# TESTING
# DATE=20170827
# INFOLDER=./tmp
# OUTFOLDER=./mosaic

## Work in /tmp/tmpG
BASE=/tmp
LOC=tmpG

rm -fR ${BASE}/${LOC}
grass -e -c mask.tif ${BASE}/${LOC}

grass ${BASE}/${LOC}/PERMANENT --exec ./dm.grass $DATE $INFOLDER $OUTFOLDER

# debug:
# grass72 /tmp/tmpG/PERMANENT
# DATE=20170827
# INFOLDER=./tmp
# OUTFOLDER=./MOSAIC

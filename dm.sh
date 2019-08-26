#!/bin/bash

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <yyyymmdd> <infolder> <outfolder>" >&2
  exit 1
fi

DATE=$1      # YYYYMMDD
INFOLDER=$2  # ./tmp ?
OUTFOLDER=$3 # ./mosaic ?

## Work in /tmp/tmpG
BASE=/tmp
LOC=tmpG

rm -fR ${BASE}/${LOC}
grass -e -c mask.tif ${BASE}/${LOC}

grass ${BASE}/${LOC}/PERMANENT --exec ./dm.grass.sh $DATE $INFOLDER $OUTFOLDER


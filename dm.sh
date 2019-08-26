#!/bin/bash

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <yyyymmdd> <infolder> <outfolder>" >&2
  exit 1
fi

DATE=$1      # YYYYMMDD
INFOLDER=$2  # ./tmp ?
OUTFOLDER=$3 # ./mosaic ?

grass -e -c mask.tif ./G_mosaic_$$ # work in ./G_mosaic_<PSEUDO_RANDOM>
grass ./G_mosaic_$$/PERMANENT --exec ./dm.grass.sh $DATE $INFOLDER $OUTFOLDER
# rm -fR ./G_mosaic_$$ # cleanup


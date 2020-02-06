#!/bin/bash

set -x

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <yyyy-mm-dd> <infolder> <outfolder>" >&2
  exit 1
fi

date=$1      # YYYY-MM-DD
infolder=$2  # ./tmp ?
outfolder=$3 # ./mosaic ?

grassroot=${infolder}/G
mkdir -p ${outfolder}
grass -e -c mask.tif ${grassroot}
grass ${grassroot}/PERMANENT --exec ./dm.grass.sh ${date} ${infolder} ${outfolder}
rm -fR ${grassroot} # cleanup

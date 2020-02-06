#!/usr/bin/env bash 

set -o errexit
set -o nounset
set -o pipefail
set -x

declare folder=$1
declare mask=$2
declare resize=$3

tifopts='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'

# import mask and set this as our region
r.import input=${mask} output=mask
g.region raster=mask res=${resize}

# activate mask
r.mask mask --o

# import SZA and zoom SUBSET region of this scene and mask
r.external source=${folder}/SZA_x.tif output=SZA --q
g.region zoom=SZA

# save SZA and subset mask
r.out.gdal -c -m input=SZA output=${folder}/SZA.tif ${tifopts} --q
r.out.gdal -c -m input=mask output=${folder}/mask.tif ${tifopts} --q

# process all other GeoTIFF files
parallel -j 1 "r.in.gdal input={} output={/.} --q --o" ::: $(ls ${folder}/*_x.tif)
out_list=$(g.list type=raster | grep -Ev "mask|MASK|SZA" | sed 's/_x//')
parallel -j 1 "r.out.gdal -m -c input={}_x output=${folder}/{}.tif ${tifopts} --o" ::: ${out_list}

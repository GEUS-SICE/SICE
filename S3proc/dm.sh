#!/usr/bin/env bash

# ./dm.sh 20170801 ./tmp ./mosaic

export GISBASE=/sw/Applications/GRASS-mac-7.2.app/Contents/MacOS

${GISBASE}/grass.sh -e -c EPSG:3413 /tmp/mosaic

#generate GISRCRC
MYGISDBASE=/tmp/
MYLOC=mosaic
MYMAPSET=PERMANENT

# Set the global grassrc file to individual file name
MYGISRC="$HOME/.grassrc.$GRASS_VERSION.$$"

echo "GISDBASE: $MYGISDBASE" > "$MYGISRC"
echo "LOCATION_NAME: $MYLOC" >> "$MYGISRC"
echo "MAPSET: $MYMAPSET" >> "$MYGISRC"
echo "GRASS_GUI: text" >> "$MYGISRC"
 
# path to GRASS settings file
export GISRC=$MYGISRC
export GRASS_PYTHON=python
export GRASS_MESSAGE_FORMAT=plain
# export GRASS_TRUECOLOR=TRUE
# export GRASS_TRANSPARENT=TRUE
# export GRASS_PNG_AUTO_WRITE=TRUE
# export GRASS_GNUPLOT='gnuplot -persist'
# export GRASS_WIDTH=640
# export GRASS_HEIGHT=480
# # export GRASS_HTML_BROWSER=firefox
# export GRASS_PAGER=cat
# export GRASS_WISH=wish
        
export PATH="$GISBASE/bin:$GISBASE/scripts:$PATH"
export LD_LIBRARY_PATH="$GISBASE/lib"
export GRASS_LD_LIBRARY_PATH="$LD_LIBRARY_PATH"
export PYTHONPATH="$GISBASE/etc/python:$PYTHONPATH"
export MANPATH=$MANPATH:$GISBASE/man

export GIS_LOCK=42
# #For the temporal modules
# export TGISDB_DRIVER=sqlite
# export TGISDB_DATABASE=$MYGISDBASE/$MYLOC/PERMANENT/tgis/sqlite.db

# # test a command
# g.list rast
# g.region -p


if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <yyyymmdd> <infolder> <outfolder>" >&2
  exit 1
fi

DATE=$1
INFOLDER=$2
OUTFOLDER=$3

if ! [ -e "$INFOLDER" ]; then
  echo "$INFOLDER not found" >&2
  exit 1
fi
mkdir -p $OUTFOLDER/${DATE}

# # load all the data
for ASCENE in $(cd $INFOLDER; find . -name "${DATE}T??????" -type d -depth 1); do
    SCENE=$(echo $ASCENE | cut -c3-)
    g.mapset -c ${SCENE}
    for file in $(ls ${INFOLDER}/${SCENE}/*.tif); do
	# echo $file
	band=$(echo $(basename ${file} .tif) | cut -d"_" -f1)
	# echo $band
	r.in.gdal input=${file} output=${band}
    done
done

BANDS=$(g.list type=raster mapset=* | cut -d"@" -f1 | sort | uniq)


# # # set the region to include all the data
g.mapset PERMANENT
g.region raster=$(g.list type=raster pattern=SZA separator=, mapset=*)
g.region res=500 -a -p
g.region -s
g.mapset -c ${DATE}

# g.list type=raster pattern=SZA mapset=*
SZA_arr=($(g.list type=raster pattern=SZA mapset=*))
# echo ${SZA_arr[@]}
SZA_list=$(g.list type=raster pattern=SZA mapset=* separator=comma)

# find the array index with the minimum SZA
r.series input=${SZA_list} method=min_raster output=SZA_LUT --o

SZA_LUT_idxs=$(r.stats -n -l SZA_LUT)
n_imgs=$(echo $SZA_LUT_idxs |wc -w)


# make N temp rasters, one for each patch, each masked as appropriate
for i in $SZA_LUT_idxs; do
    echo $i
    r.mask raster=SZA_LUT maskcats=${i} --o --q
    g.region raster=MASK zoom=MASK
    
    # r.mapcalc "tmp_${i} = ${SZA_arr[${i}]}" --o
    for B in $(echo ${BANDS}); do
	# BAND_arr copied from the SZA_arr above:
	echo $B
	BAND_arr=($(g.list type=raster pattern=${B} mapset=*))
	r.mapcalc "${B}_tmp_${i} = ${BAND_arr[${i}]}" --o
    done
done
r.mask -r
g.region -d

# patch the temp arrays to one mosaic and write to disk
TIFOPTS='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'
for B in $(echo ${BANDS}); do
    r.patch input=$(g.list type=raster pattern="${B}_tmp_*" separator=,) output=${B} --o
    r.colors map=${B} color=grey
    r.out.gdal -c input=${B} output=${OUTFOLDER}/${DATE}/${B}.tif ${TIFOPTS}
done

r.composite -d -c blue=Oa04 green=Oa06 red=Oa08 output=RGB --o
r.out.gdal -c input=RGB output=${OUTFOLDER}/${DATE}/RGB.tif ${TIFOPTS}
r.out.png input=RGB output=${OUTFOLDER}/${DATE}/RGB.png --o

g.remove -f type=raster pattern="*_tmp_*"


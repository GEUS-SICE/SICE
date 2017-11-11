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
# DATE=20170601
# INFOLDER=./tmp
# OUTFOLDER=./mosaic

###
### Export code below comes from
### https://grasswiki.osgeo.org/wiki/Working_with_GRASS_without_starting_it_explicitly#Bash_examples_.28GNU.2FLinux.29
###

## This is from "fink install grass72"
export GISBASE=/sw/Applications/GRASS-mac-7.2.app/Contents/MacOS

## Work in /tmp/tmpG
MYGISDBASE=/tmp
MYLOC=tmpG
MYMAPSET=PERMANENT

rm -fR ${MYGISDBASE}/${MYLOC}
${GISBASE}/grass.sh -e -c EPSG:3413  ${MYGISDBASE}/${MYLOC}

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
export GRASS_TRUECOLOR=TRUE
export GRASS_TRANSPARENT=TRUE
# export GRASS_WIDTH=640
# export GRASS_HEIGHT=480
        
export PATH="$GISBASE/bin:$GISBASE/scripts:$PATH"
export LD_LIBRARY_PATH="$GISBASE/lib"
export GRASS_LD_LIBRARY_PATH="$LD_LIBRARY_PATH"
export PYTHONPATH="$GISBASE/etc/python:$PYTHONPATH"
export MANPATH=$MANPATH:$GISBASE/man

export GIS_LOCK=42

###
###
###

if ! [ -e "$INFOLDER" ]; then
  echo "$INFOLDER not found" >&2
  exit 1
fi
mkdir -p $OUTFOLDER/${DATE}

# load all the data
for ASCENE in $(cd $INFOLDER; find . -name "${DATE}T??????" -type d -depth 1); do
    SCENE=$(echo $ASCENE | cut -c3-)
    g.mapset -c ${SCENE} --quiet
    for file in $(ls ${INFOLDER}/${SCENE}/*.tif); do
        echo "Importing $file"
        band=$(echo $(basename ${file} .tif))
        # echo $band
        r.in.gdal input=${file} output=${band} --quiet

        # fix inf values in two of the rasters
        if [[ ${band} == "albedo_broadband_planar" ]] || [[ ${band} == "albedo_broadband_spherical" ]]; then
           r.null map=${band} setnull=inf --quiet
        fi
    done
done


# The target bands. For example, Oa01_reflectance or SZA.
BANDS=$(g.list type=raster mapset=* | cut -d"@" -f1 | sort | uniq)

# Mask and zoom to Greenland ice+land
g.mapset PERMANENT --quiet
g.region raster=$(g.list type=raster pattern=SZA separator=, mapset=*)
g.region res=500 -a
r.in.gdal input=mask.tif output=MASK --quiet
g.region zoom=MASK
g.region -s # save as default region
g.mapset -c ${DATE} --quiet # create a new mapset for final product
r.mask raster=MASK@PERMANENT --o # mask to Greenland ice+land

# find the array index with the minimum SZA
# Array for indexing, list for using in GRASS
SZA_arr=($(g.list type=raster pattern=SZA mapset=*))
SZA_list=$(g.list type=raster pattern=SZA mapset=* separator=comma)
r.series input=${SZA_list} method=min_raster output=SZA_LUT --o

# find the indices used. It is possible one scene is never used
SZA_LUT_idxs=$(r.stats -n -l SZA_LUT)
n_imgs=$(echo $SZA_LUT_idxs |wc -w)

# Patch each BAND based on the minimum SZA_LUT
for B in $(echo $BANDS); do
    # this band in all of the sub-mapsets (with a T (timestamp) in the mapset name)
    B_arr=($(g.list type=raster pattern=${B} mapset=* | grep "@.*T"))
    r.mapcalc "${B} = null()" --o --q
    for i in $SZA_LUT_idxs; do
        echo "patching ${B} from ${B_arr[${i}]} [$i]"
        r.mapcalc "${B} = if(SZA_LUT == ${i}, ${B_arr[${i}]}, ${B})" --o --q
    done
done

# save everything to disk
TIFOPTS='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'
for B in $(echo ${BANDS}); do
    echo "Writing ${B} to ${OUTFOLDER}/${DATE}/${B}.tif"
    r.colors map=${B} color=grey --q
    r.out.gdal -m -c input=${B} output=${OUTFOLDER}/${DATE}/${B}.tif ${TIFOPTS}
done

# combine bands to make RGB
echo "Writing out RGB and SZA_LUT"
r.composite -d -c blue=Oa04_reflectance green=Oa06_reflectance red=Oa08_reflectance output=RGB --o
r.out.gdal -m -c input=RGB output=${OUTFOLDER}/${DATE}/RGB.tif ${TIFOPTS}
r.out.png input=RGB output=${OUTFOLDER}/${DATE}/RGB.png --o
r.colors map=SZA_LUT color=random
r.out.png input=SZA_LUT output=${OUTFOLDER}/${DATE}/SZA_LUT.png --o

# rm -fR /tmp/tmpG

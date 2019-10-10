#!/usr/bin/env bash 

DATE=$1
INFOLDER=$2
OUTFOLDER=$3

if ! [ -e "$INFOLDER" ]; then
  echo "$INFOLDER not found" >&2
  exit 1
fi
mkdir -p $OUTFOLDER/${DATE}
mkdir -p tmp

# load all the data
SCENES=$(cd $INFOLDER; ls | grep -E "${DATE}T??????")
SCENE=$(echo ${SCENES}|tr ' ' '\n' | head -n1) # DEBUG
for SCENE in ${SCENES}; do
    g.mapset -c ${SCENE} --quiet
    FILES=$(ls ${INFOLDER}/${SCENE}/*.tif)
    echo "Fixing NODATA values for ${SCENE}"
    parallel --bar --verbose \
	     "gdalwarp -q  -s_srs EPSG:3413 -srcnodata -999 {} ./tmp/{%}.tif; mv ./tmp/{%}.tif {}" \
	     ::: ${FILES}
    echo "Importing data for ${SCENE}"
    parallel  "r.external source={} output={/.} --quiet --o" ::: ${FILES}

    # SZA cloud masked (CM)
    echo "Masking clouds in SZA rasters"
    r.mapcalc "SZA_CM = SZA" --o --q
    r.mapcalc "SZA_CM = olci_toa_sza" --o --q
    r.mapcalc "SZA_CM = if(idepix_cloud_ambiguous == 255, null(), SZA)" --o --q
done

# The target bands. For example, Oa01_reflectance or SZA.
BANDS=$(g.list type=raster mapset=* | cut -d"@" -f1 | sort | uniq)

# Mask and zoom to Greenland ice+land
g.mapset PERMANENT --quiet
r.in.gdal input=mask.tif output=MASK --quiet
g.region raster=MASK
g.region zoom=MASK
g.region res=10000 -a
# g.region raster=$(g.list type=raster pattern=SZA separator=, mapset=*)
g.region -s # save as default region
g.mapset -c ${DATE} --quiet # create a new mapset for final product
r.mask raster=MASK@PERMANENT --o # mask to Greenland ice+land

# find the array index with the minimum SZA
# Array for indexing, list for using in GRASS
SZA_arr=($(g.list type=raster pattern=SZA_CM mapset=*))
SZA_list=$(g.list type=raster pattern=SZA_CM mapset=* separator=comma)
r.series input=${SZA_list} method=min_raster output=SZA_LUT --o
echo ${SZA_list} | tr ',' '\n' | cut -d@ -f2 > ${OUTFOLDER}/${DATE}/SZA_LUT.txt

# find the indices used. It is possible one scene is never used
SZA_LUT_idxs=$(r.stats -n -l SZA_LUT)
n_imgs=$(echo $SZA_LUT_idxs |wc -w)

# generate a raster of nulls that we can then patch into
echo "Initializing mosaic scenes..."
parallel  --bar "r.mapcalc \"{} = null()\" --o --q" ::: ${BANDS}

### REFERENCE LOOP VERSION
# # Patch each BAND based on the minimum SZA_LUT
# for B in $(echo $BANDS); do
#     # this band in all of the sub-mapsets (with a T (timestamp) in the mapset name)
#     B_arr=($(g.list type=raster pattern=${B} mapset=* | grep "@.*T"))
#     for i in $SZA_LUT_idxs; do
#         echo "patching ${B} from ${B_arr[${i}]} [$i]"
#         r.mapcalc "${B} = if(SZA_LUT == ${i}, ${B_arr[${i}]}, ${B})" --o --q
#     done
# done

# PARALLEL?
echo "Patching bands based on minmum SZA_LUT"
doit() {
    B_arr=($(g.list type=raster pattern=${2} mapset=* | grep "@.*T"))
    r.mapcalc "${2} = if(SZA_LUT == ${1}, ${B_arr[${1}]}, ${2})" --o --q
}
export -f doit
for i in $SZA_LUT_idxs; do
    parallel  --bar doit ${i} ::: ${BANDS}
done

echo "Writing mosaics to disk..."
TIFOPTS='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'
parallel  "r.colors map={} color=grey --q" ::: ${BANDS} # grayscale
parallel  --bar "r.null map={} setnull=inf --q" ::: ${BANDS}  # set inf to null
parallel  --bar "r.out.gdal -m -c input={} output=${OUTFOLDER}/${DATE}/{}.tif ${TIFOPTS}" ::: ${BANDS}

# # Loading the mosaics
# r.external input=${OUTFOLDER}/${DATE}/Oa01_reflectance.tif output=Oa01_reflectance --o --quiet
# r.external input=${OUTFOLDER}/${DATE}/Oa06_reflectance.tif output=Oa06_reflectance --o --quiet
# r.external input=${OUTFOLDER}/${DATE}/Oa10_reflectance.tif output=Oa10_reflectance --o --quiet
# r.external input=${OUTFOLDER}/${DATE}/Oa11_reflectance.tif output=Oa11_reflectance --o --quiet
# r.external input=${OUTFOLDER}/${DATE}/Oa17_reflectance.tif output=Oa17_reflectance --o --quiet
# r.external input=${OUTFOLDER}/${DATE}/Oa21_reflectance.tif output=Oa21_reflectance --o --quiet

# # uses mosaic to calculate broadband albedo using empirical approach
# r.mapcalc "BBA_empirical = min((Oa01_reflectance + Oa06_reflectance + Oa17_reflectance + Oa21_reflectance) / 4.0 * 0.945 + 0.055,1)" --o 
# r.out.gdal --overwrite -m -c input=BBA_empirical output=${OUTFOLDER}/${DATE}/BBA_empirical.tif

# # uses mosaic to calculate algal cellcount using empirical approach
# r.mapcalc "C_algea_empirical = 10^7 * (log(Oa11_reflectance / Oa10_reflectance))^2" --o
# r.out.gdal --overwrite -m -c input=C_algea_empirical output=${OUTFOLDER}/${DATE}/C_algea_empirical.tif

# combine bands to make RGB
# echo "Writing out RGB and SZA_LUT"

# gdaldem color-relief $(g.list type=raster | head -n1)  col.txt ${OUTFOLDER}/${DATE}/thumb.jpeg -of JPEG -s 0.05
# r.composite -d -c blue=Oa04_reflectance green=Oa06_reflectance red=Oa08_reflectance output=RGB --o
# r.out.gdal -m -c input=RGB output=${OUTFOLDER}/${DATE}/RGB.tif ${TIFOPTS}
# r.out.png input=RGB output=${OUTFOLDER}/${DATE}/RGB.png --o

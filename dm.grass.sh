#!/usr/bin/env bash 

set -o errexit
set -o nounset
set -o pipefail

declare date=$1
declare infolder=$2
declare outfolder=$3

red='\033[0;31m'; orange='\033[0;33m'; green='\033[0;32m'; nc='\033[0m' # No Color
log_info() { echo -e "${green}[$(date --iso-8601=seconds)] [INFO] ${@}${nc}"; }
log_warn() { echo -e "${orange}[$(date --iso-8601=seconds)] [WARN] ${@}${nc}"; }
log_err() { echo -e "${red}[$(date --iso-8601=seconds)] [ERR] ${@}${nc}" 1>&2; }

trap ctrl_c INT # trap ctrl-c and call ctrl_c()
ctrl_c() { log_err "CTRL-C. Cleaning up"; }

debug() { if [[ ${debug:-} == 1 ]]; then log_warn "debug:"; echo $@; fi; }

[[ -d "${infolder}" ]] || (log_err "${infolder} not found"; exit 1)

mkdir -p "${outfolder}/${date}"

# load all the data
scenes=$(cd "${infolder}"; ls | grep -E "${date}T??????")
scene=$(echo ${scenes}|tr ' ' '\n' | head -n1) # DEBUG
for scene in ${scenes}; do
  g.mapset -c ${scene} --quiet
  g.region res=1000 -a --quiet
  files=$(ls ${infolder}/${scene}/*.tif || true)
  if [[ -z ${files} ]]; then log_err "No files: ${scene}"; continue; fi
  log_info "Importing rasters: ${scene}"
  parallel  "r.external source={} output={/.} --q" ::: ${files}
  
  # # UNCOMMENT to turn on SZA-only mosaic (no cloud-criteria)
  # r.mapcalc "SZA_CM = SZA" --q

  # these need to be imported, not external, so we can tweak the null mask
  g.remove -f type=raster name=cloud_an,confidence_an --q
  r.in.gdal input=${infolder}/${scene}/cloud_an.tif output=cloud_an --q --o
  r.in.gdal input=${infolder}/${scene}/confidence_an.tif output=confidence_an --q --o
  r.null map=cloud_an setnull=0 --q
  r.null map=confidence_an setnull=0 --q

  # SZA_CM is SZA but Cloud Masked
  log_info "Masking clouds in SZA raster"
  # r.mapcalc "cloud_flag = if((cloud_an & 2), null(), 1)" --q
  r.mapcalc "cloud_flag = 1" --q
  r.mapcalc "conf_flag = if((confidence_an & 16384), null(), 1)" --q
  # SZA only valid where all flags are equal to 1
  r.mapcalc "SZA_CM = if((cloud_flag && conf_flag), SZA)" --q

  # remove small clusters of isolated pixels
  # frink "(1000 m)^2 -> hectares" 100 hectares per pixel, so value=10000 -> 10 pixels
  r.mapcalc "SZA_CM_mask = if(SZA_CM)" --q
  r.clump -d input=SZA_CM_mask output=SZA_CM_clump --q
  r.reclass.area -c input=SZA_CM_clump output=SZA_CM_area value=10000 mode=greater --q
  r.mapcalc "SZA_CM_rmarea = if(SZA_CM_area, SZA_CM)" --q
done

# The target bands. For example, Oa01_reflectance or SZA.
bands=$(g.list type=raster mapset=* | cut -d"@" -f1 | sort | uniq)

# Mask and zoom to Greenland ice+land
g.mapset PERMANENT --quiet
r.in.gdal input=mask.tif output=MASK --quiet
g.region raster=MASK
g.region zoom=MASK
g.region res=1000 -a
# g.region raster=$(g.list type=raster pattern=SZA separator=, mapset=*)
g.region -s # save as default region
g.mapset -c ${date} --quiet # create a new mapset for final product
r.mask raster=MASK@PERMANENT --o # mask to Greenland ice+land

# find the array index with the minimum SZA
# Array for indexing, list for using in GRASS
sza_arr=($(g.list type=raster pattern=SZA_CM_rmarea mapset=*))
sza_list=$(g.list type=raster pattern=SZA_CM_rmarea mapset=* separator=comma)
r.series input=${sza_list} method=min_raster output=sza_lut --o
# echo ${SZA_list} | tr ',' '\n' | cut -d@ -f2 > ${OUTFOLDER}/${DATE}/SZA_LUT.txt

# find the indices used. It is possible one scene is never used
sza_lut_idxs=$(r.stats -n -l sza_lut)
n_imgs=$(echo $sza_lut_idxs |wc -w)

# generate a raster of nulls that we can then patch into
log_info "Initializing mosaic scenes..."
parallel "r.mapcalc \"{} = null()\" --o --q" ::: ${bands}

### REFERENCE LOOP VERSION
# # Patch each BAND based on the minimum SZA_LUT
# for b in $(echo $bands); do
#     # this band in all of the sub-mapsets (with a T (timestamp) in the mapset name)
#     b_arr=($(g.list type=raster pattern=${b} mapset=* | grep "@.*T"))
#     for i in $sza_lut_idxs; do
#         echo "patching ${b} from ${b_arr[${i}]} [$i]"
#         r.mapcalc "${b} = if(sza_lut == ${i}, ${b_arr[${i}]}, ${b})" --o --q
#     done
# done

# PARALLEL?
log_info "Patching bands based on minmum SZA_LUT"
doit() {
  local idx=$1
  local band=$2
  local b_arr=($(g.list type=raster pattern=${band} mapset=* | grep "@.*T"))
  r.mapcalc "${band} = if((sza_lut == ${idx}), ${b_arr[${idx}]}, ${band})" --o --q
}
export -f doit
parallel doit {1} {2} ::: ${sza_lut_idxs} ::: ${bands}

# diagnostics
r.series input=${sza_list} method=count output=num_scenes_cloudfree
mapset_list=$(g.mapsets --q -l separator=newline | grep T | tr '\n' ','| sed 's/,*$//g')
raster_list=$(g.list type=raster pattern=reflectance_Oa01 mapset=${mapset_list} separator=comma)
r.series input=${raster_list} method=count output=num_scenes

bandsFloat32=$(g.list type=raster pattern="reflectance_*")
bandsInt16="sza_lut cloud_an confidence_an num_scenes num_scenes_cloudfree"
log_info "Writing mosaics to disk..."

tifopts='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'
parallel "r.colors map={} color=grey --q" ::: ${bandsFloat32} # grayscale
parallel "r.null map={} setnull=inf --q" ::: ${bandsFloat32}  # set inf to null
parallel "r.out.gdal -m -c input={} output=${outfolder}/${date}/{}.tif ${tifopts}" ::: ${bandsFloat32}

tifopts='type=Int16 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'
parallel "r.out.gdal -m -c input={} output=${outfolder}/${date}/{}.tif ${tifopts}" ::: ${bandsInt16}

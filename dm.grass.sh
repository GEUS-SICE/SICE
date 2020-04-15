#!/usr/bin/env bash 

set -o errexit
set -o nounset
set -o pipefail
set -x

declare date=$1
declare infolder=$2
declare outfolder=$3

red='\033[0;31m'; orange='\033[0;33m'; green='\033[0;32m'; nc='\033[0m' # No Color
log_info() { echo -e "${green}[$(date --iso-8601=seconds)] [INFO] ${@}${nc}"; }
log_warn() { echo -e "${orange}[$(date --iso-8601=seconds)] [WARN] ${@}${nc}"; }
log_err() { echo -e "${red}[$(date --iso-8601=seconds)] [ERR] ${@}${nc}" 1>&2; }

trap ctrl_c INT # trap ctrl-c and call ctrl_c()
ctrl_c() { log_err "CTRL-C. Cleaning up"; }

trap err_exit ERR
err_exit() { log_err "CLEANUP HERE"; }

debug() { if [[ ${debug:-} == 1 ]]; then log_warn "debug:"; echo $@; fi; }

[[ -d "${infolder}" ]] || (log_err "${infolder} not found"; exit 1)

mkdir -p "${outfolder}/${date}"


# Zoom to mask region
r.in.gdal input=mask.tif output=MASK --quiet
g.region raster=MASK
g.region zoom=MASK
g.region res=1000 -a
g.region -s # save as default region

# load all the data
yyyymmdd=${date:0:4}${date:5:2}${date:8:2}
scenes=$(cd "${infolder}"; ls | grep -E "${yyyymmdd}T??????")
scene=$(echo ${scenes}|tr ' ' '\n' | head -n3|tail -n1) # DEBUG

for scene in ${scenes}; do
  g.mapset -c ${scene} --q
  g.region -d --q
  files=$(ls ${infolder}/${scene}/*.tif || true)
  if [[ -z ${files} ]]; then log_err "No files: ${scene}"; continue; fi
  log_info "Importing rasters: ${scene}"
  parallel -j 1 "r.external source={} output={/.} --q" ::: ${files}
  
  log_info "Masking clouds in SZA raster"
  r.grow input=SCDA_v20 output=SCDA_grow radius=-5 new=-1 --q # increase clouds by 5 pixels
  # remove small clusters of isolated pixels
  r.clump -d input=SCDA_grow output=SCDA_clump --q
  # frink "(1000 m)^2 -> hectares" 100 hectares per pixel, so value=10000 -> 10 pixels
  # this sometimes fails. Force success (||true) and check for failure on next line.
  r.reclass.area -c input=SCDA_clump output=SCDA_area value=10000 mode=greater --q || true
  [[ "" == $(g.list type=raster pattern=SCDA_area) ]] && r.mapcalc "SCDA_area = null()" --q
  # SZA_CM is SZA but Cloud Masked: Invalid where buffered clouds over ice w/ valid SZA
  r.mapcalc "SZA_CM0 = if((isnull(SCDA_area) && (MASK@PERMANENT == 220)) || (isnull(SCDA_v20) && (MASK@PERMANENT != 220)), null(), 1)" --q
  r.mapcalc "SZA_CM = if(not(isnull(SZA)) & SZA_CM0, 1, null())" --q
  g.remove -f type=raster name=SCDA_grow,SCDA_clump,SCDA_area,SZA_CM0 --q
done

# The target bands. For example, R_TOA_01 or SZA.
bands=$(g.list type=raster mapset=* -m | grep -v PERMANENT | cut -d"@" -f1 | sort | uniq)

g.mapset -c ${date} --quiet # create a new mapset for final product
r.mask raster=MASK@PERMANENT --o --q # mask to Greenland ice+land

# find the array index with the minimum SZA
# Array for indexing, list for using in GRASS
sza_arr=($(g.list -m type=raster pattern=SZA_CM mapset=*))
sza_list=$(g.list -m type=raster pattern=SZA_CM mapset=* separator=comma)

r.series input=${sza_list} method=min_raster output=sza_lut --o --q
# echo ${SZA_list} | tr ',' '\n' | cut -d@ -f2 > ${outfolder}/${date}/SZA_LUT.txt

# find the indices used. It is possible one scene is never used
sza_lut_idxs=$(r.stats --q -n -l sza_lut)
n_imgs=$(echo $sza_lut_idxs |wc -w)

# generate a raster of nulls that we can then patch into
log_info "Initializing mosaic scenes..."
parallel -j 1 "r.mapcalc \"{} = null()\" --o --q" ::: ${bands}

### REFERENCE LOOP VERSION
# Patch each BAND based on the minimum SZA_LUT
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

parallel -j 1 doit {1} {2} ::: ${sza_lut_idxs} ::: ${bands}

# diagnostics
r.series input=${sza_list} method=count output=num_scenes_cloudfree --q
mapset_list=$(g.mapsets --q -l separator=newline | grep T | tr '\n' ','| sed 's/,*$//g')
raster_list=$(g.list type=raster pattern=r_TOA_01 mapset=${mapset_list} separator=comma)
r.series input=${raster_list} method=count output=num_scenes --q

bandsFloat32="$(g.list type=raster pattern="r_TOA_*") SZA SAA OZA OAA WV O3 NDSI BT_S7 BT_S8 BT_S9 r_TOA_S5 r_TOA_S5_rc r_TOA_S1 height"
bandsInt16="sza_lut num_scenes num_scenes_cloudfree"
log_info "Writing mosaics to disk..."

tifopts='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'
parallel -j 1 "r.colors map={} color=grey --q" ::: ${bandsFloat32} # grayscale
parallel -j 1 "r.null map={} setnull=inf --q" ::: ${bandsFloat32}  # set inf to null
parallel "r.out.gdal -m -c input={} output=${outfolder}/${date}/{}.tif ${tifopts}" ::: ${bandsFloat32}

tifopts='type=Int16 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'
parallel "r.out.gdal -m -c input={} output=${outfolder}/${date}/{}.tif ${tifopts}" ::: ${bandsInt16}

# Generate some extra rasters
tifopts='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q --o'
r.mapcalc "ndbi = ( r_TOA_01 - r_TOA_21 ) / ( r_TOA_01 + r_TOA_21 )"
r.mapcalc "bba_emp = (r_TOA_01 + r_TOA_06 + r_TOA_17 + r_TOA_21) / (4.0 * 0.945 + 0.055)"
r.out.gdal -f -m -c input=ndbi output=${outfolder}/${date}/NDBI.tif ${tifopts}
r.out.gdal -f -m -c input=bba_emp output=${outfolder}/${date}/BBA_emp.tif ${tifopts}

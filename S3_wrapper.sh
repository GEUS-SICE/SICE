
# 2017 & 2018
# 15 March (074) - 30 Sep (274)

# CREODIAS
SEN3_source=/eodata/Sentinel-3
dest_root=/sice-data/SICE/S3
proc_root=/sice-data/SICE/proc
mosaic_root=/sice-data/SICE/mosaic

# # dev
# dest_root=./SEN3
# proc_root=./out
# mosaic_root=./mosaic

set -o errexit
set -o nounset
set -o pipefail

LD_LIBRARY_PATH=. # SNAP requirement

for year in 2018 2017; do
  for doy in $(seq -w 74 274); do

#     ## DEBUG
# for year in 2017; do
#   for doy in 227 180; do  # 2017-08-15=227

    date=$(date -d "${year}-01-01 +$(( 10#${doy}-1 )) days" "+%Y-%m-%d")

    # # # Fetch one day of OLCI & SLSTR scenes over Greenland
    if [[ ! -d "${dest_root}/${year}/${date}" ]]; then
      mkdir -p ${dest_root}/${year}/${date}
      # ./dhusget_wrapper.sh -d ${date} -l ${SEN3_source} -o ${dest_root}/${year}/${date}
      ./dhusget_wrapper.sh -d ${date} -o ${dest_root}/${year}/${date}
    fi
    
    # SNAP: Reproject, calculate reflectance, extract bands, etc.
    if [[ ! -d "${proc_root}/${date}" ]]; then
      ./S3_proc.sh -i ${dest_root}/${year}/${date} -o ${proc_root}/${date} -X S3.xml -t
    fi
    
    # SICE
    # Does SnBBA exist already in every folder?
    if [[ $(cd ${proc_root}/${date}; ls) \
	    != $(cd ${proc_root}/${date}; ls */SnBBA.tif | parallel dirname) ]]; then
      parallel --verbose --lb -j 5 \
    	       python ./sice.py ${proc_root}/${date}/{} \
    	       ::: $(ls ${proc_root}/${date}/)
    fi
    
    # Mosaic
    if [[ ! -f "${mosaic_root}/${date}/SZA.tif" ]]; then
      ./dm.sh ${date} ${proc_root}/${date} ${mosaic_root}
    fi

    # Extra
    if [[ $(ls ${mosaic_root}/${date}/* | grep BBA_emp.tif) == "" ]]; then
      gdal_opts='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q'
      _cwd=$(pwd)
      cd ${mosaic_root}/${date}/
      tmpdir=./G_$$
      grass -c SZA.tif ${tmpdir} --exec <<EOF
r.external input=r_TOA_01.tif output=r01
r.external input=r_TOA_06.tif output=r06
r.external input=r_TOA_17.tif output=r17
r.external input=r_TOA_21.tif output=r21
r.mapcalc "ndsi = (r17-r21)/(r17+r21)"
r.mapcalc "ndbi = (r01-r21)/(r01+r21)"
r.mapcalc "bba_emp = (r01 + r06 + r17 + r21) / (4.0 * 0.945 + 0.055)"
r.out.gdal -f -m -c input=ndsi output=NDSI.tif ${gdal_opts}
r.out.gdal -f -m -c input=ndbi output=NDBI.tif ${gdal_opts}
r.out.gdal -f -m -c input=bba_emp output=BBA_emp.tif ${gdal_opts}
EOF
      rm -fR ${tmpdir}
      cd ${_cwd}
    fi

  done
done

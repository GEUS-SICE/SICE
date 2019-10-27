
# 2017 & 2018
# 15 March (047) - 30 Sep (274)

# CREODAS
SEN3_source=/eodata/Sentinel-3
dest_root=/s3-data/S3
proc_root=/s3-data/proc
mosaic_root=/s3-data/mosaic

# dev
dest_root=./SEN3
proc_root=./out
mosaic_root=./mosaic

set -o errexit
set -o nounset
set -o pipefail

LD_LIBRARY_PATH=. # SNAP requirement

for year in 2017 2018; do
  for doy in $(seq -w 47 274); do

    ## DEBUG
# for year in 2017; do
#   for doy in 227; do  # 2017-08-15

    date=$(date -d "${year}-01-01 +$(( 10#${doy}-1 )) days" "+%Y-%m-%d")

    # Fetch one day of OLCI & SLSTR scenes over Greenland
    mkdir -p ${dest_root}/${year}/${date}
    ./dhusget_wrapper.sh -d ${date} -l ${SEN3_source} -o ${dest_root}/${year}/${date}
    # ./dhusget_wrapper.sh -d ${date} -o ${dest_root}/${year}/${date}

    # SNAP: Reproject, calculate reflectance, extract bands, etc.
    ./S3_proc.sh -i ${dest_root}/${year}/${date} -o ${proc_root}/${date} -X S3.xml -t

    # SICE
    parallel --verbose --lb -j 3 \
    	     python ./sice.py ${proc_root}/${date}/{} \
    	     ::: $(ls ${proc_root}/${date}/)

    # Mosaic
    ./dm.sh ${date} ${proc_root}/${date} ${mosaic_root}

    # Extra
#    tmpdir=./G_$$
#     grass -c ${mosaic_root}/${date}/SZA.tif ${tmpdir} --exec <<EOF
# r.external input=rflectance_Oa01.tif output=r01
# r.external input=rflectance_Oa06.tif output=r06
# r.external input=rflectance_Oa17.tif output=r17
# r.external input=rflectance_Oa21.tif output=r21
# r.mapcalc "andsi = (r17-r21)/(r17+r21)"
# r.mapcalc "andbi = (r01-r21)/(r01+r21)"
# r.mapcalc "bba = (r01 + r06 + r17 + r21) / (4.0 * 0.945 + 0.055"
# gdal_opts='type=Float32 createopt=COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES --q'
# r.out.gdal -m -c input=andsi output=${mosaic_root}/${date}/ANDSI.tif ${tifopts}
# r.out.gdal -m -c input=andbi output=${mosaic_root}/${date}/ANDBI.tif ${tifopts}
# r.out.gdal -m -c input=bba output=${mosaic_root}/${date}/BBA.tif ${tifopts}
# EOF
#     rm -fR ${tmpdir}

  done
done

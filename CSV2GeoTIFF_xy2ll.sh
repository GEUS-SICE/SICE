#!/usr/bin/env bash

# CSV=bba_rs3.csv # DEBUG

ORANGE='\033[0;33m'
NC='\033[0m' # No Color
MSG_WARN() { echo -e "${ORANGE}WARNING: ${@}${NC}"; }

RES=10000
MSG_WARN "RES = ${RES}"
g.region -d
g.region res=${RES} -pa

CSVLIST=$@
# echo $CSVLIST

function CSV2GeoTIFF {
    CSV=$1
    BASE=$(basename ${CSV} .csv)
    cat ${CSV} | awk -F, '{print $2"|"$1"|"$3}' | m.proj -i input=- | r.in.xyz --q input=- output=${BASE}
    r.out.gdal --q -c -m input=${BASE} output=${BASE}.tif
}
export -f CSV2GeoTIFF

echo $CSVLIST | tr ' ' '\n' | parallel --bar CSV2GeoTIFF

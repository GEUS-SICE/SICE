#!/usr/bin/env bash

# PATH=~/local/snap/bin:$PATH ./S3_proc.sh -i ./dat_S3A -o ./out_S3A

RED='\033[0;31m'
ORANGE='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
MSG_OK() { printf "${GREEN}${1}${NC}\n"; }
MSG_WARN() { printf "${ORANGE}WARNING: ${1}${NC}\n"; }
MSG_ERR() { printf "${RED}ERROR: ${1}${NC}\n"; }

timing() { if [[ $TIMING == 1 ]]; then MSG_OK "$(date)"; fi; }

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./S3_proc.sh -i inpath -o outpath [-D | -x file.xml] [-h -v -t]"
	    echo "  -i: Path to folder containing S3A_*_EFR_*_002.SEN3 (unzipped S3 EFR) files"
	    echo "  -o: Path where to store ouput"
	    echo "  -D: Use DEBUG.xml (fast, few bands)"
	    echo "  -X: Use non-default XML file [default: S3_proc.xml]"
	    echo "  -v: Print verbose messages during processing"
	    echo "  -t: Print timing messages during processing"
	    echo "  -h: print this help"
	    exit 1;;
	-i)
	    INPATH="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-o)
	    OUTPATH="$2"
	    shift; shift;;
	-X)
	    XML="$2"
	    shift; shift;;
	-D)
	    DEBUG=1
	    shift;;
	-v)
	    VERBOSE=1
	    shift;;
	-t)
	    TIMING=1
	    shift;;
    esac
done

if [ -z $INPATH ] || [ -z $OUTPATH ];then
    echo "-i and -o option not set"
    echo " "
    $0 -h
    exit 1
fi

for folder in $(ls ${INPATH}); do
    S3FOLDER=$(basename ${folder})
    OUTFOLDER=$(echo $S3FOLDER | rev | cut -d_ -f11 | rev)
    DEST=${OUTPATH}/${OUTFOLDER}
    if [[ -d ${DEST} ]]; then
    	MSG_WARN "${OUTPATH}/${OUTFOLDER} already exists. Overwriting and/or adding..."
    else
    	MSG_OK "Generating ${OUTPATH}/${OUTFOLDER}"
    	mkdir -p ${DEST}
    fi

    MSG_OK "GPT: Start"
    timing

    if [[ ${DEBUG} == 1 ]]; then
	MSG_WARN "Using DEBUG.xml"
	MSG_ERR "Not using per pixel geocoding for speed"
	gpt DEBUG.xml -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST} -Ds3tbx.reader.olci.pixelGeoCoding=false
    elif [[ ! -z ${XML} ]]; then 
	MSG_WARN "Using ${XML}"
	MSG_OK "Per-pixel geocoding enabled"
	gpt ${XML} -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST} -Ds3tbx.reader.olci.pixelGeoCoding=true
    else
	MSG_WARN "Using default XML: S3_proc.xml"
	MSG_OK "Per-pixel geocoding enabled"
	gpt S3_proc.xml -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST} -Ds3tbx.reader.olci.pixelGeoCoding=true
    fi
    
    timing
    MSG_OK "GPT: Finished"

    MSG_OK "renaming..."
    for f in $(ls ${DEST}/*_x*); do mv -v ${f} "${f//_x}"; done

    MSG_OK "Compressing: Start"
    timing
    for f in $(ls ${DEST}); do
    	echo $f
    	gdal_translate -co "COMPRESS=DEFLATE" ${DEST}/${f} ${DEST}/${f}_tmp.tif
    	mv  ${DEST}/${f}_tmp.tif ${DEST}/${f}
    done
    timing
    MSG_OK "Finished: ${folder}"
done

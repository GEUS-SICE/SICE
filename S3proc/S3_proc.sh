#!/usr/bin/env bash

# PATH=~/local/snap/bin:$PATH ./S3_proc.sh -i ./dat_S3A -o ./out_S3A

timing() { if [[ $TIMING == 1 ]]; then date; fi; }
message() { if [[ $VERBOSE == 1 ]]; then echo $1; fi; }

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./S3_proc.sh -i inpath -o outpath [-h -v -t]"
	    echo "  -i: Path to folder containing S3A_*_EFR_*_002.SEN3 (unzipped S3 EFR) files"
	    echo "  -o: Path where to store ouput"
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
    	message "${OUTPATH}/${OUTFOLDER} already exists. Skipping processing..."
    	continue
    else
    	message "Generating ${OUTPATH}/${OUTFOLDER}"
    	mkdir -p ${DEST}
    fi

    message "GPT: Start"
    timing
    # process the bands that do not use OLCI.SnowProperties
    gpt S3_proc.xml -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST}
    # process the bands that do use OLCI.SnowProperties
    gpt S3_proc_OLCISnowProcessor.xml -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST}
    timing
    message "GPT: Finished"

    message "renaming..."
    for f in $(ls ${DEST}/*_x*); do mv -v ${f} "${f//_x}"; done

    message "Compressing: Start"
    timing
    for f in $(ls ${DEST}); do
    	echo $f
    	gdal_translate -co "COMPRESS=DEFLATE" ${DEST}/${f} ${DEST}/${f}_tmp.tif
    	mv  ${DEST}/${f}_tmp.tif ${DEST}/${f}
    done
    timing
    message "Finished: ${folder}"
done

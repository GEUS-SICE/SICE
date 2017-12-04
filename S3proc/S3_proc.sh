#!/bin/sh

timing() { if [[ $TIMING == 1 ]]; then date; fi; }
message() { if [[ $VERBOSE == 1 ]]; then echo $1; fi; }

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./S3_proc.sh -i inpath -o outpath [-h -v -t]"
	    echo "  -i: Path to input S3 EFR ZIP files"
	    echo "  -o: Path where to store ouput"
	    echo "  -v: Print verbose messages during processing"
	    echo "  -t: Print timing messages during processing"
	    echo "  -h: print this help"
	    exit 1
	    ;;
	-i)
	    INPATH="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-o)
	    OUTPATH="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-v)
	    VERBOSE=1
	    shift # past argument
	    ;;
	-t)
	    TIMING=1
	    shift # past argument
	    ;;
    esac
done

if [ -z $INPATH ] || [ -z $OUTPATH ];then
    echo "-i and -o option not set"
    echo " "
    $0 -h
    exit 1
fi


for zipfile in $(ls ${INPATH}/S3A_OL_1_EFR____*.zip); do
    S3FOLDER=$(echo $(basename ${zipfile} .zip).SEN3)
    
    OUTFOLDER=$(echo $zipfile | rev | cut -d_ -f11 | rev)
    DEST=${OUTPATH}/${OUTFOLDER}
    # if [[ -d ${OUTPATH}/${OUTFOLDER} ]]; then
    # 	message "${OUTPATH}/${OUTFOLDER} already exists. Skipping processing..."
    # 	continue
    # fi
    # message "Generating ${OUTPATH}/${OUTFOLDER}"

    message "Unzipping: Start"
    timing
    unzip -q -u $zipfile -d ${INPATH}
    timing
    message "Unzipping: Finished"
    
    message "GPT: Start"
    mkdir -p ${DEST}
    timing

    gpt S3_proc.xml -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST}
    timing
    message "GPT: Finished"

    message "Compressing: Start"
    timing
    for f in $(ls ${DEST}); do
	echo $f
    	gdal_translate -co "COMPRESS=DEFLATE" ${DEST}/${f} ${DEST}/${f}_tmp.tif
	mv  ${DEST}/${f}_tmp.tif ${DEST}/${f}
    done
    timing
    message "Extracting and Compressing: Finished"

    # cleanup
    /bin/rm -R ${INPATH}/${S3FOLDER}
done

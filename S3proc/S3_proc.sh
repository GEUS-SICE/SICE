#!/usr/bin/env bash

# PATH=~/local/snap/bin:$PATH ./S3_proc.sh -i ./dat_S3A -o ./out_S3A

timing() { if [[ $TIMING == 1 ]]; then date; fi; }
message() { if [[ $VERBOSE == 1 ]]; then echo $1; fi; }

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./S3_proc.sh -i inpath -o outpath -x XML [-h -v -t]"
	    echo "  -i: Path to input S3 EFR ZIP files"
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

runner() {
    zipfile=$1
    INPATH=$2
    OUTPATH=$3
    
    S3FOLDER=$(echo $(basename ${zipfile} .zip).SEN3)
    OUTFOLDER=$(echo $zipfile | rev | cut -d_ -f11 | rev)
    DEST=${OUTPATH}/${OUTFOLDER}
    if [[ -d ${OUTPATH}/${OUTFOLDER} ]]; then exit; fi # folder already exists
    unzip -q -u $zipfile -d ${INPATH}
    mkdir -p ${DEST}
    gpt S3_proc.xml -q 1 -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST}
    # process the bands that do use OLCI.SnowProperties
    gpt S3_proc_OLCISnowProcessor.xml -q 1 -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST}
    for f in $(ls ${DEST}/*_x*); do mv -v ${f} "${f//_x}"; done
    for f in $(ls ${DEST}); do
	echo $f
    	gdal_translate -co "COMPRESS=DEFLATE" ${DEST}/${f} ${DEST}/${f}_tmp.tif
	mv  ${DEST}/${f}_tmp.tif ${DEST}/${f}
    done
    /bin/rm -R ${INPATH}/${S3FOLDER}
}
export -f runner

ls ${INPATH}/S3?_OL_1_EFR____*.zip | parallel --progress doit ${zipfile} ${INPATH} ${OUTPATH}

# for zipfile in $(ls ${INPATH}/S3?_OL_1_EFR____*.zip); do
#     S3FOLDER=$(echo $(basename ${zipfile} .zip).SEN3)
#     OUTFOLDER=$(echo $zipfile | rev | cut -d_ -f11 | rev)
#     DEST=${OUTPATH}/${OUTFOLDER}
#     if [[ -d ${OUTPATH}/${OUTFOLDER} ]]; then
#     	message "${OUTPATH}/${OUTFOLDER} already exists. Skipping processing..."
#     	continue
#     fi
#     message "Generating ${OUTPATH}/${OUTFOLDER}"

#     message "Unzipping: Start"
#     timing
#     unzip -q -u $zipfile -d ${INPATH}
#     timing
#     message "Unzipping: Finished"
    
#     message "GPT: Start"
#     mkdir -p ${DEST}
#     timing

#     # process the bands that do not use OLCI.SnowProperties
#     gpt S3_proc.xml -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST}
#     # process the bands that do use OLCI.SnowProperties
#     gpt S3_proc_OLCISnowProcessor.xml -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST}

#     timing
#     message "GPT: Finished"

#     message "renaming..."
#     for f in $(ls ${DEST}/*_x*); do mv -v ${f} "${f//_x}"; done

#     message "Compressing: Start"
#     timing
#     for f in $(ls ${DEST}); do
# 	echo $f
#     	gdal_translate -co "COMPRESS=DEFLATE" ${DEST}/${f} ${DEST}/${f}_tmp.tif
# 	mv  ${DEST}/${f}_tmp.tif ${DEST}/${f}
#     done
#     timing
#     message "Extracting and Compressing: Finished"

#     # cleanup
#     /bin/rm -R ${INPATH}/${S3FOLDER}
# done

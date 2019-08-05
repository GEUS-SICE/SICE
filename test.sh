
#!/usr/bin/env bash 
#PATH=~/local/snap/bin:$PATH #./S3_proc.sh -i ./dat_S3A -o ./out_S3A
start=`date +%s`
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
	    echo "./tes.sh -csv"
	    exit 1;;

	-csv)
	    CSV=1
	    shift;;

    esac
done

DEST="20170701T113723"
    timing
	if [ -z $CSV ]; then
	    MSG_OK "Compressing: Start"
		for f in $(ls ${DEST}); do
    		echo $f
    		gdal_translate -co "COMPRESS=DEFLATE" ${DEST}/${f} ${DEST}/${f}_tmp.tif
    		mv  ${DEST}/${f}_tmp.tif ${DEST}/${f}
		done
	else
	    MSG_OK "Grouping csv files"
		paste ${DEST}/*.csv > ${DEST}/tmp.txt
		MSG_OK "Reorganizing columns"

		awk '{print $1 "\t" $2 "\t" $4 "\t" $54 "\t" $50 "\t" $52 "\t" $48 "\t" 1000 "\t" $6 "\t" $8 "\t" $10 "\t" $12 "\t" $14 "\t" $16 "\t" $18 "\t" $20 "\t" $22 "\t" $24"\t" $26 "\t" $28 "\t" $30 "\t" $32 "\t" $34 "\t" $36 "\t" $38 "\t" $40 "\t" $42 "\t" $44"\t" $46}'  ${DEST}/tmp.txt > ${DEST}/olci_toa.txt

		rm ${DEST}/tmp.txt
		MSG_OK "Saving header"

		sed -n '1,2p' ${DEST}/olci_toa.txt > ${DEST}/olci_toa_header.txt
				MSG_OK "Cutting header"

		sed -i '1,2d' ${DEST}/olci_toa.txt
				MSG_OK "Removing NaN"

		awk '$9 != "NaN"' ${DEST}/olci_toa.txt > olci_toa.dat
				MSG_OK "Writting line number"

		wc -l < olci_toa.dat > nlines.dat
		export PATH="$PATH:SnowProcessor"
		./SnowProcessor/sice.exe

	fi
    timing
    MSG_OK "Finished: ${folder}"
	end=`date +%s`
	echo Execution time was `expr $end - $start` seconds.
done

#!/usr/bin/env bash
start=`date +%s`

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./wrapper_mosaic.sh --date [YYYY-MM]"
	    exit 1
	    ;;
	-d|--date)
	    DATE="$2"
	    shift # past argument
	    shift # past value	
		;;
    esac
done

for DD in {1..31}
do
    if [ $DD -lt 10 ];         # If $i is smaller than 10
    then
		DAY="${DATE}-0$DD"
    else
		DAY="${DATE}-$DD"
    fi
	FILE=SLSTR_mosaic/${DATE:0:4}${DATE:5:5}${DAY:8:7}/summary_cloud.tif

	if [ -f ${FILE} ]; then
		echo "${FILE} already exists. Skipping."
		continue
	else
		echo "    Mosaicing."
		bash ./dm.sh ${DATE:0:4}${DATE:5:5}${DAY:8:7} SLSTR_scenes/$DAY SLSTR_mosaic/
	fi
done

FOLDER="SLSTR_mosaic"
rm -r result.tif
for D in `find ${FOLDER} -type d`
do
	echo $D
	gdal_calc.py -A ${D}/summary_cloud.tif -B mask.tif --A_band=1 --B_band=1 --outfile=result.tif --calc="A-(B==255)*999" 
	FILEOUT="${D}/summary_cloud.jpeg"
	echo "${D}/summary_cloud.tif"
	echo "$FILEOUT"
	gdaldem color-relief result.tif  col.txt $FILEOUT -of JPEG -s 0.05
	rm -r result.tif
done

	end=`date +%s`
	echo Execution time was `expr $end - $start` seconds.
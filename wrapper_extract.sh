#!/usr/bin/env bash
start=`date +%s`

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./wrapper_mosaic.sh --date [YYYY-MM] -X xml-file"
	    exit 1
	    ;;
	-d|--date)
	    DATE="$2"
	    shift # past argument
	    shift # past value	
		;;
	-X)
	    XMLFILE="$2"
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
	bash ./S3_proc.sh -i ${DATE}/$DAY -o  SLSTR_scenes/$DAY -X $XMLFILE
	# echo #bash ./dm.sh ${DATE:0:4}${DATE:5:5}${DAY:8:7} SLSTR_scenes/$DAY SLSTR_mosaic/

done
	end=`date +%s`
	echo Execution time was `expr $end - $start` seconds.
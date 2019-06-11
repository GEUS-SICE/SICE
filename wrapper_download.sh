#!/usr/bin/env bash
start=`date +%s`
OUTFOLDER="."
while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./wrapper.sh --date [YYYY-MM] -n name-instrument [-o /path/to/output_folder]"
	    exit 1
	    ;;
	-d|--date)
	    DATE="$2"
	    shift # past argument
	    shift # past value	
		;;
	-n|--name-instrument)
	    NAMEINSTRUMENT="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-o|--output-folder)
	    OUTFOLDER="$2"
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
bash ./fetch_scene_from_date.sh --date $DAY -o ${OUTFOLDER}/${DATE}/$DAY -n $NAMEINSTRUMENT
done
	end=`date +%s`
	echo Execution time was `expr $end - $start` seconds.
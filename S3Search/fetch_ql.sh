#!/usr/bin/env bash

POSITIONAL=()
QLFOLDER="./quicklook"

# Current version of the script
export VERSION=1.2

# Help file called in terminal using -H flag
function print_help
{
	echo "-----------------------------------------------------------------------------------------------------------------"
 	echo "${bold}NAME${normal}"
 	echo " "
 	echo "  S3search $VERSION - The command line tool to search and download Sentinel 3 data from the Copernicus API"
 	echo " " 
  	echo "${bold}DESCRIPTION${normal}"
 	echo " "
 	echo "  This script allows to get quicklooks from Sentinel's S3 PreOPs Data Hub executing queries with different filters. "
	echo " The quicklook images are downloaded, and can later be used to retrieve the Sentinel 3 scenes."
 	echo " "
 	echo "${bold}OPTIONS"
	echo " "
	echo "  ${bold}SEARCH QUERY OPTIONS:${normal}"
	echo " "
	echo "   -i <instrument name>		: instrument name. Possible options are: OLCI, SLSTR, SRAL."
	echo ""
 	echo "   -o <orbit direction>		: orbit direction. Possible options are: descending, ascending (descending by default)."
	echo ""
	echo "   -s <start date>		: Search for products with sensing date ${bold}greater than${normal} the date and time specified by <start date>. The date format is YYYY-MM-DD"
 	echo ""
	echo "   -e <end date>		: Search for products with sensing date ${bold}smaller than${normal} the date and time specified by <end date>. The date format is YYYY-MM-DD"
 	echo ""
	echo "   -f <lat,lon>	                : Area of Interest. The images intersecting the point in lat, lon coordinates."
	echo ""
	echo "  ${bold}DOWNLOAD OPTIONS:${normal}"
 	echo " "
	echo "   -q <quicklook folder> 	:  Path to the quicklook folder"
 	echo ""
 	echo ""

	exit 0
}


while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|-H|--help)
	    print_help $0
	    echo "./fetch_ql --date [YYYY-MM-DD | YYYY-DOY] [-f lat,lon] [-q /path/to/ql_folder]"
	    echo "  [-f default: Greenland]"
	    echo "  [-q default: ./quicklook]"
	    exit 1
	    ;;
	-i|--instrument)
		INSTRUMENT="$2"
		shift
		shift
		;;
	-o|--orbit)
		ORBIT="$2"
		shift
		shift
		;;
	-s|--startdate)
	    START_DATE="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-e|--enddate)
	    END_DATE="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-f|--footprint)
	    FOOTPRINT="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-q|--quicklook-folder)
	    QLFOLDER="$2"
	    shift # past argument
	    shift # past value
	    ;;
	--debug)
	    DEBUG=1
	    shift
	    ;;
	*)    # unknown option
	    POSITIONAL+=("$1") # save it in an array for later
	    shift # past argument
	    ;;
    esac
done
set -- "${POSITIONAL[@]}" # restore positional parameters

BASE="https://scihub.copernicus.eu/s3/search?start=0&rows=100&q="
MISSION="platformname:Sentinel-3"
FILENAME="filename:*EFR*"

# Defaults
USER=s3guest
PASS=s3guest

# Check instrument
if [ -z $INSTRUMENT ]; then
	echo "--instrument not set"
	echo " "
	$0 -h
	exit 1
else
	INST="instrumentshortname:${INSTRUMENT}"
fi

# Check orbit
if [ -z $ORBIT ]; then
	echo "Default orbit: descending"
	echo " "
	MISC="orbitdirection:descending"
else
	MISC="orbitdirection:${ORBIT}"
fi


# Check search dates
if [ -z $START_DATE ] && [ -z $END_DATE ];then
	echo "'-s -e options' not specified. No search date provided... searching from the beginning of time to now."
	echo ""
	export START_DATE='NOW'
	export END_DATE='NOW'
	export DATESTR="beginposition:[${START_DATE} TO ${END_DATE}]"
	
elif [ ! -z $START_DATE ] && [ -z $END_DATE ];then 
	echo "'-e option' not specified. No end date: searching from $START_DATE to now."
	echo ""
	export END_DATE='NOW'
	export DATESTR="beginposition:[${START_DATE}T00:00:01.000Z TO ${END_DATE}]"

elif [ -z $START_DATE ] && [ ! -z $END_DATE ];then 
	echo "'-s option' not specified. No start date: searching from beginning of time to $END_DATE"
	echo ""	
	export START_DATE='NOW'
	export DATESTR="beginposition:[${START_DATE} TO ${END_DATE}T23:59:59.000Z]"

else
	echo "Searching from $START_DATE to $END_DATE"
	echo ""	
	export DATESTR="beginposition:[${START_DATE}T00:00:01.000Z TO ${END_DATE}T23:59:59.000Z]"
fi

if [ -z $FOOTPRINT ]; then
    echo "--footprint not set"
    echo "SEARCHING ALL OF GREENLAND"
    FOOTPRINT="footprint:\"Intersects(POLYGON((-34.51 84.29,-74.49 78.23,-69.47 75.76,-59.76 75.46,-53.76 65.40,-48.64 60.25,-42.62 59.36,-41.47 62.37,-21.22 69.77,-8.74 81.43,-34.51 84.29)))\""
elif [[ $FOOTPRINT =~ ^[-+]?[0-9]*\.?[0-9]+,([-+]?[0-9]*\.?[0-9]+)$ ]]; then
    arr=(${FOOTPRINT//,/ })
    x1=${arr[0]}
    x2=${arr[1]}
    FOOTPRINT=$(printf "footprint:\"Intersects(%s, %s)\"" $x1 $x2)			
else
    echo "Wrong footprint format!"
    echo " "
    $0 -h
    exit 1
fi

# Build search expression
export QUERY="$BASE$MISSION AND $FILENAME AND $INST AND $DATESTR AND $FOOTPRINT AND $MISC"

wget --no-check-certificate --user="$USER" --password="$PASS" --output-document=query_results.xml "$QUERY"

# Print human readable results to screen and save the list of images and their id to a file in the script directory
N=$(grep "total results." query_results.xml)
if [[ $N != "" ]]; then
    echo "More than 100 results. Use a smaller date range"
    exit 1
fi

# filename and ID, then merge
grep -n "<title>" query_results.xml | tail -n +2 | cut -d'>' -f2- | cut -d'<' -f1 > tmp.filename.txt
grep -n "<id>" query_results.xml |  tail -n +2  | cut -f2 -d'>'| cut -f1 -d'<' > tmp.id.txt
paste -d" " tmp.filename.txt tmp.id.txt > product_IDs.txt
rm tmp.filename.txt tmp.id.txt

# Find unique filenames based on collection time. For the first of each one, download a QL image
mkdir -p $QLFOLDER
for uniq_dts in $(cut -c1-31 product_IDs.txt | sort | uniq); do
    # first of the unique filenames
    filename=$(grep ${uniq_dts} product_IDs.txt | head -n1 | cut -d" " -f1)
    filename_clean=$(echo $filename | cut -c17-31)
    # first of the quicklook IDs
    ql_id=$(grep ${uniq_dts} product_IDs.txt | head -n1 | cut -d" " -f2)
    URL="https://scihub.copernicus.eu/s3/odata/v1/Products('${ql_id}')/Products('Quicklook')/\$value"
    
    wget "${URL}" --user=s3guest --password=s3guest -nc -c -nd -P ${QLFOLDER} -O ${QLFOLDER}/${filename_clean}_${ql_id}.jpg
done

if [[ -z $DEBUG ]]; then
    rm product_IDs.txt
    rm query_results.xml
fi


#!/usr/bin/env bash

POSITIONAL=()
QLFOLDER="./quicklook"

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./fetch_ql --date [YYYY-MM-DD | YYYY-DOY] [-f lat,lon] [-q /path/to/ql_folder]"
	    echo "  [-f default: Greenland]"
	    echo "  [-q default: ./quicklook]"
	    exit 1
	    ;;
	-d|--date)
	    DATE="$2"
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

# Defaults
USER=s3guest
PASS=s3guest

BASE="https://scihub.copernicus.eu/s3/search?start=0&rows=100&q="

MISSION="platformname:Sentinel-3"
INSTRUMENT="instrumentshortname:OLCI"
FILENAME="filename:*EFR*"
MISC="orbitdirection:descending"

# Check search dates
if [ -z $DATE ]; then
    echo "--date not set"
    echo " "
    $0 -h
    exit 1
else
    if [[ $DATE =~ 20[1,2][0-9]-[0-9][0-9]?[0-9]?$ ]]; then
	YEAR=$(echo $DATE | cut -d"-" -f1)
	DOY=$(echo $DATE | cut -d"-" -f2)
	DOY=$(($DOY-1))
	DATE=$(gdate -d "${YEAR}-01-01 +${DOY} days" "+%Y-%m-%d")
	DATESTR="beginposition:[${DATE}T00:00:01.000Z TO ${DATE}T23:59:59.000Z]"
    else
	DATESTR="beginposition:[${DATE}T00:00:01.000Z TO ${DATE}T23:59:59.000Z]"
    fi
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
export QUERY="$BASE$MISSION AND $FILENAME AND  $INSTRUMENT AND $DATESTR AND $FOOTPRINT AND $MISC"

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

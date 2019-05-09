#!/usr/bin/env bash
timing() { if [[ $TIMING == 1 ]]; then MSG_OK "$(date)"; fi; }
start=`date +%s`

RED='\033[0;31m'
ORANGE='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
MSG_OK() { printf "${GREEN}${1}${NC}\n"; }
MSG_WARN() { printf "${ORANGE}WARNING: ${1}${NC}\n"; }
MSG_ERR() { printf "${RED}ERROR: ${1}${NC}\n"; }

POSITIONAL=()
OUTFOLDER="./S3_scenes"
NAMEINSTRUMENT="OLCI"

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./fetch_scene_from_date.sh --date [YYYY-MM-DD | YYYY-DOY] [-f lat,lon] [-o /path/to/output_folder] [-n name_instrument] "
	    echo "  [-f default: Greenland]"
	    echo "  [-q default: ./S3_scenes]"
	    echo "  [-n OLCI or SLSTR default: OLCI]"
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
	-o|--output-folder)
	    OUTFOLDER="$2"
	    shift # past argument
	    shift # past value
	    ;;
	
	-n|--name-instrument)
	    NAMEINSTRUMENT="$2"
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
INSTRUMENT="instrumentshortname:$NAMEINSTRUMENT"

if test "$NAMEINSTRUMENT" = "OLCI"; then
    FILENAME="filename:*EFR*"
else
    FILENAME="filename:*RBT*"
fi    
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
    FOOTPRINT="footprint:\"Intersects(POLYGON((-53.656510998614 82.4951349654326,-59.9608997952054 82.1309669419302,-67.7892790605668 80.5602726884285,-67.9606014394374 80.0218479599442,-67.6072679271745 79.3014049647312,-72.7375435732184 78.589499923855,-73.5413877637147 78.1636943551527,-72.9428482239824 77.383771707567,-69.0700767925261 76.0128312085861,-66.6509837672326 75.7624371858398,-60.3956740146368 75.8231961720352,-58.4311886831941 74.885454496734,-55.1967975793182 69.6980961092145,-53.856542195614 68.836827126205,-54.2986423614971 67.0754091899264,-53.556230345375 65.610957996411,-52.3863139424116 64.7989541895734,-52.3228757389159 64.0074120108603,-50.207636158087 62.10102160819,-48.6300832525784 60.7381422112742,-45.052233335019 59.7674821385312,-43.2890274040171 59.6436933230826,-42.4957557404764 60.3093279369714,-41.8486807919329 61.5655162642218,-41.696971498891 62.648646023379,-40.1106185043429 63.5452982243944,-39.9111533763437 64.794417571311,-38.0777963367496 65.4068477012585,-36.9899016468925 65.1987069880844,-31.2165494022336 67.7166128864512,-25.8502840866575 68.6303659153185,-21.6517276244872 70.0839769825896,-20.9932063064242 70.7880484213637,-21.2829833867197 72.9254092162205,-16.9050363384979 74.9601702268335,-17.1213527989912 79.6158229046929,-10.2883304040514 81.4244115757783,-14.0398740460794 81.9745362690188,-17.8112945221629 82.0131368667592,-28.5252333238728 83.7013945514435,-40.1075150451371 83.6651081451092,-53.656510998614 82.4951349654326)))\""
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
mkdir -p $OUTFOLDER
for entry in $(cut -c1-31 product_IDs.txt | sort); do
	echo " "
	echo ${entry}
    echo " "
	# first of the unique filenames
    filename=$(grep ${entry} product_IDs.txt | head -n1 | cut -d" " -f1)
    filename_clean=$(echo $filename | cut -c17-31)
    # first of the quicklook IDs
    id=$(grep ${entry} product_IDs.txt | head -n1 | cut -d" " -f2)
    
    PRODUCTURL="https://scihub.copernicus.eu/s3/odata/v1/Products('${id}')/"
    # wget "${PRODUCTURL}" --user=s3guest --password=s3guest -nc -c -nd -O ${OUT}/${id}.xml
    curl --silent -u s3guest:s3guest -o ${OUTFOLDER}/${id}.xml "${PRODUCTURL}"
    PRODUCT_NAME=$(grep -o "<d:Name>.*" ${OUTFOLDER}/${id}.xml | cut -d">" -f2 | cut -d"<" -f1)
    rm ${OUTFOLDER}/${id}.xml

	echo " ################"
	echo ${OUTFOLDER}
	echo " ################ "

    # wget "${PRODUCTURL}\$value" --user=s3guest --password=s3guest -nc -O ${OUT}/${PRODUCT_NAME}.zip    #--continue
    if [[ -d ${OUTFOLDER}/${PRODUCT_NAME}.SEN3 ]]; then
	MSG_WARN "Skipping: ${PRODUCT_NAME}"
    else	
	MSG_OK "Fetching: ${PRODUCT_NAME}"
	curl -o ${OUTFOLDER}/${PRODUCT_NAME}.zip -u s3guest:s3guest "${PRODUCTURL}\$value"
	(cd ${OUTFOLDER}; unzip ${PRODUCT_NAME}.zip)
	rm ${OUTFOLDER}/${PRODUCT_NAME}.zip
    fi
done

if [[ -z $DEBUG ]]; then
    rm product_IDs.txt
    rm query_results.xml
fi
	end=`date +%s`
	echo Execution time was `expr $end - $start` seconds.

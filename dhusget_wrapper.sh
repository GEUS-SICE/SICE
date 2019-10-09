#!/usr/bin/env bash

RED='\033[0;31m'
ORANGE='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
MSG_OK() { echo -e "${GREEN}${@}${NC}"; }
MSG_WARN() { echo -e "${ORANGE}WARNING: ${@}${NC}"; }
MSG_ERR() { echo -e "${RED}ERROR: ${@}${NC}"; }

# Documnet usage options
function print_usage() {
    echo "./dhusget_wrapper.sh -u <username> -p <password> -d [YYYY-MM-DD | YYYY-DOY] -o <output_folder> [-f <footprint>] [--l <SEN3 folder locations>] [dhusget.sh options]"
    echo ""
    echo "  [-u|--user SciHub Username]"
    echo "  [-p|--password SciHub Password]"
    echo "  [-d|--date YYYY-MM-DD or YYY-DOY]"
    echo "  [-o|--output-folder /path/to/folder]"
    echo "  [-f|--footprint Greenland|Iceland|<footprint code> [DEFAULT: Greenland]]"
    echo "  [-l|--local /path/for/local/SEN3 folders (e.g. /o3data/Sentinel-3)]"
}


function DEBUG() { 
    if [[ $DEBUG == 1 ]]; then
	MSG_WARN "DEBUG:"
	echo $@
    fi;
}

# Parse input arguments
POSITIONAL=()
while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    print_usage
	    exit 1
	    ;;
	-u|--user)
	    USERNAME="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-p|--password)
	    PASSWORD="$2"
	    shift; shift;;
	-d|--date)
	    DATE="$2"
	    shift; shift;;
	-f|--footprint)
	    FOOTPRINT="$2"
	    shift; shift;;
	-l|--local)
	    LOCALFILES="$2"
	    shift; shift;;
	-o|--output-folder)
	    OUTFOLDER="$2"
	    shift; shift;;
	--debug)
	    DEBUG=1
	    shift;;
	--verbose)
	    set -x
	    shift;;
	*)    # unknown option
	    POSITIONAL+=("$1") # save it in an array for later. Pass on to dhusget.sh
	    shift;;
    esac
done
set -- "${POSITIONAL[@]}" # restore positional parameters


# check inputs
if [ -z $DATE ]; then MSG_ERR "--date not set"; print_usage; exit 1; fi
if [ -z $OUTFOLDER ]; then MSG_ERR "--output-folder not set"; print_usage; exit 1; fi
if [ -z $FOOTPRINT ]; then 
    FOOTPRINT=Greenland; MSG_WARN "Footprint not set. Setting to Greenland"
else
    MSG_WARN "Footprint set to ${FOOTPRINT}"
fi

# process arguments
if [[ $DATE =~ 20[1,2][0-9]-[0-9][0-9]?[0-9]?$ ]]; then
    YEAR=$(echo $DATE | cut -d"-" -f1)
    DOY=$(echo $DATE | cut -d"-" -f2)
    DOY=$(($DOY-1))
    DATE=$(gdate -d "${YEAR}-01-01 +${DOY} days" "+%Y-%m-%d")
fi
DATESTR0="${DATE}T00:00:00.0000Z"
DATESTR1="${DATE}T23:59:59.9999Z"
DEBUG "Date search from: ${DATESTR0} to ${DATESTR1}"

if [[ ${FOOTPRINT} == "Greenland" ]]; then
    FOOTPRINT="footprint:\"Intersects(POLYGON((-53.6565 82.4951,-59.9608 82.1309,-67.7892 80.5602,-67.9606 80.0218,-67.6072 79.3014,-72.7375 78.5894,-73.5413 78.1636,-72.9428 77.3837,-69.0700 76.0128,-66.6509 75.7624,-60.3956 75.8231,-58.4311 74.8854,-55.1967 69.6980,-53.8565 68.8368,-54.2986 67.0754,-53.5562 65.6109,-52.3863 64.7989,-52.3228 64.0074,-50.2076 62.1010,-48.6300 60.7381,-45.0522 59.7674,-43.2890 59.6436,-42.4957 60.3093,-41.8486 61.5655,-41.6969 62.6486,-40.1106 63.5452,-39.9111 64.7944,-38.0777 65.4068,-36.9899 65.1987,-31.2165 67.7166,-25.8502 68.6303,-21.6517 70.0839,-20.9932 70.7880,-21.2829 72.9254,-16.9050 74.9601,-17.1213 79.6158,-10.2883 81.4244,-14.0398 81.9745,-17.8112 82.0131,-28.5252 83.7013,-40.1075 83.6651,-53.6565 82.4951)))\""
elif [[ ${FOOTPRINT} == "DEBUG" ]]; then
    FOOTPRINT="footprint:\"Intersects(POLYGON((-45 63,-45 64,-44 64,-44 63,-45 63)))\""
elif [[ ${FOOTPRINT} == "Iceland" ]]; then
    MSG_ERR "Not yet implemented"
    exit 1
elif [[ ${FOOTPRINT} == "Svalbard" ]]; then
    MSG_ERR "Not yet implemented"
    exit 1
fi
DEBUG "Footprint: ${FOOTPRINT}"



MSG_OK "***********************************************************"
MSG_OK "***                                                     ***"
MSG_OK "***               DHUSGET.SH begin                      ***"
MSG_OK "***                                                     ***"
MSG_OK "***********************************************************"
# Get the list of file names and product UUIDs
# Could download (with "-o" and maybe "-D -O outfolder"), but what if we have them already?
# For now, just get file list. We'll check if we have them and download missing files below.
./dhusget.sh $@ -u ${USERNAME} -p ${PASSWORD} -m Sentinel-3 -i OLCI -S ${DATESTR0} -E ${DATESTR1} -l 100 -F 'filename:*EFR* AND orbitdirection:descending AND ( '"${FOOTPRINT}"' )'
MSG_OK "***********************************************************"
MSG_OK "***                                                     ***"
MSG_OK "***                DHUSGET.SH end                       ***"
MSG_OK "***                                                     ***"
MSG_OK "***********************************************************"


# If no local file path provided, then we download.
mkdir -p ${OUTFOLDER}
if [[ -z ${LOCALFILES} ]]; then
    # find files in products-list.csv that are not already in ${OUTFOLDER}
    for LINE in $(cat products-list.csv); do
	UUID=$(echo ${LINE} | cut -d"'" -f2)
	FILENAME=$(echo ${LINE} | cut -d"," -f1)
	if [[ -d ${OUTFOLDER}/${FILENAME}.SEN3 ]]; then
	    MSG_WARN "${OUTFOLDER}/${FILENAME}.SEN3 already exists. No Download"
	    continue
	fi
	MSG_OK "Downloading ${FILENAME}..."
	# From https://scihub.copernicus.eu/userguide/BatchScripting
	wget --content-disposition -nc --continue --user=${USERNAME} --password=${PASSWORD} "https://scihub.copernicus.eu/dhus/odata/v1/Products('${UUID}')/\$value" -O ${OUTFOLDER}/${FILENAME}.zip
	(cd ${OUTFOLDER}; unzip ${FILENAME}.zip; rm ${FILENAME}.zip)
    done
else
    # Source for SEN3 is a locally mounted path.
    
    # rather than downloading, use the products-list.csv from the
    # dhusget.sh command and search for the files at the provided.
    MSG_OK "Linking local files into ${OUTFOLDER}"
    mkdir -p ${OUTFOLDER}
    for PRODUCT in $(cut -d, -f1 products-list.csv); do
    	SEARCH=$(find "${LOCALFILES}" -type d -name "${PRODUCT}*")
     	MSG_OK "Linking to ${SEARCH}"
     	ln -s ${SEARCH} ${OUTFOLDER}/${PRODUCT}
    done
fi

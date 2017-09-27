
#!/bin/bash
# Simple batch script to search and download Sentinel 3 images

#---------------------------------------------------------------

# Current version of the script
export VERSION=1.1

# Print script name when called
print_script=`echo "$0" | rev | cut -d'/' -f1 | rev`

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
 	echo "  This script allows to get products from Sentinel's S3 PreOPs Data Hub executing queries with different filters. "
	echo " The products can be visualized on shell and are saved in a list file or downloaded in a zip file."
 	echo " "
 	echo "${bold}OPTIONS"
 	echo " "
 	echo "  ${bold}LOGIN OPTIONS:${normal}"
 	echo " "
 	echo "   -u <username>		: data hub username (default 's3guest');"
 	echo "   -p <password>		: data hub password (default 's3guest');"
	echo " "
	echo "  ${bold}SEARCH QUERY OPTIONS:${normal}"
	echo " "
	echo "   -i <instrument name>		: instrument name. Possible options are: OLCI, SLSTR, SRAL."
	echo ""
 	echo "   -s <start date>		: Search for products with sensing date ${bold}greater than${normal} the date and time specified by <start date>. The date format is YYYY-MM-DD"
 	echo ""
	echo "   -e <end date>		: Search for products with sensing date ${bold}smaller than${normal} the date and time specified by <end date>. The date format is YYYY-MM-DD"
 	echo ""
	echo "   -f <lat_min:lon_min[:lat_max:lon_max]>	: Area of Interest. The images intersecting the point (if one lat:lon pair provided) or bounding box (if two pair) defined by the minimum and maximum longitude and latitude will be queried. Coordinates are in decimal degrees, with the follwing syntax: lat_min:lon_min[:lat_max:lon_max]. I.e. 66:45 is a point in Greenland, and 45.153:5.682:45.218:5.778 is a region covering Grenoble."
	echo ""
	echo "  ${bold}DOWNLOAD OPTIONS:${normal}"
 	echo " "
	echo "   -D 				: If the -D flag is set, the listed products will be downloaded. If not, the script will only list the products."
 	echo ""
 	echo "   -o <output folder>		: Specify the folder to which the downloaded products will be saved."
 	echo ""

	exit 0
}

# Define options

while getopts ":s:e:i:o:f:p:u:HD" option; do
	case "${option}" in
 		
		s) 
 			export START_DATE=${OPTARG};;
		u)
			export USERN=${OPTARG};;
		p)
			export PASSWD=${OPTARG};;
 		e) 
 			export END_DATE=${OPTARG};;
 		i) 
 			export INSTRUMENT=${OPTARG};;
 		f) 
 			export FOOTPRINT=${OPTARG};;

 		o)
			export OUTPUT=${OPTARG};;
		H)
			print_help $0
			exit 0
			;;
		D)
			export DOWN=1;;
 
 	esac
done

# Declare variables for search URI
export BASE="https://scihub.copernicus.eu/s3/search?start=0&rows=100&q="
export MISSION="platformname:'Sentinel-3' "


# Print header

echo ""
echo "================================================================================================================" 
echo ""
echo "S3search version: $VERSION"
echo "written by M. Lamare"
echo ""
echo "Type ' $print_script -H' for usage information"
echo ""
echo "================================================================================================================" 



## Check the options

# Check instrument name
if [ -z $INSTRUMENT ]; then
	echo "Instrument '-i option' not specified. Searching all Sentinel 3 instruments."
        echo ""
else
	case "$INSTRUMENT" in
	OLCI|SLSTR|SRAL)
		echo "Instrument is set to $INSTRUMENT."

		# OLCI EFR only
		if [ $INSTRUMENT = "OLCI" ];then
			export OLCITYPE=" AND filename:*FR*"
		else
			export OLCITYPE=""
		fi

		echo ""
		export INST_STR=" AND instrumentshortname:$INSTRUMENT"
		;;
	*)
		echo "Fail: Wrong Sentinel 3 instrument... choose OLCI, SLSTR or SRAL" 
		exit 1
		;;
	esac        
fi


# Check passwords

if [ -z $USERN ] && [ -z $PASSWD ];then
	echo "'-u -p options' not specified. Trying with default login creds. Your fault if it doesn't work!"
	echo ""
	export USERN='s3guest'
	export PASSWD='s3guest'
	
elif [ ! -z $USERN ] && [ -z $PASSWD ];then 
	echo "'-p option' not specified. No password. Fail!"
	exit 1

elif [ -z $USERN ] && [ ! -z $PASSWD ];then 
	echo "'-u option' not specified. No username. Fail!"
	exit 1

else
	echo "Username and password provided. Thanks!"
	echo ""	
fi



# Check search dates
if [ -z $START_DATE ] && [ -z $END_DATE ];then
	echo "'-s -e options' not specified. No search date provided... seaching from the beginning of time to now."
	echo ""
	export START_DATE='NOW'
	export END_DATE='NOW'
	export DATE_STR=" AND beginposition:[$START_DATE TO $END_DATE]"
	
elif [ ! -z $START_DATE ] && [ -z $END_DATE ];then 
	echo "'-e option' not specified. No end date: serching from $START_DATE to now."
	echo ""
	START_DATE+='T00:00:00.000Z'
	export END_DATE='NOW'
	export DATE_STR=" AND beginposition:[$START_DATE TO $END_DATE]"

elif [ -z $START_DATE ] && [ ! -z $END_DATE ];then 
	echo "'-s option' not specified. No start date: searching from beginning of time to $END_DATE"
	echo ""	
	END_DATE+='T00:00:00.000Z'
	export START_DATE='NOW'
	export DATE_STR=" AND beginposition:[$START_DATE TO $END_DATE]"

else
	echo "Searching from $START_DATE to $END_DATE"
	echo ""	
	START_DATE+='T00:00:00.000Z'
	END_DATE+='T00:00:00.000Z'
	export DATE_STR=" AND beginposition:[$START_DATE TO $END_DATE]"
fi

# Check footprint
if [ -z $FOOTPRINT ]; then
	echo "'-f option' not specified. No specified Area of Interest. Search is performed on the whole globe."
        echo ""
else
	if [[ $FOOTPRINT =~ ^[-+]?[0-9]*\.?[0-9]+:([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+):([-+]?[0-9]*\.?[0-9]+)$ ]]; then
		# Extract footprint parts
		# 1st = x1 = Lat min
		# 2nd = x2 = Lon min
		# 3rd = x3 = Lat max
		# 4th = x4 = Lon max
		arr=(${FOOTPRINT//:/ })
		x1=${arr[0]}
		x2=${arr[1]}
		x3=${arr[2]}
		x4=${arr[3]}   
		export FOOTPRINT_STR=$(printf " AND footprint:\"Intersects(POLYGON((%s %s,%s %s,%s %s,%s %s,%s %s)))\"" $x1 $x2 $x3 $x2 $x3 $x4 $x1 $x4 $x1 $x2)			
		echo "Search is performed on an AOI defined as a bounding box delimited by: Lat_min: $x1, Lon_min: $x2, Lat_max: $x3, Lon_max: $x4 "
        	echo ""
	elif [[ $FOOTPRINT =~ ^[-+]?[0-9]*\.?[0-9]+:([-+]?[0-9]*\.?[0-9]+)$ ]]; then
		arr=(${FOOTPRINT//:/ })
		x1=${arr[0]}
		x2=${arr[1]}
		export FOOTPRINT_STR=$(printf " AND footprint:\"Intersects(%s, %s)\"" $x1 $x2)			
		echo "Search is performed on an AOI defined as a point defined by: Lat: $x1, Lon: $x2"
	    
	else
		echo "Wrong footprint format! Please type 'lat_min:lon_min:lat_max:lon_max' in decimal degrees."
		exit 1
	fi
fi

# Build search expression
export QUERY="$BASE$MISSION$OLCITYPE$INST_STR$DATE_STR$FOOTPRINT_STR"


# Remove query file if existing
[ -e query_results.xml ] && rm query_results.xml
[ -e pdoruct_IDs.txt ] && rm product_IDs.txt

# Search API
wget --no-check-certificate --user="$USERN" --password="$PASSWD" --output-document=query_results.xml "$QUERY"

# Print human readable results to screen and save the list of images and their id to a file in the script directory
grep -n "<subtitle>" query_results.xml | cut -f2 -d'>' | cut -f1 -d'<' 
echo ""
grep -n "<title>" query_results.xml | tail -n +2 | cut -f2 -d'>' | cut -f1 -d'<' > fln.txt
grep -n "<id>" query_results.xml | tail -n +2 | cut -f2 -d'>'| cut -f1 -d'<' > idn.txt
paste fln.txt idn.txt > product_IDs.txt
rm fln.txt idn.txt
echo ""
echo "File name / file ID:"
cat product_IDs.txt
echo ""

# Check the number of query results
number=$(grep -n "<subtitle>" query_results.xml | cut -c2- | rev | cut -c25- | rev| tr -dc '0-9')
if [ "$number" -gt 100 ];then
	echo "More than 100 results. Only first 100 will be downloaded. Consider restricting your research parameters!"
	echo ""
fi



# Download options
if [ ! -z $DOWN ]; then
	# Download products using wget
	echo "Downloading all listed products"

	# Check the output directory
	if [ ! -z $OUTPUT ]; then
		echo "Saving to directory \"$OUTPUT\" "
	else
		OUTPUT=$(pwd)
		echo "Saving to directory \"$OUTPUT\" "
	fi

	cat names.txt | while read line; do
		read -a arr <<< $line	
		wget --no-check-certificate --user="$USERN" -R index.html -e robots=off -O "$OUTPUT/${arr[0]}.zip"\
		-U Mozilla --continue --password="$PASSWD" "https://scihub.copernicus.eu/s3/odata/v1/Products('${arr[1]}')/\$value"
	done
fi

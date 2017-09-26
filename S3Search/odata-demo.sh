#!/bin/bash
#------------------------------------------------------------------------------#
# Demo script illustrating some examples using the OData interface             #
# of the Data Hub Service (DHuS)                                               #
#------------------------------------------------------------------------------#
# GAEL Systems 2014                                                            #
#------------------------------------------------------------------------------#
# Change log                                                                   #
# 2014-11-07  v1.0  First version listing collections, products, matching name #
#                   or ingestion date. Download of the Manifest file.          #
# 2014-11-11  v1.1  Add search by AOI, product type and last <n> days. Get     #
#                   Polarisation & relative orbit values, Download quick-look  #
#                   or full product.                                           #
# 2014-11-18  v1.2  Add case listing products from specific acquisition date   #
#                   Date operations are now forced in UTC                      #
#                   Date operations supporting both Linux and Max OSX syntax   #
#                   -V command line option added to display script version     #
#------------------------------------------------------------------------------#

# Define default options and variables
VERSION="1.2"
DHUS_SERVER_URL="https://scihub.esa.int/dhus"
DHUS_USER="username"
DHUS_PASSWD="password"
JSON_OPT=false
VERBOSE=false
RESULT_LIST=""

# Display help
function show_help()
{
   echo "USAGE: odata-demo.sh [OPTIONS]... "
   echo "This script illustrates sample scenarios using the OData inteface of the Data Hub Service (DHuS)."
   echo "OPTIONS are:"
   echo "  -h, --help                 display this help message"
   echo "  -j, --json                 use json output format for OData (default is xml)"
   echo "  -p, --password=PASSWORD      use PASSWORD as password for the Data Hub"
   echo "  -s, --server=SERVER        use SERVER as URL of the Data Hub Server"
   echo "  -u, --user=NAME            use NAME as username for the Data Hub"
   echo "  -v, --verbose              display curl command lines and results"
   echo "  -V, --version              display the current version of the script"
}

# Display version
function show_version()
{
   echo "odata-demo.sh $VERSION"
}

# Display a banner with the passed text (limited to 20 lines)
function show_text()
{
   echo "--------------------------------------------------"
   echo "$1" | head -20
   [ $(echo "$1" | wc -l) -gt 20 ] && echo "[Truncated to 20 lines]..."
   echo "--------------------------------------------------"
}

# Return list of values for the passed field name from the result file depending on its json or xml format
function get_field_values()
{
   field_name="$1"
   if [ "$USE_JQ" = "true" ]
   then
      RESULT_LIST=$(jq ".d.results[].$field_name" "$OUT_FILE" | tr -d '"')
   else
      RESULT_LIST=$(cat "$OUT_FILE" | xmlstarlet sel -T -t -m "//*[local-name()='entry']//*[local-name()='$field_name']" -v '.' -n)
   fi
}

# Display numbered list of items from a multiple lines variable
function show_numbered_list()
{
   # Get number of items in the list
   LIST="$1"
   if [ ! "$LIST" ]
   then
      nb_items=0
      echo "Result list is empty."
      return
   fi
   # Loop on list and add number as prefix
   nb_items=$(echo "$LIST" | wc -l | tr -d ' ')
   echo "Result list has $nb_items item(s):"
   OLD_IFS=$IFS
   IFS=$'\n'
   i=0
   for item in $LIST
   do
      i=$(expr $i + 1)
      echo "   $i. $item"
   done
   IFS=$OLD_IFS
}

# Query the server and return json or xml output, with optional verbose mode
# Args are URL JSON_FILTER XML_FILTER
function query_server()
{
   # Get URL and filter space characters
   URL="${1// /%20}"

   # Version using JSON output and jq parsing
   if [ "$USE_JQ" = "true" ]
   then
      # Add "?" to URL if not yet present, or "&" with json format option
      if (echo $URL | grep "?" > /dev/null)
      then URL="${URL}&\$format=json"
      else URL="${URL}?\$format=json"
      fi
      [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX \"$URL\""
      $CURL_PREFIX "$URL" > "$OUT_FILE"
      [ "$VERBOSE" = "true" ] && show_text "$(jq "." "$OUT_FILE")"

   # Version using XML output and xmlstarlet parsing
   else
      [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX \"$URL\""
      $CURL_PREFIX "$URL" > "$OUT_FILE"
      [ "$VERBOSE" = "true" ] && show_text "$(xmlstarlet fo "$OUT_FILE")"
   fi
}

# Parse command line arguments
for arg in "$@"
do
   case "$arg" in
      -h   | --help)       show_help; exit 0 ;;
      -j   | --json)       JSON_OPT=true ;;
      -p=* | --password=*) DHUS_PASSWD="${arg#*=}" ;;
      -s=* | --server=*)   DHUS_SERVER_URL="${arg#*=}" ;;
      -u=* | --user=*)     DHUS_USER="${arg#*=}" ;;
      -v   | --verbose)    VERBOSE=true ;;
      -V   | --version)    show_version; exit 0 ;;
      *) echo "Invalid option: $arg" >&2; show_help; exit 1 ;;
   esac
done

# Set variables depending to optional command line arguments
ROOT_URL_ODATA="$DHUS_SERVER_URL/odata/v1"
ROOT_URL_SEARCH="$DHUS_SERVER_URL/search"
CURL_PREFIX="curl -gu $DHUS_USER:$DHUS_PASSWD"

# Check if needed commands are present (date (differs on Linux and OSX), curl, then jq or xmlstarlet)
USE_JQ=false
USE_XMLST=false
USE_DATEV=false
if $(date -v-1d &> /dev/null)
then USE_DATEV=true
fi
if ! $(type curl &> /dev/null)
then echo "Command \"curl\" is missing, please install it first!"; exit 1
fi
if [ "$JSON_OPT" = "true" ]
then
   if ! $(type jq &> /dev/null)
   then echo "Command \"jq\" is missing, please install it first!"; exit 1
   fi
   USE_JQ=true
   OUT_FILE="/tmp/result.json"
else
   if ! $(type xmlstarlet &> /dev/null)
   then echo "Command \"xmlstarlet\" is missing, please install it first!"; exit 1
   fi
   OUT_FILE="/tmp/result.xml"
fi

# Menu: Ask which scenario to start
while true
do
   echo ""
   echo "Choose a sample demo:"
   echo "   1. List the collections"
   echo "   2. List <n> products from a specified collection"
   echo "   3. List first 10 products matching part of product name"
   echo "   4. List first 10 products matching a specific ingestion date"
   echo "   5. List first 10 products matching a specific aquisition date"
   echo "   6. List first 10 products since last <n> days, by product type and intersecting an AOI"
   echo "   7. Get product id from product name"
   echo "   8. Get polarisation from a product id"
   echo "   9. Get relative orbit from a product id"
   echo "  10. Download Manifest file from a product id"
   echo "  11. Download quick-look from a product id"
   echo "  12. Download full product from its id"
   echo "   q. Quit"
   echo -n "Please enter the selected item number: "
   read answer
   case $answer in
      1) # List the collections
         # Build URL and query server to get result list
         query_server "${ROOT_URL_ODATA}/Collections"
         get_field_values "Name"
         # Display result list
         show_numbered_list "$RESULT_LIST"
         ;;

      2) # List <n> products from a specified collection
         # Ask for a collection name and filter potential quotes
         echo -n "Please enter the name of a collection (e.g. one from step 1., default=none): "
         read colname; colname=${colname//\"/}
         # Ask for top and skip limiters
         echo -n "How many products to list [1-n], default=10: "
         read nbtop; [ -z "$nbtop" ] && nbtop=10
         echo -n "Starting from [0-p], default=0: "
         read nbskip; [ -z "$nbskip" ] && nbskip=0
         # Build URL and query server to get result list
         if [ -z "$colname" ]
         then query_server "${ROOT_URL_ODATA}/Products?\$skip=$nbskip&\$top=$nbtop"
         else query_server "${ROOT_URL_ODATA}/Collections('$colname')/Products?\$skip=$nbskip&\$top=$nbtop"
         fi
         get_field_values "Name"
         # Display result list
         show_numbered_list "$RESULT_LIST"
         ;;

      3) # List first 10 products matching part of product name
         # Ask for a product name part and remove potential quotes
         echo -n "Please enter the name part to match (e.g. GRD, EW, 201410, default=SLC): "
         read namepart; namepart=${namepart//\"/}; [ -z "$namepart" ] && namepart="SLC"
         # Build URL and query server to get result list
         query_server "${ROOT_URL_ODATA}/Products?\$select=Id&\$filter=substringof('$namepart',Name)&\$top=10"
         get_field_values "Name"
         # Display result list
         show_numbered_list "$RESULT_LIST"
         ;;

      4) # List first 10 products matching a specific ingestion date
         # Ask for ingestion date, default is today
         echo -n "Please enter the ingestion date (YYYYMMDD format, default today=$(date -u +%Y%m%d)): "
         read idate; [ -z "$idate" ] && idate=$(date -u +%Y%m%d)
         year=${idate:0:4}
         month=${idate:4:2}
         day=${idate:6:2}
         # Build URL and query server to get result list
         query_server "${ROOT_URL_ODATA}/Products?\$filter=year(IngestionDate)+eq+$year+and+month(IngestionDate)+eq+$month+and+day(IngestionDate)+eq+$day&\$top=10"
         get_field_values "Name"
         # Display result list
         show_numbered_list "$RESULT_LIST"
         ;;

      5) # List first 10 products matching a specific aquisition date
         # Display a notice due to the current limitations
         echo "PLEASE NOTE: the current version is getting a list of 1000 products from the server and filters the results locally. Getting this list may take some time. Additional filter at server level will be available in future evolutions. Another way to do this is to use demo case 3. with the following date pattern YYYYMMDD, which is part of the product name."
         # Ask for acquisition date, default is yesterday, manage date command syntax for Linux or Mac OSX
         if [ "$USE_DATEV" = "true" ]
         then yesterday=$(date -u -v-1d +%Y%m%d)
         else yesterday=$(date -u -d 'yesterday' +%Y%m%d)
         fi
         echo -n "Please enter the acquisition date (YYYYMMDD format, default yesterday=$yesterday): "
         read acq_date; [ -z "$acq_date" ] && acq_date=$yesterday
         # Build URL and query server to get result list
         query_server "${ROOT_URL_ODATA}/Products?\$top=1000"
         if [ "$USE_DATEV" = "true" ]
         then
            millistart=$(date -u -j -f %Y%m%d-%H%M%S "$acq_date-000000" +%s000)
            millistop=$(expr $millistart \+ 86399999)
            acq_date2=$(date -u -j -f %Y%m%d "$acq_date" +%Y-%m-%d)
         else
            millistart=$(date -u -d "$acq_date" +%s000)
            millistop=$(date -u -d "$acq_date+1day-1sec" +%s999)
            acq_date2=$(date -u -d "$acq_date" +%Y-%m-%d)
         fi
         if [ "$USE_JQ" = "true" ]
         then
            RESULT_LIST=$(jq ".d.results | map(select(.ContentDate.Start >= \"/Date($millistart)/\" and .ContentDate.Start <= \"/Date($millistop)/\")) | .[].Name" "$OUT_FILE" | tr -d '"')
         else
            RESULT_LIST=$(xmlstarlet sel -T -t -m '//_:entry' -i "contains(.//d:ContentDate/d:Start/text(),\"$acq_date2\")" -c './_:title/text()' -n "$OUT_FILE")
         fi
         # Display result list
         show_numbered_list "$RESULT_LIST"
         ;;

      6) # List first 10 products since last <n> days, by product type and intersecting an AOI
         # Display a notice due to the current use of /search
         echo "PLEASE NOTE: the current syntax is using the /search api instead of pure OData. Additional functions including geographical search will be also available via the OData API in future evolutions."
         # Ask for the query parameters
         echo -n "Please enter the number of days from today (default=1): "
         read lastdays; [ -z "$lastdays" ] && lastdays=1
         echo -n "Please enter the selected product type (e.g. SLC, default=GRD): "
         read ptype; [ -z "$ptype" ] && ptype="GRD"
         polygon_default="POLYGON((-15.0 47.0,5.5 47.0,5.5 60.0,-15.5 60.0,-15.50 47.0,-15.0 47.0))"
         echo -n "Please enter the AOI polygon, first and last points shall be the same. Defaults is $polygon_default: "
         read polygon; [ -z "$polygon" ] && polygon="$polygon_default"
         # Build query and replace blanks spaces by '+'
         query="ingestiondate:[NOW-${lastdays}DAYS TO NOW] AND producttype:${ptype} AND footprint:\"Intersects(${polygon})\""
         query_server "${ROOT_URL_SEARCH}?q=${query// /+}"
         if [ "$USE_JQ" = "true" ]
         then
            RESULT_LIST=$(jq ".feed.entry[].id" "$OUT_FILE" | tr -d '"')
         else
            RESULT_LIST=$(cat "$OUT_FILE" | xmlstarlet sel -T -t -m '//_:entry/_:id/text()' -v '.' -n)
         fi
         # Display result list
         show_numbered_list "$RESULT_LIST"
         ;;

      7) # Get product id from product name
         # Ask for a product name and remove potential quotes
         echo -n "Please enter the name of the product (e.g. one from previous steps): "
         read prodname; prodname=${prodname//\"/}
         # Build URL and query server to get result list
         query_server "${ROOT_URL_ODATA}/Products?\$filter=Name+eq+'$prodname'"
         get_field_values "Id"
         # Display result list
         show_numbered_list "$RESULT_LIST"
         ;;

      8) # Get polarisation from a product id
         # Ask for a product id
         echo -n "Please enter the id of the product (e.g. one from step 5.): "
         read prodid; prodid=${prodid//\"/}
         # Build URL to get polarisation
         URL="${ROOT_URL_ODATA}/Products('$prodid')/Attributes('Polarisation')/Value/\$value"
         [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX \"$URL\""
         value=$($CURL_PREFIX "$URL")
         show_text "Polarisation = $value"
         ;;

      9) # Get relative orbit from a product id
         # Ask for a product id
         echo -n "Please enter the id of the product (e.g. one from step 5.): "
         read prodid; prodid=${prodid//\"/}
         # Build URL to get relative orbit
         URL="${ROOT_URL_ODATA}/Products('$prodid')/Attributes('Relative%20orbit%20(start)')/Value/\$value"
         [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX \"$URL\""
         value=$($CURL_PREFIX "$URL")
         show_text "Relative orbit (start) = $value"
         ;;

     10) # Download Manifest file from a product id
         # Ask for a product id
         echo -n "Please enter the id of the product (e.g. one from step 5.): "
         read prodid; prodid=${prodid//\"/}
         # Build URL to get product name
         URL="${ROOT_URL_ODATA}/Products('$prodid')/Name/\$value"
         [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX \"$URL\""
         prodname=$($CURL_PREFIX "$URL")
         [ "$VERBOSE" = "true" ] && show_text "$prodname"
         # Build URL to get Manifest node
         URL="${ROOT_URL_ODATA}/Products('$prodid')/Nodes('$prodname.SAFE')/Nodes('manifest.safe')/\$value"
         output_file="$prodname.manifest.safe"
         [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX -o "$output_file" \"$URL\""
         $CURL_PREFIX -o "$output_file" "$URL" && echo "Manifest file saved as \"$output_file\""
         [ "$VERBOSE" = "true" ] && show_text "$(cat "$output_file")"
         ;;

     11) # Download quick-look from a product id
         # Ask for a product id
         echo -n "Please enter the id of the product (e.g. one from step 5.): "
         read prodid; prodid=${prodid//\"/}
         # Build URL to get product name
         URL="${ROOT_URL_ODATA}/Products('$prodid')/Name/\$value"
         [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX \"$URL\""
         prodname=$($CURL_PREFIX "$URL")
         [ "$VERBOSE" = "true" ] && show_text "$prodname"
         # Build URL to get quick-look
         URL="${ROOT_URL_ODATA}/Products('$prodid')/Nodes('$prodname.SAFE')/Nodes('preview')/Nodes('quick-look.png')/\$value"
         output_file="$prodname.quick-look.png"
         [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX -o "$output_file" \"$URL\""
         $CURL_PREFIX -o "$output_file" "$URL" && echo "Quick-look file saved as \"$output_file\""
         ;;

     12) # Download full product from its id
         # Ask for a product id
         echo -n "Please enter the id of the product (e.g. one from step 5.): "
         read prodid; prodid=${prodid//\"/}
         # Build URL to get product
         URL="${ROOT_URL_ODATA}/Products('$prodid')/\$value"
         [ "$VERBOSE" = "true" ] && show_text "$CURL_PREFIX -JO \"$URL\""
         $CURL_PREFIX -JO "$URL"
         ;;

      q) echo "Bye."
      exit 0;;

      *) echo "Invalid selection \"$answer\"!" ;;
   esac
   #echo -n "Press ENTER to continue..."; read key
done

# Exit
exit 0

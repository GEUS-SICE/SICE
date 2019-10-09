#!/usr/bin/env bash 

RED='\033[0;31m'
ORANGE='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
MSG_OK() { echo -e "${GREEN}${@}${NC}"; }
MSG_WARN() { echo -e "${ORANGE}WARNING: ${@}${NC}"; }
MSG_ERR() { echo -e "${RED}ERROR: ${@}${NC}"; }

t_0=`date +%s`
t_last=`date +%s`
timing() { 
    if [[ $TIMING == 1 ]]; then
	MSG_OK "$(date)";
	t_now=$(date +%s)
	echo "    Time since start:" $(( ${t_now} - ${t_0} ))"s"
	echo "    Time since last:" $(( ${t_now} - ${t_last} ))"s"
	t_last=$(date +%s)
    fi; }

function print_usage() {
    echo ""
    echo "./S3_proc.sh -i inpath -o outpath [-D | -X file.xml] [-h -v -t]"
    echo "  -i: Path to folder containing S3A_*_EFR_*_002.SEN3 (unzipped S3 EFR) files"
    echo "  -o: Path where to store ouput"
    echo "  -D: Use DEBUG.xml (fast, few bands)"
    echo "  -X: Use non-default XML file [default: S3_proc.xml]"
    echo "  -v: Print verbose messages during processing"
    echo "  -t: Print timing messages during processing"
    echo "  --SICE: Run SICE"
    echo "  -h: print this help"
    echo ""
}

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    print_usage
	    exit 1
	    ;;
	-i)
	    INPATH="$2"
	    shift # past argument
	    shift # past value
	    ;;
	-o)
	    OUTPATH="$2"
	    shift; shift;;
	-X)
	    XML="$2"
	    shift; shift;;
	-D)
	    DEBUG=1
	    shift;;
	--SICE)
	    SICE=1
	    shift;;
	-v)
	    VERBOSE=1
	    set -x    # print commands to STDOUT before running them
	    shift;;
	-t)
	    TIMING=1
	    shift;;
    esac
done

PPGC_BOOL=true # per pixel geocoding
if [ ${DEBUG} == 1 ]; then
    MSG_WARN "DEBUG flag set"
    MSG_OK "Using DEBUG.xml"
    XML=DEBUG.xml
    MSG_OK "Turning off per-pixel geocoding for speed"
    PPGC_BOOL=false
fi
	   
if [ -z ${INPATH} ]; then MSG_ERR "-i not set"; print_usage; exit 1; fi
if [ -z ${OUTPATH} ]; then MSG_ERR "-o not set"; print_usage; exit 1; fi
if [ -z ${XML} ]; then MSG_ERR "-X not set"; print_usage; exit 1; fi

for folder in $(ls ${INPATH}); do
    S3FOLDER=$(basename ${folder})
    OUTFOLDER=$(echo $S3FOLDER | rev | cut -d_ -f11 | rev)
    DEST=${OUTPATH}/${OUTFOLDER}

    FILETMP=${DEST}/summary_cloud.tif 
    if [ -f ${FILETMP} ]; then
    	MSG_WARN "${FILETMP} already exists. Skipping..."
	continue # go to next folder
    fi

    MSG_OK "Generating ${OUTPATH}/${OUTFOLDER}"
    mkdir -p ${DEST}

    MSG_OK "GPT: Start"
    timing
    gpt ${XML} \
	-Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml \
	-Ppathfile=${INPATH}/${S3FOLDER}/xfdumanifest.xml \
	-PtargetFolder=${DEST} \
	-Ds3tbx.reader.olci.pixelGeoCoding=${PPGC_BOOL} \
	-e
    MSG_OK "GPT: Finished"
    timing

    MSG_OK "renaming..."
    # GPT bug means we can't write out band.tif, but have to use some other name.
    # I chose "band_x.tif". Here we work around that bug.
    for f in $(ls ${DEST}/*_x*); do mv ${f} "${f//_x}"; done

    MSG_OK "Compressing..."
    for f in $(cd ${DEST}; ls *.tif); do
	echo $f
	gdal_translate -co "COMPRESS=DEFLATE" ${DEST}/${f} ${DEST}/${f}_tmp.tif
	mv  ${DEST}/${f}_tmp.tif ${DEST}/${f}
    done

    if [ ${SICE} ]; then
	# input for sice
	# ns,alat,alon,sza,vza,saa,vaa,height,(toa(iks),iks=1,21)
	# ozone.dat
	# This file contains ozone concentration as provided in the OLCI file (units: kg/m/m)
	# The code transforms it to DU using:
	# ozone concentration in DU=46729.*OLCI_ozone
	# The number of lines in this file MUST be equal to the number of lines in the file 'nlines.dat'
	
	timing
	MSG_OK "Preparing SICE input files"

        grid_width=$(head -n 1 ${DEST}/latitude.csv | grep -o -E '[0-9]+')
        grid_height=$(( $(wc -l ${DEST}/latitude.csv| awk '{print $1} ') / $grid_width ))
	if [[ ! $grid_height =~ ^-?[0-9]+$ ]]; then 
	    MSG_WARN "Grid width: ${grid_width}"
	    MSG_WARN "Grid height: ${grid_height}"
	    MSG_ERR "Width or height of csv files not integer"
	    exit 1
	fi

	# Combine all these files, select every 2nd field cut header, and remove NaNs
	paste ${DEST}/{latitude,longitude,SZA,OZA,SAA,OAA,altitude,Oa*_reflectance}.csv \
	    | cut -d$'\t' -f1,$(seq -s "," 2 2 56) \
	    | tail -n +3 \
	    | awk '$2 != "NaN"' \
	    | awk '$3 != "NaN"' \
		   > ./${DEST}/olci_toa.dat
	
	# MSG_OK "Writing line number"
	wc -l ${DEST}/olci_toa.dat > ${DEST}/nlines.dat
	
	# MSG_OK "Creating ozone file"
	paste ${DEST}/{latitude,longitude,ozone}.csv \
	    | cut -d$'\t' -f1,2,4,6 \
	    | tail -n +3 \
	    | awk '$2 != "NaN"' \
	    | awk '$3 != "NaN"' \
	    | cut -d$'\t' -f4 \
		   > ./${DEST}/ozone.dat

	rm ${DEST}/{SZA,OZA,SAA,OAA,altitude,Oa*_reflectance,ozone}.csv
	
	# moving files to processor folder
	cp ${DEST}/{ozone,olci_toa,nlines}.dat ./SnowProcessor/

	# ===========  Running FORTRAN SICE ======================
	timing
	MSG_OK "Running sice.exe: BEGIN"
	cd ./SnowProcessor
	./sice.exe
	MSG_OK "Running sice.exe: END"
	timing
	# =========== translating output =========================
	# 
	# Output description:
	# spherical_albedo.dat	ns,ndate(3),alat,alon,(answer(i),i=1,21),isnow
	# lanar_albedo.dat	ns,ndate(3),alat,alon,(rp(i),i=1,21),isnow
	# boar.dat		ns,ndate(3),alat,alon,(refl(i),i=1,21),isnow
	# size.dat	      ns,ndate(3),alat,alon,D,area,al,r0, andsi,andbi,indexs,indexi,indexd,isnow
	# impurity.dat		ns,alat,alon,ntype,conc,bf,bm,thv,toa(1),isnow
	# bba.dat		ns,ndate(3),alat,alon,rp3,rp1,rp2,rs3,rs1,rs2,isnow
	# bba_alex_reduced.dat	ns,ndate(3),rp3,isnow
	# notsnow.dat		ns,ndate(3),alat,alon,icloud,iice
	# notsnow.dat lists the lines which are not processed bacause they have clouds
	#                   (first index=1) or bare ice (second index=1)

	# # converting files into csv
        MSG_OK "Converting bba.dat olci_toa.dat size.dat to GeoTIFF"

	# head bba.dat | sed 's/\ \ */,/g'| head -n1|tr ',' '\n' | cat -n
        parallel --bar --verbose \
		 "cat bba.dat | sed 's/\ \ */,/g' | cut -d, -f4,5,{1}|grep -v NaN > bba_{2}.csv" \
		 ::: $(seq 6 12) \
		 :::+ rp3 rp1 rp2 rs3 rs1 rs2 isnow

	# size.dat: ,_,_,lat,lon,D,area,al,r0,andsi,andbi,indexs,indexi,indexd,isnow
        parallel --bar --verbose \
		 "cat size.dat | sed 's/\ \ */,/g' | cut -d, -f4,5,{1}|grep -v NaN > size_{2}.csv" \
		 ::: $(seq 6 15) \
		 :::+ D area al r0 andsi andbi indexs indexi indexd isnow

	# head olci_toa.dat | sed 's/\t/,/g'| head -n1|tr ',' '\n' | cat -n
        parallel --bar --verbose \
		 "cat olci_toa.dat | sed 's/\t/,/g' | cut -d, -f2,3,{1}|grep -v NaN > olci_toa_{2}.csv" \
		 ::: $(seq 4 29) \
		 :::+ sza vza saa vaa height toa1 toa2 toa3 toa4 toa5 toa6 toa7 toa8 toa9 toa10 \
		 toa11 toa12 toa13 toa14 toa15 toa16 toa17 toa18 toa19 toa20 toa21

	grass -e -c ../mask.tif ./G_CSVll2GeoTIFFxy
	grass ./G_CSVll2GeoTIFFxy/PERMANENT/ --exec ../CSVll2GeoTIFFxy.sh $(ls *.csv)
	rm -fR ./G_CSVll2GeoTIFFxy

	cd ..
	cp -r ./SnowProcessor/*.tif ${DEST}/
	# rm -r ./SnowProcessor/*.csv
	cp ./SnowProcessor/bba_alex_reduced.dat ${DEST}/bba_alex_reduced.dat
	cp ./SnowProcessor/bba.dat ${DEST}/bba.dat
	cp ./SnowProcessor/boar.dat ${DEST}/boar.dat
	cp ./SnowProcessor/planar_albedo.dat ${DEST}/planar_albedo.dat
	cp ./SnowProcessor/spherical_albedo.dat ${DEST}/spherical_albedo.dat
	cp ./SnowProcessor/impurity.dat ${DEST}/impurity.dat
	cp ./SnowProcessor/nlines.dat ${DEST}/nlines.dat
	cp ./SnowProcessor/notsnow.dat ${DEST}/notsnow.dat
	cp ./SnowProcessor/size.dat ${DEST}/size.dat
	cp ./SnowProcessor/interm.dat ${DEST}/interm.dat
	
	rm ./SnowProcessor/*.{tif,csv}
	rm ./SnowProcessor/{bba_alex_reduced,bba,boar}.dat 
	rm ./SnowProcessor/planar_albedo.dat
	rm ./SnowProcessor/spherical_albedo.dat 
	rm ./SnowProcessor/impurity.dat
	rm ./SnowProcessor/nlines.dat 
	rm ./SnowProcessor/olci_toa.dat 
	rm ./SnowProcessor/notsnow.dat
	rm ./SnowProcessor/ozone.dat
	rm ./SnowProcessor/size.dat
	rm ./SnowProcessor/interm.dat
    fi
done

MSG_OK "Finished: ${folder}"
timing
	

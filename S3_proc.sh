#!/usr/bin/env bash 
#PATH=~/local/snap/bin:$PATH #./S3_proc.sh -i ./dat_S3A -o ./out_S3A
start=`date +%s`
start0=`date +%s`
RED='\033[0;31m'
ORANGE='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
MSG_OK() { printf "${GREEN}${1}${NC}\n"; }
MSG_WARN() { printf "${ORANGE}WARNING: ${1}${NC}\n"; }
MSG_ERR() { printf "${RED}ERROR: ${1}${NC}\n"; }

timing() { if [[ $TIMING == 1 ]]; then MSG_OK "$(date)"; fi; }

while [[ $# -gt 0 ]]
do
    key="$1"
    
    case $key in
	-h|--help)
	    echo "./S3_proc.sh -i inpath -o outpath [-D | -X file.xml] [-h -v -t]"
	    echo "  -i: Path to folder containing S3A_*_EFR_*_002.SEN3 (unzipped S3 EFR) files"
	    echo "  -o: Path where to store ouput"
	    echo "  -D: Use DEBUG.xml (fast, few bands)"
	    echo "  -X: Use non-default XML file [default: S3_proc.xml]"
	    echo "  -v: Print verbose messages during processing"
	    echo "  -t: Print timing messages during processing"
	    echo "  -h: print this help"
	    exit 1;;
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
	-csv)
	    CSV=1
	    shift;;
	-v)
	    VERBOSE=1
	    shift;;
	-t)
	    TIMING=1
	    shift;;
    esac
done

if [ -z $INPATH ] || [ -z $OUTPATH ];then
    echo "-i and -o option not set"
    echo " "
    $0 -h
    exit 1
fi
for folder in $(ls ${INPATH}); do
    S3FOLDER=$(basename ${folder})
    OUTFOLDER=$(echo $S3FOLDER | rev | cut -d_ -f11 | rev)
    DEST=${OUTPATH}/${OUTFOLDER}
	FILETMP=${DEST}/summary_cloud.tif 

    if [ -f ${FILETMP} ]; then
    	MSG_WARN "${FILETMP} already exists. Skipping..."
		continue
    else
    	MSG_OK "Generating ${OUTPATH}/${OUTFOLDER}"
    	mkdir -p ${DEST}
    fi

    MSG_OK "GPT: Start"

    if [[ ${DEBUG} == 1 ]]; then
		MSG_WARN "Using DEBUG.xml"
		MSG_ERR "Not using per pixel geocoding for speed"
		gpt DEBUG.xml -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -Ppathfile=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST} -Ds3tbx.reader.olci.pixelGeoCoding=false -e
    elif [[ ! -z ${XML} ]]; then 
		MSG_WARN "Using ${XML}"
		MSG_OK "Per-pixel geocoding enabled"
		gpt ${XML} -Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml -Ppathfile=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST} -Ds3tbx.reader.olci.pixelGeoCoding=true -e
	else
		MSG_WARN "Using default XML: S3_proc.xml"
		MSG_OK "Per-pixel geocoding enabled"
		gpt S3_proc.xml --Ssource=${INPATH}/${S3FOLDER}/xfdumanifest.xml  Ppathfile=${INPATH}/${S3FOLDER}/xfdumanifest.xml -PtargetFolder=${DEST} -Ds3tbx.reader.olci.pixelGeoCoding=true -e
    fi
    
    MSG_OK "GPT: Finished"

    MSG_OK "renaming..."
    for f in $(ls ${DEST}/*_x*); do mv ${f} "${f//_x}"; done

    timing
	if [ -z $CSV ]; then
	    MSG_OK "Compressing: Start"
		for f in $(ls ${DEST}); do
    		echo $f
    		gdal_translate -co "COMPRESS=DEFLATE" ${DEST}/${f} ${DEST}/${f}_tmp.tif
    		mv  ${DEST}/${f}_tmp.tif ${DEST}/${f}
		done
	else
		# input for sice
		# ns,alat,alon,sza,vza,saa,vaa,height,(toa(iks),iks=1,21)
		# ozone.dat
		# This file contains ozone concentration as provided in the OLCI file (units: kg/m/m)
		# The code transforms it to DU using:
		# ozone concentration in DU=46729.*OLCI_ozone
		# The number of lines in this file MUST be equal to the number of lines in the file 'nlines.dat'
		end=`date +%s`
		echo Execution time was `expr $end - $start` seconds.
		start=`date +%s`

	    MSG_OK "Preparing input files"
		paste ${DEST}/latitude.csv ${DEST}/longitude.csv ${DEST}/SZA.csv ${DEST}/OZA.csv ${DEST}/SAA.csv ${DEST}/OAA.csv ${DEST}/altitude.csv ${DEST}/Oa*_reflectance.csv > ${DEST}/tmp.txt

		awk '{print $1 "\t" $2 "\t" $4 "\t" $6 "\t" $8 "\t" $10 "\t" $12 "\t" $14 "\t" $16 "\t" $18 "\t" $20 "\t" $22 "\t" $24 "\t" $26 "\t" $28 "\t" $30 "\t" $32 "\t" $34"\t" $36 "\t" $38 "\t" $40 "\t" $42 "\t" $44 "\t" $46 "\t" $48 "\t" $50 "\t" $52 "\t" $54"\t" $56}'  ${DEST}/tmp.txt > ${DEST}/olci_toa.txt

		rm ${DEST}/tmp.txt
		
		# MSG_OK "Cutting header"
		sed -i '1,2d' ${DEST}/olci_toa.txt > ${DEST}/olci_toa.dat
		cp ${DEST}/olci_toa.txt  ${DEST}/olci_toa_tmp.dat
		 rm ${DEST}/olci_toa.txt 
		
		grid_width=$(echo "$(head -n 1 ${DEST}/latitude.csv)" | grep -o -E '[0-9]+')
		grid_height=$(($(echo "$(wc -l ${DEST}/latitude.csv| awk '{print $1} ')" | grep -o -E '[0-9]+') / $grid_width))

		if [[ ! $grid_height =~ ^-?[0-9]+$ ]]; then
		echo $grid_width
		echo $grid_height
			MSG_ERR "Width or height of csv files not integer"
		fi


		# MSG_OK "Removing NaN"
		awk '$2 != "NaN"' ${DEST}/olci_toa_tmp.dat > ${DEST}/olci_toa_tmp2.dat
		awk '$3 != "NaN"' ${DEST}/olci_toa_tmp2.dat > ${DEST}/olci_toa.dat
		 rm ${DEST}/olci_toa_tmp.dat
		 rm ${DEST}/olci_toa_tmp2.dat

		# MSG_OK "Writting line number"
		wc -l < ${DEST}/olci_toa.dat > ${DEST}/nlines.dat

		# MSG_OK "Creating ozone file"
		paste ${DEST}/latitude.csv ${DEST}/longitude.csv ${DEST}/ozone.csv  > ${DEST}/tmp1.txt

		awk '{print $1 "\t" $2 "\t" $4 "\t" $6}'  ${DEST}/tmp1.txt > ${DEST}/tmp2.txt
		
		awk '$2 != "NaN"' ${DEST}/tmp2.txt > ${DEST}/tmp3.txt
		awk '$3 != "NaN"' ${DEST}/tmp3.txt > ${DEST}/tmp4.txt
		
		awk '{print $4}'  ${DEST}/tmp4.txt > ${DEST}/ozone.dat
		sed -i '1,2d' ${DEST}/ozone.dat

		rm ${DEST}/SZA.csv ${DEST}/OZA.csv ${DEST}/SAA.csv ${DEST}/OAA.csv ${DEST}/altitude.csv ${DEST}/Oa*_reflectance.csv 
		rm ${DEST}/ozone.csv
		rm ${DEST}/tmp1.txt
		rm ${DEST}/tmp2.txt
		rm ${DEST}/tmp3.txt
		rm ${DEST}/tmp4.txt

		# moving files to processor folder
		cp ${DEST}/ozone.dat ./SnowProcessor/ozone.dat
		cp ${DEST}/olci_toa.dat ./SnowProcessor/olci_toa.dat
		cp ${DEST}/nlines.dat ./SnowProcessor/nlines.dat
		end=`date +%s`
		echo Execution time was `expr $end - $start` seconds.
		start=`date +%s`
		# ===========  Running FORTRAN SICE ======================
		MSG_OK "Running sice.exe"
		cd ./SnowProcessor
		./sice.exe
		end=`date +%s`
		echo Execution time was `expr $end - $start` seconds.
		start=`date +%s`
		# =========== translating output =========================
		# 
		# Output description:
		# spherical_albedo.dat		ns,ndate(3),alat,alon,(answer(i),i=1,21),isnow
		# lanar_albedo.dat			ns,ndate(3),alat,alon,(rp(i),i=1,21),isnow
		# boar.dat					ns,ndate(3),alat,alon,(refl(i),i=1,21),isnow
		# size.dat					ns,ndate(3),alat,alon,D,area,al,r0, andsi,andbi,indexs,indexi,indexd,isnow
		# impurity.dat				ns,alat,alon,ntype,conc,bf,bm,thv,toa(1),isnow
		# bba.dat					ns,ndate(3),alat,alon,rp3,rp1,rp2,rs3,rs1,rs2,isnow
		# bba_alex_reduced.dat		ns,ndate(3),rp3,isnow
		# notsnow.dat				ns,ndate(3),alat,alon,icloud,iice
		# notsnow.dat lists the lines which are not processed bacause they have clouds (first index=1) or bare ice (second index=1)

		# converting files into csv
		MSG_OK "Converting bba.dat olci_toa.dat size.dat into tif"
		awk -F$'\t'  'BEGIN{print "ns,alat,alon,sza,vza,saa,vaa,height,toa1,toa2,toa3,toa4,toa5,toa6,toa7,toa8,toa9,toa10,toa11,toa12,toa13,toa14,toa15,toa16,toa17,toa18,toa19,toa20,toa21"}; {for(i=1;i<=NF;i++){if (i==NF) { printf "%s", $i } else { printf "%s,", $i }}; printf "\n"}' olci_toa.dat > olci_toa.csv

		awk  'BEGIN{print "ns,ndate,alat,alon,D,area,al,r0,andsi,andbi,indexs,indexi,indexd,isnow,icloud,iice"}; {for(i=1;i<=NF;i++){printf "%s,", $i};printf "-999,-999\n"}' size.dat > size_tmp.csv

		awk 'BEGIN{print "ns,ndate,alat,alon,rp3,rp1,rp2,rs3,rs1,rs2,isnow,icloud,iice"}; {for(i=1;i<=NF;i++){printf "%s,", $i};printf "-999,-999\n"}' bba.dat > bba_tmp.csv

		awk '{for(i=1;i<=NF;i++){if (i==NF) { printf "%s", $i } else { printf "%s,", $i }}; printf "\n"}' notsnow.dat > notsnow_tmp.csv
		
		# appending the not snow data to the csvs
		awk -F$',' '{print $1 "," $2 "," $3 "," $4 ",-999,-999,-999,-999,-999,-999,-999," $5 "," $6}'  notsnow_tmp.csv > notsnow_for_bba.csv
		awk -F$',' '{print $1 "," $2 "," $3 "," $4 ",-999,-999,-999,-999,-999,-999,-999,-999,-999,-999," $5 "," $6}'  notsnow_tmp.csv > notsnow_for_size.csv

		cat bba_tmp.csv notsnow_for_bba.csv > bba.csv
		cat size_tmp.csv notsnow_for_size.csv > size.csv

		# adding header
		awk 'BEGIN{print "ns,ndate,alat,alon,icloud,iice"}; {print}; END{print "END"}' notsnow_tmp.csv > notsnow.csv

		rm *_tmp.csv
		rm notsnow_for_bba.csv notsnow_for_size.csv
		
		# declare -a outfiles=("spherical_albedo" "planar_albedo" "size" "impurity" "bba" "bba_alex_reduced")
declare -a outfiles=("bba" "size" "olci_toa")

for f in "${outfiles[@]}"; do
if [ ! -f ${f}.vrt ]; then
cat <<-EOF > ${f}.vrt
<OGRVRTDataSource>
<OGRVRTLayer name="${f}">
<SrcDataSource>${f}.csv</SrcDataSource>
<GeometryType>wkbPoint</GeometryType>
<GeometryField encoding="PointFromColumns" x="alon" y="alat"/>
</OGRVRTLayer>
</OGRVRTDataSource>
EOF
fi

if [ ! -f ${f}_3413.vrt ]; then
cat <<-EOF > ${f}_3413.vrt
<OGRVRTDataSource>
<OGRVRTLayer name="${f}_3413">
<SrcDataSource>${f}_3413.csv</SrcDataSource>
<GeometryType>wkbPoint</GeometryType>
<GeometryField encoding="PointFromColumns" x="X" y="Y"/>
</OGRVRTLayer>
</OGRVRTDataSource>
EOF
fi
done

		# now loop through the above array
		for f in "${outfiles[@]}"; do
		   echo "$f"
		   if [ $f == "bba" ]; then
				declare -a var=("rp3" "rp1" "rp2" "rs3" "rs1" "rs2" "isnow" "icloud" "iice")
				echo "${var[@]}"
			fi
			if [ $f == "size" ]; then
				declare -a var=("D" "area" "al" "r0" "andsi" "andbi" "indexs" "indexi" "indexd")
				echo "${var[@]}"
			fi
			if [ $f == "olci_toa" ]; then
				declare -a var=("sza" "vza" "saa" "vaa" "height" "toa1" "toa21")
				echo "${var[@]}"
			fi

			# reprojecting
			ogr2ogr -f CSV -t_srs EPSG:3413 -s_srs EPSG:4326 -lco GEOMETRY=AS_XY -nln ${f}_3413 ${f}_3413.csv ${f}.vrt

			#converting to tiff			
			# if [ ! -f scene_extent.tif ]; then
				gdal_grid -q -a count:radius1=10000:radius2=10000  -outsize ${grid_width} ${grid_height}  -a_srs EPSG:3413 -l ${f}_3413 ${f}_3413.vrt  concavehull_${f}_tmp.tif		
				gdal_calc.py  --quiet --NoDataValue=-999 -A concavehull_${f}_tmp.tif --calc="A>1" --outfile scene_extent.tif
			# fi

			for ii in "${var[@]}"; do
				gdal_grid -q -l ${f}_3413 -zfield "$ii" -outsize ${grid_width} ${grid_height} -a_srs EPSG:3413 -a nearest:radius1:5000:radius2:5000:nodata=-999  ${f}_3413.vrt ${ii}_tmp.tif
				gdal_calc.py --quiet -A ${ii}_tmp.tif -B scene_extent.tif --outfile="${ii}_clipped".tif --calc="A*(B==1) -999*(B==0)" --NoDataValue=-999
			done
			rm *_tmp.tif
		done

		cd ..
		cp -r ./SnowProcessor/*.tif					${DEST}/
		rm -r ./SnowProcessor/*.csv
		# rm -r ./SnowProcessor/*.vrt
		cp ./SnowProcessor/bba_alex_reduced.dat		${DEST}/bba_alex_reduced.dat
		cp ./SnowProcessor/bba.dat					${DEST}/bba.dat
		cp ./SnowProcessor/boar.dat					${DEST}/boar.dat
		cp ./SnowProcessor/planar_albedo.dat			${DEST}/planar_albedo.dat
		cp ./SnowProcessor/spherical_albedo.dat		${DEST}/spherical_albedo.dat
		cp ./SnowProcessor/impurity.dat				${DEST}/impurity.dat
		cp ./SnowProcessor/nlines.dat				${DEST}/nlines.dat
		cp ./SnowProcessor/notsnow.dat				${DEST}/notsnow.dat
		cp ./SnowProcessor/size.dat					${DEST}/size.dat
		cp ./SnowProcessor/interm.dat				${DEST}/interm.dat
					 
		rm ./SnowProcessor/*.tif
		rm ./SnowProcessor/*.csv
		rm ./SnowProcessor/bba_alex_reduced.dat 
		rm ./SnowProcessor/bba.dat
		rm ./SnowProcessor/boar.dat 
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

timing
MSG_OK "Finished: ${folder}"
end=`date +%s`
echo Execution time was `expr $end - $start` seconds.
echo Total execution time was `expr $end - $start0` seconds.

	
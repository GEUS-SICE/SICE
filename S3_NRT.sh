#!/usr/bin/env bash

# Wrapper for running SICE pipeline Near Real-Time (NRT)

# example of cron job:
# m h  dom mon dow   command
# 00 12 * * * /bin/bash -c "/path/to/wrapper/S3_NRT.sh" > /path/to/log/log_NRT.txt

# use SNAP gpt
export PATH=/path/to/snap/bin:${PATH}

# activate SICE anaconda virtual environment
anaconda_path=""
. "${anaconda_path}"/envs/SICE/bin/activate

source "${anaconda_path}"/etc/profile.d/conda.sh
conda activate SICE

set -o errexit
set -o nounset
set -o pipefail
set -x

red='\033[0;31m'
orange='\033[0;33m'
green='\033[0;32m'
nc='\033[0m' # No Color
log_info() { echo -e "${green}[$(date --iso-8601=seconds)] [INFO] ${*}${nc}"; }
log_warn() { echo -e "${orange}[$(date --iso-8601=seconds)] [WARN] ${*}${nc}"; }
log_err() { echo -e "${red}[$(date --iso-8601=seconds)] [ERR] ${*}${nc}" 1>&2; }

# Scihub credentials (from local auth.txt in SICE folder)
username=$(sed -n '1p' auth.txt)
password=$(sed -n '2p' auth.txt)

# change directory to the current folder
cd "${0%/*}"

### dev
# SEN3_source=./SEN3
# proc_root=./out
# mosaic_root=./mosaic

LD_LIBRARY_PATH=. # SNAP requirement

date=$(date -d '-2days' "+%Y-%m-%d")
year=$(date "+%Y")

declare -a regions=("Greenland" "Iceland" "Svalbard" "NovayaZemlya" "SevernayaZemlya" "FransJosefLand" "NorthernArcticCanada" "SouthernArcticCanada" "JanMayen" "Norway" "Beaufort")

for region in "${regions[@]}"; do

	# CREODIAS
	SEN3_local=/eodata/Sentinel-3
	SEN3_source=/sice-data/SICE/"${region}"/S3
	proc_root=/sice-data/SICE/"${region}"/proc
	mosaic_root=/sice-data/SICE/"${region}"/mosaic

	mkdir -p /sice-data/SICE/"${region}"

	### Fetch one day of OLCI & SLSTR scenes over Greenland
	## Use local files (PTEP, DIAS, etc.)
	./dhusget_wrapper.sh -d "${date}" -l "${SEN3_local}" -o "${SEN3_source}"/"${year}"/"${date}" \
		-f "${region}" -u "${username}" -p "${password}"

	# SNAP: Reproject, calculate reflectance, extract bands, etc.
	./S3_proc.sh -i "${SEN3_source}"/"${year}"/"${date}" -o "${proc_root}"/"${date}" -X S3_fast.xml -t

	# Run the Simple Cloud Detection Algorithm (SCDA)
	python ./SCDA.py "${proc_root}"/"${date}"

	# Mosaic
	./dm.sh "${date}" "${proc_root}"/"${date}" "${mosaic_root}"

	# SICE
	python ./sice.py "${mosaic_root}"/"${date}"

done

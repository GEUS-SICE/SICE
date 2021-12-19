# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé and Jason Box, GEUS (Geological Survey of Denmark and Greenland)

A script for the download of SICE product files through the SICE dataverse at GEUS

How to Get an API Token: https://guides.dataverse.org/en/latest/api/auth.html

dataset_name is a flag to point to a given SICE data set:

SICE_NRT: Wehrlé, Adrien; Box, Jason; Vandecrux, Baptiste; Mankoff, Ken, 2021, 
          "Daily Near Real Time (NRT) Greenland snow and ice broadband albedo, SSA and cloud mask 
          from Sentinel-3's OLCI", https://doi.org/10.22008/FK2/SD56CB, GEUS Dataverse, V21
   
SICE_BBA: Wehrlé, Adrien; Box, Jason; Vandecrux, Baptiste; Mankoff, Ken, 2021, 
          "Gapless semi-empirical daily snow and ice albedo from Sentinel-3 OLCI", 
          https://doi.org/10.22008/FK2/A5RXJ5, GEUS Dataverse, V1
"""

import os
import pandas as pd
from pyDataverse.api import NativeApi, DataAccessApi

# %% choose SICE dataset

dataset_name = "SICE_NRT"

if dataset_name == "SICE_NRT":
    # dataset DOI
    persistentId = "doi:10.22008/FK2/SD56CB"

    # list of output files that needs to be downloaded from each dataverse subfolder
    files_to_download = [
        "r_TOA_01.tif",
        "r_TOA_06.tif",
        "r_TOA_17.tif",
        "r_TOA_21.tif",
        "albedo_bb_planar_sw.tif",
        "snow_specific_surface_area.tif",
        "SCDA_final.tif",
    ]

if dataset_name == "SICE_BBA":
    # dataset DOI
    persistentId = "doi:10.22008/FK2/A5RXJ5"


# %% prepare download information

# dataverse URL
dataverse_server = "https://dataverse01.geus.dk"

#  local folder to store data set
folder_store = "/path/to/SICE/folder"

# user API key
api_key = "your_api_key"

# create a NativeApi instance
api = NativeApi(dataverse_server, api_key)

# access dataverse’s data access API
data_api = DataAccessApi(dataverse_server, api_key)

# get dataverse metadata
dataset = api.get_dataset(persistentId)

# example of date range (all dates within the time window will be downloaded)
date_range = ["2021-08-01", "2021-08-03"]

# create list of dates from first to last date
date_list = list(pd.date_range(date_range[0], date_range[1]).strftime("%Y-%m-%d"))

# %% the actual download

#  local data set subfolder to store files
destination_folder = f"{folder_store}/{dataset_name}"
os.makedirs(destination_folder)

# access list of files to download from the dataverse
dataverse_files = dataset.json()["data"]["latestVersion"]["files"]

for file in dataverse_files:

    # store metadata
    dataverse_filename = file["dataFile"]["filename"]
    file_id = file["dataFile"]["id"]

    # extract SICE_NRT file date from subfolder name
    if dataset_name == 'SICE_NRT':
        file_date = file["directoryLabel"]

    # etract SICE_BBA file date from file name
    if dataset_name == 'SICE_BBA':
        file_date = file["directoryLabel"]

    if dataverse_filename in files_to_download and file_date in date_list:

        # create the dataverse directory tree
        try:
            os.makedirs(f"{destination_folder}/{file_date}")
        except FileExistsError:
            pass

        if dataset_name == 'SICE_NRT':
            local_filename = f"{destination_folder}{file_date}/{dataverse_filename}"
        
        if dataset_name == 'SICE_BBA':
            local_filename = f"{destination_folder}{dataverse_filename}"
            
        # download if file does not exist yet
        if bool(os.path.isfile(local_filename)) == False:

            print(f"downloading {file_date}/{dataverse_filename}...")

            # download datafile
            response = data_api.get_datafile(file_id)

            # write file
            with open(local_filename, "wb") as f:
                f.write(response.content)
        else:

            print(f"{local_filename} already exists")

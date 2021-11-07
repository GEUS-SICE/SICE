# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé and Jason Box, GEUS (Geological Survey of Denmark and Greenland)

A simple script for the download of output files through the SICE dataverse
(example of the SICE NRT data set).

"""

import os
import pandas as pd
from pyDataverse.api import NativeApi, DataAccessApi

# %% prepare download information

# dataverse URL
dataverse_server = "https://dataverse01.geus.dk"

# user API key
api_key = "your_api_key"

# dataset DOI (here SICE NRT data set)
persistentId = "doi:10.22008/FK2/SD56CB"

#  local folder to store files
folder_store = "/path/to/SICE/folder"

# create a NativeApi instance
api = NativeApi(dataverse_server, api_key)

# access dataverse’s data access API
data_api = DataAccessApi(dataverse_server, api_key)

# get dataverse metadata
dataset = api.get_dataset(persistentId)

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

# example of date range (all dates within the time window will be downloaded)
date_range = ["2021-08-01", "2021-08-03"]

# create list of dates from first to last date
date_list = list(pd.date_range(date_range[0], date_range[1]).strftime("%Y-%m-%d"))

# %% the actual download

# access list of files to download from the dataverse
dataverse_files = dataset.json()["data"]["latestVersion"]["files"]

for file in dataverse_files:

    # store metadata
    dataverse_filename = file["dataFile"]["filename"]
    file_id = file["dataFile"]["id"]
    file_directory = file["directoryLabel"]

    if dataverse_filename in files_to_download and file_directory in date_list:

        # create the dataverse directory tree
        try:
            os.makedirs(f"{folder_store}/{file_directory}")
        except FileExistsError:
            pass

        local_filename = f"{folder_store}{file_directory}/{dataverse_filename}"

        # download if file does not exist yet
        if bool(os.path.isfile(local_filename)) == False:

            print(f"downloading {file_directory}/{dataverse_filename}...")

            # download datafile
            response = data_api.get_datafile(file_id)

            # write file
            with open(local_filename, "wb") as f:
                f.write(response.content)
        else:

            print(f"{local_filename} already exists")

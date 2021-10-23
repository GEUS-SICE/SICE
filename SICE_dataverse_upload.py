# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, Baptiste Vandecrux, GEUS (Geological Survey 
         of Denmark and Greenland)

"""

import json
import requests
import os
from pyDataverse.api import NativeApi
import time
import argparse

# %% parse arguments from command line

parser = argparse.ArgumentParser()
parser.add_argument("InputFolder")
args = parser.parse_args()

# %% declare various inputs

# dataverse URL
dataverse_server = "https://dataverse01.geus.dk"

# user API key
api_key = "your_api_key"

# dataset DOI (here NRT dataset)
persistentId = "doi:10.22008/FK2/SD56CB"

# list files to upload from daily subfolders
file_list = [
    "r_TOA_01.tif",
    "r_TOA_06.tif",
    "r_TOA_17.tif",
    "r_TOA_21.tif",
    "albedo_bb_planar_sw.tif",
    "snow_specific_surface_area.tif",
    "SCDA_final.tif",
    "SCDA_v20.tif",
    "BBA_combination.tif",
]

# Add file description
file_description = "SICE products"

# %% upload function


def upload_files_to_dataverse(
    folder: str, file_list: list, file_description: str
) -> str:
    """
    Upload a list of files and associated descriptions to the dataverse
    
    :param folder: path to local folder where files are stored
    :param file_list: list of files to upload 
    :param file_description: description to add to uploaded files 
    :returns status: upload status, if successful then status is 'OK',
    otherwise 'ERROR'
    """

    for file in file_list:

        # check if file exists in local and is not corrupted
        try:
            files = {"file": open(f"{folder}/{file}", "rb")}
        except Exception as e:
            print(e)
            continue

        # build parameter dictionary
        params = dict(
            description=file_description,
            directoryLabel=os.path.basename(os.path.normpath(folder)),
        )

        # serialize dictionary to a JSON formatted string
        params_as_json_string = json.dumps(params)

        # build payload
        payload = dict(jsonData=params_as_json_string)

        # assemble target URL
        url_persistent_id = (
            f"{dataverse_server}/api/datasets/:persistentId/"
            + "add?persistentId={persistendId}&key={api_key}"
        )

        # print status
        print("uploading ", os.path.basename(os.path.normpath(folder)) + os.sep + file)

        # make POST request to target URL
        r = requests.post(url_persistent_id, data=payload, files=files)

        # store upload status
        status = r.json()["status"]

        return status


# %% run every 5 seconds until upload is successful (circumventing denied URL requests)

# create a NativeApi instance
api = NativeApi(dataverse_server, api_key)

# declare a flag to track upload status
flag = None

while flag != "OK":

    try:
        flag = upload_files_to_dataverse(args.InputFolder, file_list, file_description)
    except Exception as e:
        print(e)
        print("... starting again")
        time.sleep(5)

# make a new release
print("Publishing dataset...")
api.publish_dataset(persistentId, "major")

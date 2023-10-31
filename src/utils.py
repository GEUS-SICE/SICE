import matplotlib.pyplot as plt
import numpy as np
import os
import logging
import subprocess
from botocore.client import Config as botoConfig
from botocore.exceptions import ClientError
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
import boto3
import glob

logger = logging.getLogger(__name__)

def plot_image(image, factor=1.0, clip_range=None, **kwargs):
    """
    Utility function for plotting RGB images.
    """
    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(15, 15))
    if clip_range is not None:
        ax.imshow(np.clip(image * factor, *clip_range), **kwargs)
    else:
        ax.imshow(image * factor, **kwargs)
    ax.set_xticks([])
    ax.set_yticks([])


def merge_tiffs(input_filename_list, merged_filename, *, overwrite=False, delete_input=False):
    """Performs gdal_merge on a set of given geotiff images

    :param input_filename_list: A list of input tiff image filenames
    :param merged_filename: Filename of merged tiff image
    :param overwrite: If True overwrite the output (merged) file if it exists
    :param delete_input: If True input images will be deleted at the end
    """
    if os.path.exists(merged_filename):
        if overwrite:
            os.remove(merged_filename)
        else:
            raise OSError(f"{merged_filename} exists!")

    logger.info("merging %d tiffs to %s", len(input_filename_list), merged_filename)
    subprocess.check_call(
        ["gdal_merge.py", "-co", "BIGTIFF=YES", "-co", "compress=LZW", "-a_nodata", "nan","-o", merged_filename, *input_filename_list]
    )
    logger.info("merging done")

    if delete_input:
        logger.info("deleting input files")
        for filename in input_filename_list:
            if os.path.isfile(filename):
                os.remove(filename)

def importToBucket(awsConfig, resultsFolder):
    
    try:
        s3_client = boto3.resource('s3',
                                   endpoint_url=awsConfig['s3Url'],
                                   use_ssl=False,
                                   aws_access_key_id=awsConfig['s3AccessKey'],
                                   aws_secret_access_key=awsConfig['s3SecrestKey'],
                                   config=botoConfig(
                                       signature_version='s3',
                                       connect_timeout=60,
                                       read_timeout=60,
                                   ))

        bucket = s3_client.Bucket(awsConfig['bucketName'])
    except Exception as e:
        logger.error(e)
        raise Exception('Invalid bucket parameters') 
    
    
    # get tif files to upload
    filenamesList = glob.glob(f'{resultsFolder}/*.tif')
    try:
        for file in filenamesList:
            destFile = file.replace(resultsFolder, awsConfig['folder'])
            logger.info(f'Uploading to {destFile}')
            response = bucket.upload_file(file, destFile)
    except Exception as e:
        logger.error(e)
        raise Exception(f'Failed to upload file: {destFile}') 

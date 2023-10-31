
# Various utilities

import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
import argparse
import sys
import os
import json
from shapely import geometry, wkt
import IPython.display
from dataverse_upload import dataverse_upload
import datetime as dt
import numpy as np
from numpy import asarray as ar
import glob
import shutil
import logging
import concurrent.futures
import time
import pandas as pd
from multiprocessing import set_start_method,get_context
import geopandas as gpd
import rasterio as rio
from rasterio.transform import Affine
from pyproj import Transformer
from pyproj import CRS as CRSproj
from scipy.spatial import KDTree
from sentinelhub import SentinelHubBatch, SentinelHubRequest, Geometry, DataCollection, MimeType, SHConfig, BBox, bbox_to_dimensions, ServiceUrl
from utils import merge_tiffs, importToBucket
from shapely.geometry import Polygon
import tarfile
import traceback
from pysice import proc
from cams import get_maps


if sys.version_info < (3, 4):
    raise "must use python 3.6 or greater"

# create logs folder
base_path = os.path.abspath('..')
if not os.path.exists(base_path + os.sep + "logs"):
    os.makedirs(base_path + os.sep + "logs")

# right now we only log to consol
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(f'{base_path}/logs/sice_sh_{time.strftime("%Y_%m_%d",time.localtime())}.log'),
        logging.StreamHandler()
    ])
    

def parse_arguments():
        parser = argparse.ArgumentParser(description='')
        parser.add_argument("-d","--day", type=str,help="Please input the day you want to proces")
        parser.add_argument("-a","--area", type=str,help="Please input the area you want to proces",\
                            choices=['Greenland','Iceland','Svalbard','SouthernArcticCanada','NorthernArcticCanada',\
                                     'AlaskaYukon','SevernayaZemlya','NovayaZemlya','FransJosefLand','Norway'])
        parser.add_argument("-r","--res", type=int,help="Please input the resolution you want to proces")
        parser.add_argument("-t","--test", type=int, default = 0)
        args = parser.parse_args()
        return args


def multi_merge(product,dl_f,pro_f):
    
    prodResult = product.replace(".tif", '_merged.tif')
    if os.path.exists(prodResult):
        os.remove(prodResult)
        logging.info(f'Deleted file: {prodResult}')
    logging.info(f'Creating file {prodResult}')
    filenamesList = glob.glob(f'{dl_f}/*/*/{product}')
    if filenamesList:
        merge_tiffs(filenamesList, prodResult, overwrite=True)
    
        shutil.move(prodResult, f'{pro_f}/{prodResult}')

def opentiff(filename):

    "Input: Filename of GeoTIFF File "
    "Output: xgrid,ygrid, data paramater of Tiff, the data projection"
    warnings.filterwarnings("ignore", category=FutureWarning)
    
    da = rio.open(filename)
    proj = CRSproj(da.crs)

    elevation = np.array(da.read(1),dtype=np.float32)
    nx,ny = da.width,da.height
    x,y = np.meshgrid(np.arange(nx,dtype=np.float32), np.arange(ny,dtype=np.float32)) * da.transform

    da.close()

    return x,y,elevation,proj

def exporttiff(x,y,z,crs,filename):
    
    "Input: xgrid,ygrid, data paramater, the data projection, export path, name of tif file"
    warnings.filterwarnings("ignore", category=FutureWarning)
    resx = (x[0,1] - x[0,0])
    resy = (y[1,0] - y[0,0])
    transform = Affine.translation((x.ravel()[0]),(y.ravel()[0])) * Affine.scale(resx, resy)
    
    if resx == 0:
        resx = (x[0,0] - x[1,0])
        resy = (y[0,0] - y[0,1])
        transform = Affine.translation((y.ravel()[0]),(x.ravel()[0])) * Affine.scale(resx, resy)
    
    with rio.open(
    filename,
    'w',
    driver='GTiff',
    height=z.shape[0],
    width=z.shape[1],
    count=1,
    dtype=z.dtype,
    crs=crs,
    transform=transform,
    ) as dst:
        dst.write(z, 1)
    
    dst.close()
    
    return None 


# Disable
def blockPrint():
    sys.stdout = open(os.devnull, 'w')

def tarextract(ff,dd):
    
        #print(f"extracting {ff}") 
        tar = tarfile.open(ff, "r:")
        
        tar.extractall(path=dd)
        tar.close()
# Restore
def enablePrint():
    sys.stdout = sys.__stdout__

def deletefolders(folder,subfolder): 
    shutil.rmtree(folder + os.sep + subfolder)

def processList(folder, bounds,res,yes):
    bbox = BBox(bbox=bounds, crs="EPSG:3413")
    #size = bbox_to_dimensions(bbox, resolution=res)
    east1, north1 = bbox.lower_left
    east2, north2 = bbox.upper_right
    size = round(abs(east2 - east1) / res), round(abs(north2 - north1) / res)
    folderPath = f'{DL_FOLDER}/{folder}'
    if yes == 1:
        print("Still Going")
    if os.path.exists(folderPath):
        logging.info(f"Folder already exists {folderPath}")
        return
    
    try:
        #logging.info(f"Processing folder {folderPath}")
        request1 = SentinelHubRequest(
            evalscript=evalscript1,
            data_folder=folderPath,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL3_OLCI,
                    identifier="OLCI",
                    time_interval=date_range,
                    upsampling="BICUBIC",
                    downsampling="BICUBIC",
                ),
            ],
            responses=[
                SentinelHubRequest.output_response('toa1', MimeType.TIFF),
                SentinelHubRequest.output_response('toa2', MimeType.TIFF),
                SentinelHubRequest.output_response('toa3', MimeType.TIFF),
                SentinelHubRequest.output_response('toa4', MimeType.TIFF),
                SentinelHubRequest.output_response('toa5', MimeType.TIFF),
                SentinelHubRequest.output_response('toa6', MimeType.TIFF),
                SentinelHubRequest.output_response('toa7', MimeType.TIFF),
                SentinelHubRequest.output_response('toa8', MimeType.TIFF),
                SentinelHubRequest.output_response('toa9', MimeType.TIFF),
                SentinelHubRequest.output_response('toa10', MimeType.TIFF),
                SentinelHubRequest.output_response('toa11', MimeType.TIFF),
                SentinelHubRequest.output_response('toa12', MimeType.TIFF),
                SentinelHubRequest.output_response('toa13', MimeType.TIFF),
                SentinelHubRequest.output_response('toa14', MimeType.TIFF),
                SentinelHubRequest.output_response('toa15', MimeType.TIFF),
                SentinelHubRequest.output_response('toa16', MimeType.TIFF),
                SentinelHubRequest.output_response('toa17', MimeType.TIFF),
                SentinelHubRequest.output_response('toa18', MimeType.TIFF),
                SentinelHubRequest.output_response('toa19', MimeType.TIFF),
                SentinelHubRequest.output_response('toa20', MimeType.TIFF),
                SentinelHubRequest.output_response('toa21', MimeType.TIFF),
                
                SentinelHubRequest.output_response('saa', MimeType.TIFF),
                SentinelHubRequest.output_response('vaa', MimeType.TIFF),
                SentinelHubRequest.output_response('vza', MimeType.TIFF),
                SentinelHubRequest.output_response('sza', MimeType.TIFF),
                SentinelHubRequest.output_response('totalozone', MimeType.TIFF),
                SentinelHubRequest.output_response('pixelidOLCI', MimeType.TIFF),
                SentinelHubRequest.output_response('userdata', MimeType.JSON),
            ],
            bbox=bbox,
            size=size,
            config=sh_config,
        )
        
        resp1 = request1.get_data(save_data=True)
        
        request2 = SentinelHubRequest(
            evalscript=evalscript2,
            data_folder=folderPath,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL3_OLCI,
                    identifier="OLCI",
                    time_interval=date_range,
                    upsampling="BICUBIC",
                    downsampling="BICUBIC",
                ),
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL3_SLSTR,
                    identifier="SLSTR",
                    time_interval=date_range,
                    upsampling="BICUBIC",
                    downsampling="BICUBIC",
                ),
            ],
            responses=[
                SentinelHubRequest.output_response('S7', MimeType.TIFF),
                SentinelHubRequest.output_response('S8', MimeType.TIFF),
                SentinelHubRequest.output_response('S9', MimeType.TIFF),
                SentinelHubRequest.output_response('pixelidSLSTR1000', MimeType.TIFF),
                SentinelHubRequest.output_response('userdata', MimeType.JSON),
            ],
            bbox=bbox,
            size=size,
            config=sh_config,
        )
        resp2 = request2.get_data(save_data=True)
        
        
        request3 = SentinelHubRequest(
            evalscript=evalscript3,
            data_folder=folderPath,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL3_OLCI,
                    identifier="OLCI",
                    time_interval=date_range,
                    upsampling="BICUBIC",
                    downsampling="BICUBIC",
                ),
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL3_SLSTR,
                    identifier="SLSTR",
                    time_interval=date_range,
                    upsampling="BICUBIC",
                    downsampling="BICUBIC",
                ),
            ],
            responses=[
                SentinelHubRequest.output_response('S1', MimeType.TIFF),
                SentinelHubRequest.output_response('S5', MimeType.TIFF),
                SentinelHubRequest.output_response('pixelidSLSTR500', MimeType.TIFF),
                SentinelHubRequest.output_response('userdata', MimeType.JSON),
            ],
            bbox=bbox,
            size=size,
            config=sh_config,
        )
        resp3 = request3.get_data(save_data=True)
        
        request4 = SentinelHubRequest(
            evalscript=evalscript4,
            data_folder=folderPath,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.DEM_COPERNICUS_30,
                    identifier="COP_30",
                    upsampling="BICUBIC",
                    downsampling="BICUBIC",
                ),
            ],
            responses=[
                SentinelHubRequest.output_response('dem', MimeType.TIFF),
            ],
            bbox=bbox,
            size=size,
            config=sh_config,
        )
        
        resp4 = request4.get_data(save_data=True)
        
        
    except Exception as e:
        logging.error(e)
        logging.error(folder)
        logging.error(size)
        logging.error(bbox)
        logging.error(date_range)
        if os.path.exists(folderPath):
            logging.info(f'Deleting tile {folder} because of SentinelHub Error')
            shutil.rmtree(folderPath)
            yes = 1

        


class ConcurrentSHRequestExecutor:
    def __init__(self, toProcess):
        self.toProcess = toProcess
        
    def operation(self, chunk):
        processList(round(self.toProcess.id[chunk]) , list(self.toProcess.geometry[chunk].bounds),res,0)
        
    def executeRequests(self):
        with concurrent.futures.ProcessPoolExecutor() as executor:
            executor.map(self.operation, np.arange(0, len(self.toProcess.values)), chunksize=4)
        print("done")


def cloudfilt(profile,scene,cd):
    warnings.filterwarnings("ignore", category=FutureWarning)
    scenespath = glob.glob(scene + os.sep + "*.tif")
    
    if len(scenespath) == 0:
        
        scenespath = glob.glob(scene + os.sep + "*.tiff")
    
    for i,scene in enumerate(scenespath):
        
        name = scene.split(os.sep)[-1]
        
        if name != "SCDA.tif":
            
           
            
            data = rio.open(scene).read(1)
            
            if name == "Snow_Albedo_Sph.tif":
                print(np.nanmean(data)) 
            
            
            data[cd == 255] = np.nan
            data[np.isnan(cd)] = np.nan
            
            with rio.open(scene,'w',**profile) as dst:
                dst.write(data, 1)        

    

def CloudMasking(mainpath,scene):
    
    warnings.filterwarnings("ignore", category=FutureWarning)
    #saving profile metadata only for the first iteration
    meta = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*toa1.tif')
    metaresponse = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*response.tiff')
    if meta:

        cdpath = glob.glob(mainpath + os.sep + scene +  os.sep + "*" + os.sep + "*SCDA.tif")

        cd = rio.open(cdpath[0]).read(1)

        profile = rio.open(meta[0]).profile
        #print(meta[0][:-18])
        cloudfilt(profile,meta[0][:-8],cd)

        try:
            cloudfilt(profile,metaresponse[0][:-13],cd)
        except: 
            logging.info("Error in Meta Response Tiff")
            logging.info(scene)
            logging.info(metaresponse)

            

def nanRemoval(datapath,inpath):
    warnings.filterwarnings("ignore", category=FutureWarning)
    data = rio.open(datapath)
    profile = data.profile
    
    dataz = data.read(1)
    #print("no of nans: ",dataz[np.isnan(dataz)] )
    dataz[np.isnan(dataz)] = np.nanmean(dataz)
    #print("no of zeros: ", dataz[dataz == 0]  )
    dataz[dataz == 0] = np.nanmean(dataz)
    
    
    
    with rio.open(datapath,'w',**profile) as dst:
        dst.write(dataz, 1)            

def mask_sice(sicepath,dempath,scene,usr_p,dlfolder,area):
    
    masktile = usr_p + os.sep + "masks" + os.sep + area + "500m" + os.sep + scene + ".tif"
    #logging.info(f'maskingtile path: {masktile}')
    #print(f'maskingtile path: {masktile}')
    
    xmask,ymask,zmask,projmask = opentiff(masktile)
    datagrid = np.ones_like(zmask) * np.nan
    
    files = glob.glob(sicepath + os.sep + "*.tif")
    dem = glob.glob(dempath + os.sep + "*.tiff")
    scda = glob.glob(dlfolder + os.sep + scene + os.sep + "*"  + os.sep + "SCDA.tif")
    files = files + dem + scda
    
    #logging.info(f"Using Opentiiff on {scene}")
    xdata,ydata,zdata,projdata = opentiff(files[0])   
    
    tree = KDTree(np.c_[xdata.ravel(),ydata.ravel()])   
    for f in files:
      
        zdata = rio.open(f).read(1)
        
        for i,(xmid,ymid) in enumerate(zip(xmask.ravel(),ymask.ravel())):     
                if zmask.ravel()[i] == 220: 
                    dd, ii = tree.query([xmid,ymid],k = 1,p = 2)
                    datagrid.ravel()[i] = zdata.ravel()[ii]
        
        #path = f.split(os.sep)[:-2]
        #name = f.split(os.sep)[-1]
        
        exporttiff(xmask,ymask,datagrid,projdata,f)


def radiometric_calibration(R16path,scene,inpath):
    
    warnings.filterwarnings("ignore", category=FutureWarning)
    '''
    Sentinel-3 Product Notice – SLSTR:
    "Based on the analysis performed to-date, a recommendation has been put forward to users to
    adjust the S5 and S6 reflectances by factors of 1.12 and 1.20 respectively in the nadir view and
    1.15 and 1.26 in the oblique view. Uncertainty estimates on these differences are still to be
    evaluated and comparisons with other techniques have yet to be included."
    
    INPUTS:
        R16: Dataset reader for Top of Atmosphere (TOA) reflectance channel S5.
             Central wavelengths at 1.6um. [rasterio.io.DatasetReader]
        scene: Scene on which to compute SCDA. [string]
        
    OUTPUTS:
        {inpath}/r_TOA_S5_rc.tif: Adjusted Top of Atmosphere (TOA)
                                  reflectance for channel S5.
    '''
    R16 = rio.open(R16path)
    profile_R16 = R16.profile
    factor = 1.12
    R16_data = R16.read(1)
    R16_rc = R16_data*factor
    outpath =  R16path[:-6] 
    with rio.open(outpath + 'S5_rc.tif','w',**profile_R16) as dst:
        dst.write(R16_rc, 1)        

def SCDA_v20(R550, R16, BT37, BT11, BT12, profile, scene, 
             inpath, despath, SICE_toolchain=True):
    warnings.filterwarnings("ignore", category=FutureWarning)
    
    '''
    
    INPUTS:
        inpath: Path to the folder of a given date containing extracted scenes
                in .tif format. [string]
        SICE_toolchain: if True: cloud=255, clear=1
                        if False: cloud=1, clear=0
        profile: Profile to save outputs. [rasterio.profiles.Profile]
        scene: Scene on which to compute the SCDA. [string]
        R550, R16: Top of Atmosphere (TOA) reflectances for channels S1 and S5.
                   Central wavelengths at 550nm and 1.6um. [arrays]
        BT37, BT11, BT12: Gridded pixel Brightness Temperatures (BT) for channels 
                          S7, S8 and S9 (1km TIR grid, nadir view). Central 
                          wavelengths at 3.7, 11 and 12 um. [arrays]
              
    OUTPUTS:
        {inpath}/NDSI.tif: Normalized Difference Snow Index (NDSI) in a 
                           .tif file, stored in {inpath}. [.tif]
        {inpath}/SCDA.tif: Simple Cloud Detection Algorithm (SCDA) results 
                           in a .tif file, stored in {inpath}. 
                           clouds=1, clear=0 [.tif]
         
    '''
    
    
    # Checking for nan - getting mean val. 
    
    #determining the NDSI, needed for the cloud detection
    NDSI=(R550-R16)/(R550+R16)
    
    #NDSIpath = glob.glob(inpath + os.sep + scene + os.sep + * + os.sep + '*NDSI.tif')
    #with rasterio.open(inpath+os.sep+scene+os.sep+'NDSI.tif','w',**profile) as dst:
    #    dst.write(NDSI, 1)
    
    #initializing thresholds
    base=np.empty((R550.shape[0],R550.shape[1]))
    THR=base.copy()
    THR[:]=np.nan
    THRmax=base.copy()
    THRmax[:]=-5.5 
    S=base.copy()
    S[:]=1.1
    
    #masking nan values
    mask_invalid=np.isnan(R550)
    
    #tests 1 to 5, only based on inputs
    t1=ar(R550>0.30)*ar(NDSI/R550<0.8)*ar(BT12<=290)
    t2=ar(BT11-BT37<-13)*ar(R550>0.15)*ar(NDSI >= -0.30)\
       *ar(R16>0.10)*ar(BT12<=293)
    t3=ar(BT11-BT37<-30)
    t4=ar(R550<0.75)*ar(BT12>265)
    t5=ar(R550>0.75)
    
    cloud_detection=t1
    cloud_detection[cloud_detection==False]=t2[cloud_detection==False]
    cloud_detection[cloud_detection==False]=t3[cloud_detection==False]
    
    THR1=0.5*BT12-133
    
    THRmax[t4==False]=-8
    THR=np.minimum(THR1,THRmax)
    S[t5==False]=1.5
    
    #test 6, based on fluctuating thresholds
    t6=ar(BT11-BT37<THR)*ar(NDSI/R550<S)*ar((NDSI>=-0.02) & (NDSI<=0.75))\
       *ar(BT12<=270)*ar(R550>0.18)

    cloud_detection[cloud_detection==False]=t6[cloud_detection==False]
    
    
    #masking nan values
    #cloud_detection[mask_invalid]=True
    
    
    
    if SICE_toolchain:
        cloud_detection = np.where(cloud_detection==True, 255.0, 1.0)
    
    #writing results
    profile_cloud_detection=profile.copy()
    if SICE_toolchain:
        profile_cloud_detection.update(dtype=rio.uint8, nodata=255)
    else:
        profile_cloud_detection.update(dtype=rio.uint8)
    #print(despath + 'SCDA.tif')
    with rio.open(despath + 'SCDA.tif','w',**profile_cloud_detection) as dst:
        dst.write(cloud_detection.astype(np.uint8), 1)
        
    return cloud_detection, NDSI

def SCDA(mainpath,scene):
    
    #saving profile metadata only for the first iteration
    meta = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*S1.tif')
    #pathjohn = mainpath + os.sep + scene + os.sep + "*" + os.sep + '*S1.tif'
    warnings.filterwarnings("ignore", category=FutureWarning)
    #print("metapath: " + pathjohn)
    if meta:

        profile = rio.open(meta[0]).profile

        #calibrating R16
        R16path = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*S5.tif')
        nanRemoval(datapath = R16path[0], inpath = mainpath)
        radiometric_calibration(R16path = R16path[0], scene = scene, inpath = mainpath)


        #loading inputs
        R550path = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*S1.tif')

        nanRemoval(datapath = R550path[0], inpath = mainpath)
        R550=rio.open(R550path[0]).read(1)


        R16path = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*S5_rc.tif')
        R16=rio.open(R16path[0]).read(1)
        
        BT37path = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*S7.tif')
        nanRemoval(datapath = BT37path[0], inpath = mainpath)
        BT37 = rio.open(BT37path[0]).read(1)
        
        BT11path = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*S8.tif')
        nanRemoval(datapath = BT11path[0], inpath = mainpath)
        BT11=rio.open(BT11path[0]).read(1)
        
        BT12path = glob.glob(mainpath + os.sep + scene + os.sep + "*" + os.sep + '*S9.tif')
        nanRemoval(datapath = BT12path[0], inpath = mainpath)
        BT12=rio.open(BT12path[0]).read(1)
        
        #running SCDA v2.0 and v1.4
        cd,NDSI=SCDA_v20(R550 = R550, R16 = R16, BT37 = BT37, BT11 = BT11, BT12 = BT12, scene = scene, profile = profile, inpath = mainpath,despath = BT12path[0][:-6])

        #os.remove(R16path[0])
        #os.remove(R550path[0])

    else: 
        print("Scene is corrupted, Skipping...") 

def multiproc(main,scenes,sicePathsfilt,demPathsfilt,sceneno,usrpath,dlfolder,datecams,area):
            
            try:
                logging.info(f"Processing {scenes}")
                
                SCDA(main,scenes)
                CloudMasking(main,scenes)
                mask_sice(sicePathsfilt,demPathsfilt,sceneno,usrpath,dlfolder,area) 
                get_maps(sicePathsfilt,sicePathsfilt, datecams,sceneno)
                proc(sicePathsfilt,demPathsfilt)
                
            except Exception as e:
                
                logging.info(f"This Scene Would Not Process {scenes}")
                logging.info("Scene error: ")
                logging.info(traceback.format_exc())
                logging.error(e)
    

    

if __name__ == "__main__":       
    
    #set_start_method('spawn', force=True)
    
    warnings.filterwarnings("ignore", category=FutureWarning)
    
    try:
        set_start_method("spawn")
    except:
        pass

    args = parse_arguments()

    date = args.day
    area = args.area
    res = args.res # minimum resolution of data is 300m
    test = args.test
    USR_PATH = os.getcwd()
    BASE_PATH = os.path.abspath('..')
    co = 12 # number of cores used!!!!
    
    

    #External variables
    # Set the date of calculation
    # resolution (m)


    #area of interest
                                     
    tiles_area = BASE_PATH + os.sep + 'masks' + os.sep + 'tiles' + os.sep + area + "_50kmTilesBuffer.geojson"
                                     
    toProcess = gpd.read_file(tiles_area)

    #target projection of the final results
    projection = '3413'

    # log processing parameters - don't log any S3 information
    #logging.info(f'Date: {date}')
    #logging.info(f'AOI: {aoi_polar}')
    #logging.info(f'Projection: {projection}')

    #system settings

    #base folder where the code is located
   
    EVAL_SCRIPT1_PATH = os.path.join(USR_PATH, 'S3Adata.js') 
    EVAL_SCRIPT2_PATH = os.path.join(USR_PATH, 'eval1000Tile.js') 
    EVAL_SCRIPT3_PATH = os.path.join(USR_PATH, 'evalSLSTR500.js') 
    EVAL_SCRIPT4_PATH = os.path.join(USR_PATH, 'dem.js') 

    #delete download folder after processing - will save space but will download all the data for each requwst (otherwise the cached tile data will be used)
    DELETE_DOWNLOAD_FOLDER = False
    
    OUTPUT_DIR =  os.path.join(BASE_PATH, "output") #local folder # will be copied to the local folder of the user requesting the data
    # create logs folder

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR )


    
    logging.info("System configuration ok.")    
    
    try:
        SH_CLIENT_ID = os.environ.get('SH_CLIENT_ID') # Please add your SentinelHub id
        SH_CLIENT_SECRET = os.environ.get('SH_CLIENT_SECRET')  # Please add your SentinelHub id
    except:
        logging.info("Please input your SentinelHub Client and Secret ID in pysicehub.py")
        
    
   

    sh_config = SHConfig()
    sh_config.sh_base_url = "https://creodias.sentinel-hub.com"
    sh_config.download_timeout_seconds=300

    sh_config.sh_client_id = SH_CLIENT_ID
    sh_config.sh_client_secret = SH_CLIENT_SECRET


    # Evalscript
    with open(EVAL_SCRIPT1_PATH, "r") as f:
        evalscript1 = f.read()

    # Evalscript
    with open(EVAL_SCRIPT2_PATH, "r") as f:
        evalscript2 = f.read()

        # Evalscript
    with open(EVAL_SCRIPT3_PATH, "r") as f:
        evalscript3 = f.read()

    with open(EVAL_SCRIPT4_PATH, "r") as f:
        evalscript4 = f.read()    

    
    logging.info("Configuration ok.")    
    
    down = 1
    UTIL_FOLDER = BASE_PATH + os.sep + 'util'
    utc_shift = int(pd.read_csv(UTIL_FOLDER + os.sep + "UTC_TimeShift.csv")[area])
    date_morning = str(8 - utc_shift).zfill(2)
    date_evening = str(18 - utc_shift).zfill(2)
    
    if int(date_evening) > 23:
        date_evening = '23'
    
    date_range = (f'{date}T{date_morning}:00:00', f'{date}T{date_evening}:00:00')

   
    DATE_FOLDER = date.replace("-","_")
    DL_FOLDER =  os.path.join(BASE_PATH,'downloads', str(res), DATE_FOLDER)
    PROCESSED_FOLDER = f'{DL_FOLDER}/processed'
    if down == 1:
        #Remove chunks that are too small to be processed
        MIN_AREA = 0.05 * (50000 * 50000)
        toProcess = toProcess[toProcess.geometry.to_crs('epsg:3413').area > MIN_AREA]
        
        if os.path.exists(DL_FOLDER):
            subf = os.listdir(DL_FOLDER)
            mainf = [DL_FOLDER for i in range(len(subf))]
            logging.info(f'Deleting Folder: {DL_FOLDER}')
            with get_context("spawn").Pool(co) as p:
                p.starmap(deletefolders,zip(mainf,subf))
                p.close()
            logging.info(f'Folder {DL_FOLDER} deleted')


        # make concurrent calls using all the available processor
        logging.info(f'Processing tiles. Number of tiles to process: {len(toProcess.id)}')
        
        # This downloads all the tiles and do some proc
        executor = ConcurrentSHRequestExecutor(toProcess)
        executor.executeRequests()  

        logging.info('Done')

        # check if all the tiles were correctly downloaded - sometimes some fail in the multi-thread mode
        filenamesList = glob.glob(f'{DL_FOLDER}/*/*/response.tar')
        missing = [];

        for id in toProcess.id:
            id = round(id)
            isPresent = False
            for f in filenamesList:
                if str(id) in f: 
                    isPresent = True
                    continue
            if not isPresent:    
                missing.append(id)
                logging.debug(f"Id is missing: {id}")

        notProcessed = toProcess[toProcess.id.isin(missing)]

        logging.info(f'Number of failed tiles: {len(missing)}')

        # compute missing tile individually - much slower than multy-threaded
        logging.info('Computing failed tiles')
        for idx in notProcessed.index: 
            id = round(notProcessed.id[idx])
            bounds = list(notProcessed.loc[idx].geometry.bounds)
            
                
            processList(id, bounds,res,0)    

        logging.info('Done')


        logging.info('Extracting .tar responses')
        filenamesList = glob.glob(f'{DL_FOLDER}/*/*/response.tar')
        dest = [file.replace('response.tar', '') for file in filenamesList]

        with get_context("spawn").Pool(co) as p:     
            p.starmap(tarextract,zip(filenamesList,dest))
            p.close()

        logging.info("Done")
    
    skip = 0

    bands = np.arange(1,22)
    
    bands_sice = np.concatenate((bands[bands < 12],bands[bands > 15]))
    
    toa = [("toa" + str(b) + ".tif") for b in bands]
    toa_out = [("r_TOA_" + str(b).zfill(2) + ".tif") for b in bands]
    alb_spec = [("albedo_spectral_planar_" + str(b).zfill(2) + ".tif") for b in bands_sice]
    alb_spec_out = [("albedo_spectral_planar_" + str(b).zfill(2) + ".tif") for b in bands_sice]
    rBRR_spec = [("rBRR_" + str(b).zfill(2)  + ".tif") for b in bands_sice]
    rBRR_spec_out = [("rBRR_" + str(b).zfill(2) + ".tif") for b in bands_sice]
    
    misc_prod = ['th.tif','grain_diameter.tif','snow_specific_area.tif','sza.tif','vza.tif','saa.tif','vaa.tif','albedo_bb_planar_sw.tif',\
                 'albedo_bb_spherical_sw.tif','isnow.tif','AOD_550.tif','ANG.tif','r0.tif','SCDA.tif','al.tif','O3_SICE.tif',\
                 'factor.tif','cv1.tif','cv2.tif','pixelidOLCI.tif','pixelidSLSTR500.tif']
               
    misc_prod_out = ['threshold.tif','grain_diameter.tif','snow_specific_surface_area.tif','sza.tif','vza.tif','saa.tif','vaa.tif',\
                  'albedo_bb_planar_sw.tif','albedo_bb_spherical_sw.tif','isnow.tif','AOD_550.tif','ANG.tif','r0.tif','cloud_mask.tif',\
                    'al.tif','O3_SICE.tif','factor.tif','cv1.tif','cv2.tif','pixelidOLCI.tif','pixelidSLSTR500.tif']
    
    products = misc_prod + toa + alb_spec + rBRR_spec
    
    out = misc_prod_out + toa_out + alb_spec_out + rBRR_spec_out

   
    scenes = os.listdir(DL_FOLDER)
    main = [DL_FOLDER for x in range(len(scenes))]
    
    sicePaths = glob.glob(DL_FOLDER + "/*/*/*toa1.tif")
    demPaths = glob.glob(DL_FOLDER + "/*/*/*response.tiff")


    sicePathsfilt = [[s[:-8]  for s in sicePaths if (s.split(os.sep)[-3]==d.split(os.sep)[-3])] for d in demPaths]
    sicePathsfilt = [item for sublist in sicePathsfilt for item in sublist]

    demPathsfilt = [[d[:-13]  for s in sicePaths if (s.split(os.sep)[-3]==d.split(os.sep)[-3])] for d in demPaths]
    demPathsfilt = [item for sublist in demPathsfilt for item in sublist]

    sceneno = [[s.split(os.sep)[-3]  for s in sicePaths if (s.split(os.sep)[-3]==d.split(os.sep)[-3])] for d in demPaths]
    sceneno = [item for sublist in sceneno for item in sublist]

    usrpath = [BASE_PATH for ii in range(len(sceneno))]
    area_list =  [area for ii in range(len(sceneno))]
    dlfolder = [DL_FOLDER for ii in range(len(sceneno))]
    datecams = [date for x in range(len(demPathsfilt))]

    

    with get_context("spawn").Pool(co) as p:
            logging.info('Executing pysicehub')
            p.starmap(multiproc,zip(main,scenes,sicePathsfilt,demPathsfilt,sceneno,usrpath,dlfolder,datecams,area_list))
            p.close()
            p.join()
            logging.info("Done")

    proproduct = [PROCESSED_FOLDER for ii in range(len(products))]
    dlproduct = [DL_FOLDER for ii in range(len(products))]
    
    if not os.path.exists(PROCESSED_FOLDER):
        os.makedirs(PROCESSED_FOLDER)
    
    with get_context("spawn").Pool(co) as p:     
            p.starmap(multi_merge,zip(products,dlproduct,proproduct))
            p.close()
            p.join()
            logging.info("Done")

  
    resultsDataPath = os.path.join(USR_PATH, PROCESSED_FOLDER)
    processedDataPath = os.path.join(USR_PATH, PROCESSED_FOLDER)
    for product,out in zip(products,out):
            srcFile = processedDataPath + "/" + product.replace(".tif", "_merged.tif")
            destFile = processedDataPath + "/" + out
            if os.path.exists(srcFile):
                os.rename(srcFile, destFile)

    finalOutput = f'{OUTPUT_DIR}/sice_{res}_{DATE_FOLDER}'

    if os.path.exists(finalOutput):
            shutil.rmtree(finalOutput)
            logging.info(f'Folder {finalOutput} deleted')

    logging.info(f'Copying results to {finalOutput}')
    shutil.copytree(resultsDataPath, finalOutput)

    if DELETE_DOWNLOAD_FOLDER and os.path.exists(DL_FOLDER):
        subf = os.listdir(DL_FOLDER)
        mainf = [DL_FOLDER for i in range(len(subf))]
        logging.info(f'Deleting Folder: {DL_FOLDER}')
        with get_context("spawn").Pool(co) as p:     
            p.starmap(deletefolders,zip(mainf,subf))
        #shutil.rmtree(DL_FOLDER)
        logging.info(f'Folder {DL_FOLDER} deleted')


    logging.info('Converting to netcdf and uploading to Dataverse')
    finalOutput =  f'{OUTPUT_DIR}/sice_{res}_{DATE_FOLDER}'
    dataverse_upload(finalOutput,area)

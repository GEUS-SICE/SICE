"""
Created on Fri Oct  7 08:47:58 2022

@author: Rasmus Bahbah Nielsen (rabni@geus.dk)

"""
############## Description ##############
#
# This Main script downloads the CAMS AOD in 550nm and 865nm data for a specific date and
# use a N Nearest Neighbour with Gaussian RBF computed weights 
# to interpolate 550 nm and the Angstrom Exponent on the SICE grid. 
# creating two outputs "AOD_550.tif" and "ANG.tif"
#
# The Angstrom Exponent Equation:
#    
# alpha = -(log(tau_l1/tau_l2) / log(l1/l2))
#
# Where tau_l1 is the AOD at wavelength 1 (550nm)
# and tau_l2 is the AOD at wavelength 2 (865nm), 
# l1 is wavelength 1 (550nm) , l2 is wavelength 2 (865nm)
#
# This Version use the 100 nearest neighbours, 
# and it computes two set of Gaussian RBF weights:
#
# w_x = exp((epsX * d_x)**2)
# w_y = exp((epsY * d_y)**2)
#
# where d_x is the distance in the x direction between the grid point and its N neighbours.
# and d_y is the distance in the y direction between the grid point and its N neighbours. 
#
# epsX and epsY are the shape parameters that controls how much the RBF 
# penalizes values that are far away in the x and y direction.
#
# so if epsX -> 0 then points far (x->inf) away will have weights w_x -> 1
#    if epsX -> inf then points close (x->0) will have weights w_x -> 0
#
# epsX is deliberately set higher than epsY, because the original projection in the AOD550 
# grid is in lon and lat. The x distances between data points are therefore smaller, 
# because we are close to the north pole. 
#
# The total weights are:
#
# w = w_x * w_y
#
############## Inputs ##############
#
# -g | --grid          SICE grid input path         
# -d | --day           day of the CAMS data
# -o | --output        output path of the two tif outputs
#



import argparse
import sys
import os
import glob
from pyproj import CRS,Transformer
import cdsapi
from scipy.spatial import KDTree
import rasterio as rio
import xarray as xr
import numpy as np
import time
import datetime as dt
from rasterio.transform import Affine
from pyproj import CRS as CRSproj
import rasterio
import warnings
import logging
import zipfile
import shutil
WGSProj = CRS.from_string("+init=EPSG:4326")
PolarProj = CRS.from_string("+init=EPSG:3413")

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
    

def blockPrint():
    sys.stdout = open(os.devnull, 'w')

def enablePrint():
    sys.stdout = sys.__stdout__

if sys.version_info < (3, 4):
    raise "must use python 3.6 or greater"


def parse_arguments():
        parser = argparse.ArgumentParser(description='main excicuteable for the SICE CAMS Aerosol data and regridding')
        parser.add_argument("-g","--grid", type=str,help="Please input the grid file name")
        parser.add_argument("-d","--day", type=str,default='default',help="Please input the day you want to proces")
        parser.add_argument("-o","--outputfolder", type=str, help="Please input the output folder for the CAMS Data")
        args = parser.parse_args()
        return args


def APIrequest(date,lead,scene,area):
    
    
    
    c = cdsapi.Client(wait_until_complete=False)
    
    try:
        c.retrieve(
                'cams-global-atmospheric-composition-forecasts',
                {
                    'date':  date + '/' + date,
                    'type': 'forecast',
                    'format': 'grib',
                    'variable': [
                        'total_aerosol_optical_depth_550nm', 'total_aerosol_optical_depth_670nm',
                    ],
                    'time': '00:00',
                    'leadtime_hour': lead,
                    'area': area,
                },
                'Aerosol_' + scene + '.grib')

    except: 
        print(f"something went wrong, could not download for tile {scene}")
        return
    return

def OpenRaster(filename):
    
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



def ExportGeoTiff(x,y,z,crs,path,filename):
    
    "Input: xgrid,ygrid, data paramater, the data projection, export path, name of tif file"
    
    resx = (x[0,1] - x[0,0])
    resy = (y[1,0] - y[0,0])
    transform = Affine.translation((x.ravel()[0]),(y.ravel()[0])) * Affine.scale(resx, resy)
    
    if resx == 0:
        resx = (x[0,0] - x[1,0])
        resy = (y[0,0] - y[0,1])
        transform = Affine.translation((y.ravel()[0]),(x.ravel()[0])) * Affine.scale(resx, resy)
    
    with rasterio.open(
    path + os.sep + filename,
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
    
    return None 

def get_maps(grid,output,day,scene):
    
    ##### Setting Input Parameters ##### 
    
    blockPrint()
    GridFolder = grid + os.sep + "toa1.tif"
    #print(f"GRID: {GridFolder}")
    AerosolFolder = output
    
    if not day:
    
        date = (dt.date.today() - dt.timedelta(1)).strftime("%Y-%m-%d")
        lead = "24"
    
    else:
        
        date = day
        lead = "0"
        
        
    #####  Creating Coordinate Transformations #####
    
    wgs_data = Transformer.from_proj(WGSProj, PolarProj) 
    polar_data = Transformer.from_proj(PolarProj ,WGSProj) 
   
    ##### Importing SICE Grid and Setting NaN Values, and transform to epsg 3413 if necessary #####
    
    gridx, gridy, gridz, DataProj = OpenRaster(GridFolder)
    
    if WGSProj == DataProj:
        
        LatS = np.nanmin(gridy.ravel()) - 1
        lonW = np.nanmin(gridx.ravel()) - 1
        LatN = np.nanmax(gridy.ravel()) + 1
        lonE = np.nanmax(gridx.ravel()) + 1
        
        area = [LatS, lonW, LatN, lonE]
        gridx,gridy = wgs_data.transform(gridx, gridy)
        #print("John")
        
    else:
        
        gridx,gridy = polar_data.transform(gridx, gridy)
        
        LatS = np.nanmin(gridy.ravel()) - 1
        lonW = np.nanmin(gridx.ravel()) - 1
        LatN = np.nanmax(gridy.ravel()) + 1
        lonE = np.nanmax(gridx.ravel()) + 1
        
        area = [LatS, lonW, LatN, lonE]
        gridx,gridy = wgs_data.transform(gridx, gridy)
        
    
    resx = abs(gridx[0,1] - gridx[0,0])
    
    #gridz[gridz < -10000] = np.nan
    
    ##### Downloading Data from the CAMS Website #####
  
    #logging.info(f"cams date:  {date}")
    #logging.info(f"cams area:  {area}")
    #logging.info(f"cams lead:  {lead}")
    base_folder = os.getcwd()
    down_folder = base_folder + os.sep + scene
    
    if os.path.exists(down_folder):
        shutil.rmtree(down_folder)
        os.mkdir(down_folder)
    else:
        os.mkdir(down_folder)
    
    
    c = cdsapi.Client(key='13901:b4109228-0834-4e2e-8890-82b29fd64c9c', url='https://ads.atmosphere.copernicus.eu/api/v2')
    c.retrieve(
                        'cams-global-atmospheric-composition-forecasts',
                        {
                            'date':  date + '/' + date,
                            'type': 'forecast',
                            'format': 'netcdf_zip',
                            'variable': [
                                'total_aerosol_optical_depth_550nm', 'total_aerosol_optical_depth_670nm',
                            ],
                            'time': '12:00',
                            'leadtime_hour': lead,
                            'area': area,
                        },
                        down_folder + os.sep + 'Aerosol_' + scene + '.netcdf_zip')
    
    
    with zipfile.ZipFile(down_folder + os.sep + 'Aerosol_' + scene + '.netcdf_zip', 'r') as zip_ref:
        zip_ref.extractall(down_folder)
    
    ##### Opening Dataset and Changing to EPSG:3413 Proj #####
    
    ds = xr.open_dataset(down_folder + os.sep + 'data.nc')
    
    lon = np.array(ds.longitude)
    lat = np.array(ds.latitude)
    aod550 = np.array(ds.aod550[0])
    aod670 = np.array(ds.aod670[0])
    
    lon, lat = np.meshgrid(lon, lat)
    
    xx, yy = wgs_data.transform(lon, lat)

    ##### Filtering Data With a 100 km Buffer #####
    
    buffer = 100000
    
    bbmsk = (xx <= (max(gridx.ravel()) + buffer)) & (xx >= (min(gridx.ravel()) - buffer))\
          & (yy >= (min(gridy.ravel()) - buffer)) & (yy <= (max(gridy.ravel()) + buffer))
        
    
    xx = xx[bbmsk]
    yy = yy[bbmsk]
    aod550 = aod550[bbmsk]
    aod670 = aod670[bbmsk]
    
    ds.close()
    
    if os.path.exists(down_folder) :
        shutil.rmtree(down_folder)
    
    #os.chdir(main_folder)
    
    ##### Computing Angstrom Parameter #####
    
    ang = -(np.log(aod550 / aod670) / np.log((550 * 10**-9) / (670 * 10**-9)))
    
    
    ##### Nearest Neighbour Weighted Interpolation #####

    gridaod550 = np.ones_like(gridz) * gridz
    gridang = np.ones_like(gridz) * gridz
    
    tree = KDTree(np.transpose(np.array([xx,yy])))
    
    epsX = (7 * 10**-5) # These constants are Found Empiracally, dont touch
    epsY = (2 * 10**-5) # These constants are Found Empiracally, dont touch
    
    logging.info("Regridding and Interpolating Aerosol Data....")
    
    for i,(xmid,ymid) in enumerate(zip(gridx.ravel(),gridy.ravel())):
        
            dd, ii = tree.query([xmid,ymid],k = 100,p = 1)
            
            ii = ii[dd < np.inf]
            dd = dd[dd < np.inf]
            
            distX = abs(xmid - xx[ii])
            distY = abs(ymid - yy[ii])
            
            if (len(ii) == 0) or (np.isnan(gridaod550.ravel()[i])) or (len(aod550[ii]) < 2):
                
                
                gridaod550.ravel()[i] = np.nan
                gridang.ravel()[i] = np.nan
               
            else: 
                
                w_x = np.exp(-(epsX * distX)**2)
                w_y = np.exp(-(epsY * distY)**2)
                
                w = w_y * w_x
               
                gridaod550.ravel()[i] = np.average(aod550[ii], weights = w)
                gridang.ravel()[i] = np.average(ang[ii], weights = w)
                
            
    ##### Exporting Data to two Tiff files #####
    
    #gridx, gridy = polar_data.transform(gridx, gridy)
        
    ExportGeoTiff(gridx, gridy, gridaod550, PolarProj, AerosolFolder, "AOD_550.tif")
    ExportGeoTiff(gridx, gridy, gridang, PolarProj, AerosolFolder, "ANG.tif")

            

            


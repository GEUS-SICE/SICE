# -*- coding: utf-8 -*-
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
from pyproj import CRS,Transformer
import cdsapi
from scipy.spatial import KDTree
import xarray as xr
import numpy as np
import datetime as dt
from rasterio.transform import Affine
import rasterio
WGSProj = CRS.from_string("+init=EPSG:4326")


if sys.version_info < (3, 4):
    raise "must use python 3.6 or greater"
    

def parse_arguments():
        parser = argparse.ArgumentParser(description='main excicuteable for the SICE CAMS Aerosol data and regridding')
        parser.add_argument("-g","--grid", type=str,help="Please input the grid file name")
        parser.add_argument("-d","--day", type=str,default='default',help="Please input the day you want to proces")
        parser.add_argument("-o","--outputfolder", type=str, help="Please input the output folder for the CAMS Data")
        args = parser.parse_args()
        return args
    

def OpenRaster(filename):
    
   "Input: Filename of GeoTIFF File "
   "Output: xgrid,ygrid, data paramater of Tiff, the data projection"
   
   
   
   da = xr.open_rasterio(filename)
   proj = CRS.from_string(da.crs)

   transform = Affine(*da.transform)
   elevation = np.array(da.variable[0],dtype=np.float32)
   nx,ny = da.sizes['x'],da.sizes['y']
   x,y = np.meshgrid(np.arange(nx,dtype=np.float32), np.arange(ny,dtype=np.float32)) * transform
   
   
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

if __name__ == "__main__":
    
    
    ##### Setting Input Parameters ##### 
    
    args = parse_arguments()
    
    GridFolder = args.grid + os.sep + "num_scenes.tif"
    AerosolFolder = args.outputfolder
    
    if args.day == "default":
    
        date = (dt.date.today() - dt.timedelta(1)).strftime("%Y-%m-%d")
        lead = "24"
    else:
        
        date = args.day
        lead = "0"
   
        
    
    
    ##### Importing SICE Grid and Setting NaN Values #####
    
    gridx, gridy, gridz, DataProj = OpenRaster(GridFolder)
    
    resx = abs(gridx[0,1] - gridx[0,0])
    
    
    
    gridz[gridz < -10000] = np.nan
    
    ##### Downloading Data from the CAMS Website #####
    
    c = cdsapi.Client()
    try:
        c.retrieve(
            'cams-global-atmospheric-composition-forecasts',
            {
                'date':  date + '/' + date,
                'type': 'forecast',
                'format': 'grib',
                'variable': [
                    'total_aerosol_optical_depth_550nm', 'total_aerosol_optical_depth_865nm',
                ],
                'time': '00:00',
                'leadtime_hour': lead,
                'area': [
                    90, -70, 59,
                    -15,
                ],
            },
            'Aerosol.grib')
        
    except:
        
        print("Couldn't Download Data from CAMS, might be a server problem - Exiting...")
        quit()
        
    
    
    ##### Opening Dataset and Changing to EPSG:3413 Proj #####
    
    ds = xr.open_dataset('Aerosol.grib', engine='cfgrib')
    
    lon = np.array(ds.longitude)
    lat = np.array(ds.latitude)
    aod550 = np.array(ds.aod550)
    aod865 = np.array(ds.aod865)
    
    lon, lat = np.meshgrid(lon, lat)
    
    wgs_data = Transformer.from_proj(WGSProj, DataProj)
    
    xx, yy = wgs_data.transform(lon, lat)
    

    ##### Filtering Data With a 100 km Buffer #####
    
    buffer = 100000
    
    bbmsk = (xx <= (max(gridx.ravel()) + buffer)) & (xx >= (min(gridx.ravel()) - buffer))\
          & (yy >= (min(gridy.ravel()) - buffer)) & (yy <= (max(gridy.ravel()) + buffer))
        
    
    xx = xx[bbmsk]
    yy = yy[bbmsk]
    aod550 = aod550[bbmsk]
    aod865 = aod865[bbmsk]
    
    ##### Computing Angstrom Parameter #####
    
    ang = -(np.log(aod550 / aod865) / np.log(550 * 10**-9 / 865 * 10**-9))
    
    
    ##### Nearest Neighbour Weighted Interpolation #####

    gridaod550 = np.ones_like(gridz) * gridz
    gridang = np.ones_like(gridz) * gridz
    
    tree = KDTree(np.transpose(np.array([xx,yy])))
    
    epsX = (7 * 10**-5) # These constants are Found Empiracally, dont touch
    epsY = (2 * 10**-5) # These constants are Found Empiracally, dont touch
    
    print("Regridding and Interpolating Aerosol Data....")
    
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
        
    ExportGeoTiff(gridx, gridy, gridaod550, DataProj, AerosolFolder, "AOD_550.tif")
    ExportGeoTiff(gridx, gridy, gridang, DataProj, AerosolFolder, "ANG.tif")
            
            
            
            
            

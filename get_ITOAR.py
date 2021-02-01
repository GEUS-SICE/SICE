# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, GEUS (Geological Survey of Denmark and Greenland)

Computes the Intrinsic Top of Atmosphere Reflectance (ITOAR) from effective 
Solar Zenith Angles (SZA) and Observation Zenith Angles (OZA) for a given mosaic
and given bands using ArcticDEM-derived slopes and aspects.
        
"""

import numpy as np
import rasterio
import os
import argparse
from osgeo import gdal, gdalconst


parser = argparse.ArgumentParser()
parser.add_argument('inpath')
parser.add_argument('inpath_adem')

args = parser.parse_args()

# slope threshold in degrees to create slope_flag
# Default is set to 15° based on the "small slope approximation" 
# (Picard et al, 2020)
slope_thres = 15
    
    
def get_effective_angle(variable):
    '''
    
    Determines effective Solar and Observation Zenith angles to compute the 
    Intrinsic BOA Reflectance (ITOAR).
    
    INPUTS:
        variable: name of the variable to compute (here SZA or OZA) [string]
    
    OUTPUTS:
        {variable}_eff: effective angles [array]
        slope_flag: slope mask based on the "small slope approximation" 
                     (Picard et al, 2020). 1 for slope<=threshold, 
                     255 (no data) for slope>threshold [array]
        {variable}_eff.tif: tiff file containing the effective angles [.tif] 
        if variable is set to SZA:
            slope.tif: tiff file containing the slope [.tif]
            slope_flag.tif: tiff file containing the slope_flag [.tif] 
            aspect.tif: tiff file containing the slope aspect [.tif]
        
    '''
    
    # load variables
    try:
        angle_name = variable + '.tif'
        angle = rasterio.open(args.inpath + variable + '.tif').read(1)
    except:
        print('ERROR: %s is missing' % angle_name)
        return
    try:
        saa = rasterio.open(args.inpath + 'SAA.tif').read(1)
    except:
        print('ERROR: SAA.tif is missing')
        return
    
    # load slope and aspect
    slope = rasterio.open(args.inpath_adem + 'Greenland_S.tif').read(1)
    aspect = rasterio.open(args.inpath_adem + 'Greenland_A.tif').read(1)
    
    # create a flag based on the "small slope approximation" 
    slope_flag = slope.copy()
    slope_flag[np.where(slope <= slope_thres)] = 1
    slope_flag[np.where(slope > slope_thres)] = 255
    
    # convert slope, aspect, angle and SAA to radians
    angle_rad = np.deg2rad(angle)
    saa_rad = np.deg2rad(saa)
    slope_rad = np.deg2rad(slope)
    aspect_rad = np.deg2rad(aspect)
    
    # compute effective angle
    mu = np.cos(angle_rad) * np.cos(slope_rad) + np.sin(angle_rad) * np.sin(slope_rad) * \
               np.cos(saa_rad - aspect_rad)
               
    eff = np.arccos(mu)
    angle_eff = np.rad2deg(eff)

    # load initial metadata to save the output
    profile = rasterio.open(args.inpath + variable + '.tif', 'r').profile
    angle_eff = np.nan_to_num(angle_eff)  # nan no data don't pass
    # profile.update(nodata=0)

    # write output file
    output_filename = args.inpath + variable + '_eff' + '.tif'
    
    try:
        with rasterio.open(output_filename, 'w', **profile) as dst:
            dst.write(angle_eff, 1)
            
    except ValueError:
        profile = {k: v for k, v in profile.items() if k not in 
                   ['blockxsize', 'blockysize']}
        with rasterio.open(output_filename, 'w', **profile) as dst:
            dst.write(angle_eff, 1)

    # write slope_flag 
    profile.update(nodata=255)
    
    slope_flag_filename = args.inpath + 'slope_flag_' + str(slope_thres) \
                          + '_degrees.tif'
    
    with rasterio.open(slope_flag_filename, 'w', **profile) as dst:
        dst.write(slope_flag, 1)   
    
    # return slope, aspect and slope flag only for SZA (only once)
    if variable == 'SZA':
        return angle_eff, slope, aspect, slope_flag
    
    if variable == 'OZA':
        return angle_eff


def get_ITOAR(slope, aspect):
    '''

    Determines the Intrinsic Top Of Atmosphere Reflectance (ITOAR) for given bands 
    as inputs for sice.py.
    
    INPUTS:
        slope: slope raster [array]
        aspect: slope aspect raster [array]
    
    OUTPUTS:
        ir_TOA_{band_num}.tif: tiff file containing the intrinsic TOA for each
                              band_num [.tif] 
                              
    '''
    
    # load solar and viewing zenith angles (flat)
    sza = rasterio.open(args.inpath + 'SZA.tif').read(1)
    oza = rasterio.open(args.inpath + 'OZA.tif').read(1)
    
    # load solar azimuth angle (flat)
    saa = rasterio.open(args.inpath + 'SAA.tif').read(1)
    
    # load TOAR (flat)
    toar17 = rasterio.open(args.inpath + 'r_TOA_17.tif').read(1)
    toar21 = rasterio.open(args.inpath + 'r_TOA_21.tif').read(1)
    # save profile as base for ITOAR file
    profile = rasterio.open(args.inpath + 'r_TOA_21.tif').profile 
    
    # compute ITOARs
    def compute_ITOAR(toar):
        
        mu0 = np.cos(np.deg2rad(sza))
        mu = np.cos(np.deg2rad(oza))
        mu0_ov = mu0 * np.cos(np.deg2rad(slope)) + np.sin(np.deg2rad(sza))\
            * np.sin(np.deg2rad(slope)) * np.cos(np.deg2rad(saa) - np.deg2rad(aspect))

        itoar = toar * mu0 / mu0_ov
        
        return itoar
    
    itoar17 = compute_ITOAR(toar17)
    itoar21 = compute_ITOAR(toar21)
    
    # save ITOARs
    with rasterio.open(args.inpath + 'ir_TOA_17.tif', 'w', **profile) as dst:
        dst.write(itoar17, 1)
    with rasterio.open(args.inpath + 'ir_TOA_21.tif', 'w', **profile) as dst:
        dst.write(itoar21, 1)

    
# get effective SZA and OZA
SZA_eff, slope, aspect, slope_flag = get_effective_angle(variable='SZA')
OZA_eff = get_effective_angle(variable='OZA')

# get ITOAR 
get_ITOAR(slope, aspect)

# remove initial angles
os.remove(args.inpath + 'SZA.tif')
os.remove(args.inpath + 'OZA.tif')
os.remove(args.inpath + 'r_TOA_21.tif')
os.remove(args.inpath + 'r_TOA_17.tif')

# rename corrected angles
os.rename(args.inpath + 'SZA_eff.tif', args.inpath + 'SZA.tif')
os.rename(args.inpath + 'OZA_eff.tif', args.inpath + 'OZA.tif')
os.rename(args.inpath + 'ir_TOA_21.tif', args.inpath + 'r_TOA_21.tif')
os.rename(args.inpath + 'ir_TOA_17.tif', args.inpath + 'r_TOA_17.tif')

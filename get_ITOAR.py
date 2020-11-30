# -*- coding: utf-8 -*-
"""
Created on Fri Jan 17 08:45:17 2020

@author: Adrien Wehrlé, GEUS (Geological Survey of Denmark and Greenland)


Computes the Intrinsic Top of Atmosphere Reflectance (ITOAR) for a given scene
and given bands using ArcticDEM-derived slopes and aspects.

INPUTS:
    inpath: path to the folder containing the desired S3 scene processed using the 
            2nd step of SICE processing pipeline (https://github.com/mankoff/SICE/) [string]
    inpath_adem: path to the folder containing regional ArcticDEM derived 
                 slopes and aspects [string]
    region: region over which the toolchain is run [string]
    slope_thres: slope threshold in degrees to create slope_flag. Default 
                     is set to 15° based on the "small slope approximation" 
                     (Picard et al, 2020) [int]
    outpath: path where to save {var}_eff.tif [string]
    
    WARNING: SZA.tif, OZA.tif, SAA.tif and r_TOA_{band_num}.tif are needed 
             in each scene folder in order to complete the correction.
             
    
        
OUTPUTS:
    for a given scene:
        slope.tif: tiff file containing the slope [.tif]
        slope_flag.tif: tiff file containing slope_flag based on the "small slope
                        approximation" (Picard et al, 2020) [.tif]
        aspect.tif: tiff file containing the aspect [.tif]
        SZA_eff.tif: tiff file containing the effective solar zenith angle [.tif]
        OZA_eff.tif: tiff file containing the viewing solar zenith angle [.tif]
        ir_TOA_{band_num}.tif: tiff file containing the slope-corrected TOA for each
                               band_num [.tif] 
        
"""

import numpy as np
import rasterio
import os
import argparse
from osgeo import gdal, gdalconst


parser = argparse.ArgumentParser()
parser.add_argument('inpath')
parser.add_argument('inpath_dem')

args = parser.parse_args()

region = 'Greenland'
slope_thres = 15
inpath = args.inpath
inpath_adem = args.inpath_dem
outpath = inpath
    
    
def get_effective_angle(var, inpath, outpath, inpath_adem=inpath_adem, 
                        region=region, slope_thres=slope_thres):
    '''
    
    Determines effective solar/viewing angles to compute the Intrinsic BOA Reflectance (Itoar).
    
    INPUTS:
        var: name of the variable to compute [string]
        inpath: path to the folder containing the variables ({var} and SAA needed) [string]
        inpath_adem: path to the folder containing regional ArcticDEM-derived 
                     slopes and aspects [string]
        region: region over which the toolchain is run [string]
        slope_thres: slope threshold in degrees to create slope_flag. Default 
                     is set to 15° based on the "small slope approximation" 
                     (Picard et al, 2020). 1 for slope<=slope_thres, 
                     255 (no data) for slope>slope_thres [int]
        outpath: path where to save {var}_eff.tif [string]
    
    OUTPUTS:
        {var}_eff: effective angles [array]
        slope_flag: slope mask based on the "small slope approximation" 
                     (Picard et al, 2020). 1 for slope<=threshold, 
                     255 (no data) for slope>threshold [array]
        {var}_eff.tif: tiff file containing the effective angles [.tif] 
        if variable is set to SZA:
            slope.tif: tiff file containing the slope [.tif]
            slope_flag.tif: tiff file containing the slope_flag [.tif] 
            aspect.tif: tiff file containing the slope aspect [.tif]
        
    '''
    
    # loading variables
    try:
        angle_name = var + '.tif'
        angle = rasterio.open(inpath + var + '.tif').read(1)
    except:
        print('ERROR: %s is missing' % angle_name)
        return
    try:
        saa = rasterio.open(inpath + 'SAA.tif').read(1)
    except:
        print('ERROR: SAA.tif is missing')
        return
    
    def resample_clip_adem(var, inpath=inpath, inpath_adem=inpath_adem, 
                           outpath=outpath, reg=region):
        '''
        
        Resamples and clips ArcticDEM derived slopes and aspects to match S3Snow
        outputs.
        
        INPUTS:
            var: name of the variable to compute ("slope" or "aspect") [string]
            inpath: path to the folder containing the variables (var, height and saa needed) [string]
            inpath_adem: path to the folder containing regional ArcticDEM derived 
                         slopes and aspects [string]
            outpath: path where to save slope.tif and aspect.tif [string]
                         
        OUTPUTS: 
            if var is set to slope: 
                {outpath}/slope.tif: Resampled and clipped ArcticDEM derived slopes [.tif]
            if var is set to slope: 
                {outpath}/aspect.tif: Resampled and clipped ArcticDEM derived aspects [.tif]
        
        '''
            
        # source
        src_filename = inpath_adem + reg + '_arcticdem_' + var + '.tif'
        src = gdal.Open(src_filename, gdalconst.GA_ReadOnly)
        src_proj = src.GetProjection()
        src_geotrans = src.GetGeoTransform()
        
        # raster to match
        match_filename = inpath+angle_name
        match_ds = gdal.Open(match_filename, gdalconst.GA_ReadOnly)
        match_proj = match_ds.GetProjection()
        match_geotrans = match_ds.GetGeoTransform()
        wide = match_ds.RasterXSize
        high = match_ds.RasterYSize
        
        # output/destination
        dst_filename = inpath + var + '.tif'
        dst = gdal.GetDriverByName('Gtiff').Create(dst_filename, wide, high, 1, 
                                                   gdalconst.GDT_Float32)
        dst.SetGeoTransform(match_geotrans)
        dst.SetProjection(match_proj)
        
        # run
        gdal.ReprojectImage(src, dst, src_proj, match_proj, gdalconst.GRA_NearestNeighbour)
        
    # running resample_clip_adem()
    resample_clip_adem(var='slope')
    resample_clip_adem(var='aspect')
    
    # loading slope and aspect
    slope = rasterio.open(inpath + 'slope.tif').read(1)
    aspect = rasterio.open(inpath + 'aspect.tif').read(1)
    
    # creating a flag based on the "small slope approximation" 
    slope_flag = slope.copy()
    slope_flag[np.where(slope <= slope_thres)] = 1
    slope_flag[np.where(slope > slope_thres)] = 255
    
    # converting slope, aspect, angle and SAA to radians
    angle_rad = np.deg2rad(angle)
    saa_rad = np.deg2rad(saa)
    slope_rad = np.deg2rad(slope)
    aspect_rad = np.deg2rad(aspect)
    
    # calculating effective angle
    mu = np.cos(angle_rad) * np.cos(slope_rad) + np.sin(angle_rad) * np.sin(slope_rad) * \
               np.cos(saa_rad - aspect_rad)
               
    eff = np.arccos(mu)
    angle_eff = np.rad2deg(eff)

    # loading initial metadata to save the output
    profile = rasterio.open(inpath + var + '.tif', 'r').profile
    angle_eff = np.nan_to_num(angle_eff)  # nan no data don't pass
    # profile.update(nodata=0)

    # writing the output
    output_filename = outpath + var + '_eff' + '.tif'
    
    try:
        
        with rasterio.open(output_filename, 'w', **profile) as dst:
            dst.write(angle_eff, 1)
            
    except ValueError:
        
        profile = {k: v for k, v in profile.items() if k not in 
                   ['blockxsize', 'blockysize']}
        
        with rasterio.open(output_filename, 'w', **profile) as dst:
            dst.write(angle_eff, 1)

    # writing slope_flag 
    profile.update(nodata=255)
    
    slope_flag_filename = outpath + 'slope_flag_' + str(slope_thres) \
                          + '_degrees.tif'
    
    with rasterio.open(slope_flag_filename, 'w', **profile) as dst:
        dst.write(slope_flag, 1)   
    
    # returning slope, aspect and slope flag only for SZA (only once)
    if var == 'SZA':
        return angle_eff, slope, aspect, slope_flag
    
    if var == 'OZA':
        return angle_eff


def get_ITOAR(slope, aspect, inpath, outpath):
    '''

    Determines the Intrinsic Bottom of Atmosphere Reflectance (Itoar) for given bands 
    as inputs of Alexander Kokhanovsky's algorithm.
    
    INPUTS:
        slope: slope raster [array]
        aspect: aspect of the slope raster [array]
        slope_flag: slope mask based on the "small slope approximation" (Picard et al, 2020). 
                    1 for slope<=threshold, 255 (no data) for slope>threshold [array]
        inpath: path to the folder containing the variables (rBRR and SAA needed) [string]
        outpath: path where to save R_slope_{band}.tif [string]
    
    OUTPUTS:
        Itoar_{band_num}.tif: tiff file containing the effective angles for each
                              band_num [.tif] 
                              
    '''
    
    # loading solar and viewing zenith angles (flat)
    sza = rasterio.open(inpath + 'SZA.tif').read(1)
    oza = rasterio.open(inpath + 'OZA.tif').read(1)
    
    # loading solar azimuth angle (flat)
    saa_io = rasterio.open(inpath + 'SAA.tif')
    saa = saa_io.read(1)
    
    # loading TOAR (flat)
    toar = rasterio.open(inpath + 'r_TOA_21.tif').read(1)
    # saving profile as base for ITOAR file
    profile = rasterio.open(inpath + 'r_TOA_21.tif').profile 
    
    # computing ITOAR
    mu0 = np.cos(np.deg2rad(sza))
    mu = np.cos(np.deg2rad(oza))
    mu0_ov = mu0 * np.cos(np.deg2rad(slope)) + np.sin(np.deg2rad(sza))\
        * np.sin(np.deg2rad(slope)) * np.cos(np.deg2rad(saa) - np.deg2rad(aspect))
    
    itoar = toar * mu0 / mu0_ov
    
    # masking itoar with slope_flag
    with rasterio.open(outpath + 'ir_TOA_21.tif', 'w', **profile) as dst:
        dst.write(itoar, 1)
 

scenes = os.listdir(args.inpath)

for i, scene in enumerate(scenes):

    inpath_scene = inpath + os.sep + scene + os.sep
    outpath_scene = outpath + os.sep + scene + os.sep
    
    # get effective SZA and OZA
    SZA_eff, slope, aspect, slope_flag = get_effective_angle(var='SZA',
                                                             inpath=inpath_scene,
                                                             outpath=outpath_scene)
    
    OZA_eff = get_effective_angle(var='OZA', inpath=inpath_scene,
                                  outpath=outpath_scene)
    
    # get intrinsic r_TOA
    get_ITOAR(slope, aspect, inpath=inpath_scene, outpath=outpath_scene)

    # removing initial angles
    os.remove(inpath_scene + 'SZA.tif')
    os.remove(inpath_scene + 'OZA.tif')
    os.remove(inpath_scene + 'r_TOA_21.tif')

    # replacing initial angles by corrected ones
    os.rename(inpath_scene + 'SZA_eff.tif', inpath_scene + 'SZA.tif')
    os.rename(inpath_scene + 'OZA_eff.tif', inpath_scene + 'OZA.tif')
    os.rename(inpath_scene + 'ir_TOA_21.tif', inpath_scene + 'r_TOA_21.tif')
    
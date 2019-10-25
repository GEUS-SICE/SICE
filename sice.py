# pySICE
# 
# VERSION 2.3
# Oct. 25, 2019

# BAV 10-10-2019 (bav@geus.dk)
# Changes:
#   old variable:           Replaced by:
#   raa                     its formula: 180.-(vaa-saa)
#   AKOEF                   its formula: totadu/404.59
#   nv np and isk           i_channel
#   xxx                     ak1*ak2/r0
#   answer                  alb_sph
#   nsolo                   spher_calc
#   fun                     alb2rtoa
#   deltak                  removed (diagnostic variable)
#   sobthv                  specific case o alb2rtoa
#   funs                    removed (not used)
#   zbrent                  replaced by a python version
#   psi                     specific case of sol
#   wave                    removed (using vectorized w instead)
              
# This code retrieves snow/ice  albedo and related snow products for clean Arctic
# atmosphere. The errors increase with the load of pollutants in air.
# Alexander  KOKHANOVSKY
# a.kokhanovsky@vitrocisetbelgium.com
# **************************************************
               
# Inputs:
# sza                       solar zenith angle
# vza                       viewing zenith angle
# saa                       solar azimuthal angle
# vaa                       viewing azimuthal angle
# height                    height of underlying surface(meters)
# toa[i_channel]            spectral OLCI TOA reflectance at 21 channels (R=pi*I_reflec/cos(SZA)/E_0)
# tozon [i_channel]         spectral ozone vertical optical depth at the fixed ozone concentration 404.59DU ( wavelength, VOD)
# voda[i_channel]           spectral water vapour vertical optical depth at the fixed concentration 3.847e+22 molecules per square sm
# aot                       threshold value on aerosol optical thickness (aot) at 500nm

# Outputs: 
# Ozone retrieval:
# BXXX                      retrieved total ozone from OLCI measurements
# totadu                    ECMWF total column ozone in Dobson Unit
# toa                       ozone-corrected OLCI toa relfectances

# snow characteristics:
# isnow                     0 = clean snow, 1 = polluted snow
# ntype                     pollutant type: 1(soot), 2( dust), 3 and 4 (other or mixture)
# conc                      pollutant concentration is defined as the volumetric concentration 
#                           of pollutants devided by the volumetric concentration of ice grains
# bf                        normalized absorption coefficient of pollutants ay 1000nm ( in inverse mm)
# bm                        Angstroem absorption coefficient of pollutants ( around 1 - for soot, 3-7 for dust)
    
# alb_sph(i),i=1,21)        spherical albedo
# (rp(i),i=1,21)            planar albedo
# (refl(i),i=1,21)          relfectance (boar)

# D                         diamater of grains(mm)
# area                      specific surface area (kg/m/m)
# al                        effective absorption length(mm)
# r0                        reflectance of a semi-infinite non-absorbing snow layer
#
# plane BroadBand Albedo (BBA)
# rp1                       visible(0.3-0.7micron)
# rp2                       near-infrared (0.7-2.4micron)
# rp3                       shortwave(0.3-2.4 micron)shortwave(0.3-2.4 micron)

# spherical BBA
# rs1                       visible(0.3-0.7micron)
# rs2                       near-infrared (0.7-2.4micron)
# rs3                       shortwave(0.3-2.4 micron)shortwave(0.3-2.4 micron)

# Constants required:
# xa, ya                    ice refractive index ya at wavelength xa
# w                         OLCI channels
# bai                       Imaginary part of ice refrative index at OLCI channels

# Functions required:
# alb2rtoa                  calculates TOA reflectance from surface albedo
# salbed                    calculates ratm for albedo correction (?)
# zbrent                    equation solver
# sol                       solar spectrum
# analyt_func               calculation of surface radiance
# quad_func                 calculation of quadratic parameters
# trapzd                    trapezoidal rule for integral calculation
# funp                      snow spectral planar and spherical albedo function

#Removed parts compared to Fortran:
#--------------------------
## if Oa11 < ALR21 the surface is assumed to be dark ice and we move to the next pixel    
#    if(toa[21]<ALR21):
#        iice = 1  
#        # moving to next pixel
#        break
#    else:
#        iice = 0
#---------------------------
#    # calculation of NDSI, NDBI and flags
#    rr1=toa[17]   
#    rr2=toa[21]
#    arr1=toa[1]
#
#    # derivation of indices
#    indexs=0, indexi=0, indexd=0
#
#    andsi=(rr1-rr2)/(rr1+rr2)
#    andbi=(arr1-rr2)/(arr1+rr2)
#
#    if (andsi>0.03 and arr1>0.5): indexs=1
#    if (andbi>0.33):     indexi=1
#    if (andbi>0.66):    indexd=1
#
#	===============================0
    
import numpy as np
from numpy import genfromtxt

import sice_lib as sl
import rasterio as rio
import time
start_time = time.time()

import sys
InputFolder = sys.argv[1] + '/'

#%% ========= input tif ================
print("Reading input ")

Oa01 = rio.open(InputFolder+'reflectance_Oa01.tif')
meta = Oa01.meta

def WriteOutput(var,var_name,in_folder):
    # this functions write tif files based on a model file, here "Oa01"
    # opens a file for writing
    with rio.open(in_folder+var_name+'.tif', 'w+', **meta) as dst:
        dst.write(np.reshape(var,np.shape(Oa01)),1)
    
    # calculates x, y and z 2D grids
    l,b,r,t = Oa01.bounds
    res = Oa01.res
    x = np.arange(l,r, res[0])
    y = np.arange(t,b, -res[0])
    z=np.reshape(var,np.shape(Oa01))
    return x, y, z
    
    
olci_data = np.tile(Oa01.read(1).flatten()*np.nan, (21,1)).transpose()

for i in range(21):
    dat = rio.open((InputFolder+'reflectance_Oa'+str(i+1).zfill(2)+'.tif'))
    olci_data[:,i] = dat.read(1).flatten()
    
ozone = rio.open(InputFolder+'ozone.tif').read(1).flatten()
water = rio.open(InputFolder+'water.tif').read(1).flatten()
sza = rio.open(InputFolder+'SZA.tif').read(1).flatten()
saa = rio.open(InputFolder+'SAA.tif').read(1).flatten()
vza = rio.open(InputFolder+'OZA.tif').read(1).flatten()
vaa = rio.open(InputFolder+'OAA.tif').read(1).flatten()
height = rio.open(InputFolder+'height.tif').read(1).flatten()

water_vod = genfromtxt('./tg_water_vod.dat', delimiter='   ')
voda = water_vod[range(21),1]

ozone_vod = genfromtxt('./tg_vod.dat', delimiter='   ',skip_header=2)
tozon = ozone_vod[range(21),1]
aot = 0.1
   
#%% Running sice
print("Running sice")

BXXX, isnow, D, area, al, r0, isnow, conc, ntype, rp1, rp2, rp3, rs1, rs2, rs3 =  \
vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan
alb_sph, rp,refl =  olci_data*np.nan, olci_data*np.nan, olci_data*np.nan

from tqdm import tqdm

for i in  tqdm(range(len(vaa))):
    if(olci_data[i][20]<0.1):
        isnow[i] = 4
        continue
    if np.any(np.isnan(olci_data[i])):
        continue

    BXXX[i], D[i], area[i], al[i], r0[i], isnow[i], conc[i], ntype[i],alb_sph[i,:], rp[i,:],refl[i,:], rp1[i], rp2[i], rp3[i], rs1[i], rs2[i], rs3[i] = \
    sl.pySICE(sza[i],vza[i],saa[i],vaa[i],height[i],olci_data[i],ozone[i],water[i],voda,tozon,aot)
    
#%% Output generation
# pick the variable you want to output

WriteOutput(rp1,'rp1_py',InputFolder)
WriteOutput(rp2,'rp2_py',InputFolder)
WriteOutput(isnow,'isnow_py',InputFolder)
WriteOutput(rs1,'rs1_py',InputFolder)
WriteOutput(rs2,'rs2_py',InputFolder)
WriteOutput(rs1,'rs1_py',InputFolder)
WriteOutput(r0,'r0_py',InputFolder)
WriteOutput(BXXX,'O3_py',InputFolder)

print("Writing output --- %s seconds ---" % (time.time() - start_time))
start_time = time.time()



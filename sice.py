# pySICEv1.4
# 
# from FORTRAN VERSION 5.2
# March 31, 2020
#
# Latest update of python scripts: 29-04-2020 (bav@geus.dk)
# - Fixed a bug in the indexing of the polluted pixels for which the spherical albedo equation could not be solved.  Solved the oultiers visible in bands 12-15 and 19-20 and  expended the BBA calculation to few pixels that fell out of the index.
# -compression of output
# - new backscatter fraction from Alex
# - new format for tg_vod.dat file
              
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
#	====================================

import numpy as np
from numpy import genfromtxt
import sice_lib as sl
import rasterio as rio
import time
import sys
from constants import w, bai, sol1_clean, sol2, sol3_clean, sol1_pol, sol3_pol, asol
np.seterr(invalid='ignore')

start_time = time.process_time()

InputFolder =  sys.argv[1] + '/'

#%% ========= input tif ================
Oa01 = rio.open(InputFolder+'r_TOA_01.tif')
meta = Oa01.meta
with rio.Env():    
    meta.update(compress='DEFLATE')

def WriteOutput(var,var_name,in_folder):
    # this functions write tif files based on a model file, here "Oa01"
    # opens a file for writing

    with rio.open(in_folder+var_name+'.tif', 'w+', **meta) as dst:
        dst.write(var.astype('float32'),1)
    
toa = np.tile(Oa01.read(1)*np.nan, (21,1,1))

for i in range(21):
    dat = rio.open((InputFolder+'r_TOA_'+str(i+1).zfill(2)+'.tif'))
    toa[i,:,:] = dat.read(1)
    
ozone = rio.open(InputFolder+'O3.tif').read(1)
water = rio.open(InputFolder+'WV.tif').read(1)
sza = rio.open(InputFolder+'SZA.tif').read(1)
saa = rio.open(InputFolder+'SAA.tif').read(1)
vza = rio.open(InputFolder+'OZA.tif').read(1)
vaa = rio.open(InputFolder+'OAA.tif').read(1)
height = rio.open(InputFolder+'height.tif').read(1)

sza[np.isnan(toa[0,:,:])] = np.nan
saa[np.isnan(toa[0,:,:])] = np.nan
vza[np.isnan(toa[0,:,:])] = np.nan
vaa[np.isnan(toa[0,:,:])] = np.nan

water_vod = genfromtxt('./tg_water_vod.dat', delimiter='   ')
voda = water_vod[range(21),1]

ozone_vod = genfromtxt('./tg_vod.dat', delimiter='   ')
tozon = ozone_vod[range(21),1]
aot = 0.1

#%%   declaring variables
BXXX, isnow, D, area, al, r0, isnow, conc, ntype, rp1, rp2, rp3, rs1, rs2, rs3 =  \
vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, \
vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, \
vaa*np.nan, vaa*np.nan, vaa*np.nan

alb_sph, rp, refl =  toa*np.nan, toa*np.nan, toa*np.nan

#%% =========== ozone scattering  ====================================
BXXX, toa_cor_o3 = sl.ozone_scattering(ozone,tozon, sza, vza,toa)

# Filtering pixels unsuitable for retrieval
isnow[sza>75] = 100
isnow[toa_cor_o3[20, :,:] < 0.1] = 102
for i_channel in range(21):
    toa_cor_o3[i_channel, ~np.isnan(isnow)] = np.nan

vaa[ ~np.isnan(isnow)] = np.nan
saa[ ~np.isnan(isnow)] = np.nan
sza[ ~np.isnan(isnow)] = np.nan
vza[ ~np.isnan(isnow)] = np.nan
height = height.astype(float)
height[ ~np.isnan(isnow)] = np.nan

# =========== view geometry and atmosphere propeties  ==============
raa, am1, am2, ak1, ak2, amf, co = sl.view_geometry(vaa, saa, sza, vza, aot, height)
tau, p, g,gaer,taumol,tauaer = sl.aerosol_properties(aot, height, co)
        
# =========== snow properties  ====================================
D, area, al, r0, bal = sl.snow_properties(toa_cor_o3, ak1, ak2)
# filtering small D
D_thresh = 0.1
isnow[D<D_thresh] = 104

for i in range(21):
    toa_cor_o3[i,D<D_thresh] = np.nan
area[D<D_thresh] = np.nan
al[D<D_thresh] = np.nan
r0[D<D_thresh] = np.nan
bal[D<D_thresh] = np.nan
am1[D<D_thresh] = np.nan
am2[D<D_thresh] = np.nan
#D[D<D_thresh] = np.nan

# =========== clean snow  ====================================
# for that we calculate the theoretical reflectance at band 1 of a surface with:
# r0 = 1, a (albedo) = 1, ak1 = 1, ak2 = 1
# t1 and t2 are the backscattering fraction
t1, t2, ratm, r, astra, rms = sl.prepare_coef(tau, g, p, am1, am2, amf,gaer,taumol,tauaer)
rs_1 = sl.alb2rtoa(1, t1[0,:,:], t2[0,:,:], np.ones_like(r0), np.ones_like(ak1), 
                   np.ones_like(ak2), ratm[0,:,:], r[0,:,:])

# we then compare it to the observed toa[0] value
ind_clean = toa_cor_o3[0,:,:] >= rs_1
isnow[ind_clean] = 0
      
# STEP 4a: clean snow retrieval
# the spherical albedo derivation: alb_sph
def mult_channel(c,A):
    tmp = A.T*c
    return tmp.T
alb_sph = np.exp(-np.sqrt(1000.*4.*np.pi* mult_channel(bai/w, np.tile(al,(21,1,1)))))
alb_sph[alb_sph>0.999]=1

# ========== very dirty snow  ====================================
ind_pol = toa_cor_o3[0,:,:] < rs_1

isnow[ind_pol] = 1

ind_very_dark = np.logical_and(toa_cor_o3[20]<0.4, ind_pol)
isnow[ind_very_dark] = 6

am11=np.sqrt(1.-am1[ind_very_dark]**2.)
am12=np.sqrt(1.-am2[ind_very_dark]**2.)

tz=np.arccos(-am1[ind_very_dark] * am2[ind_very_dark] + am11 * am12 * np.cos(raa[ind_very_dark]*3.14159/180.))  *180./np.pi
             
pz=11.1*np.exp(-0.087*tz)+1.1*np.exp(-0.014*tz)

rclean = 1.247 + 1.186 *(am1[ind_very_dark]+am2[ind_very_dark]) + \
5.157 * am1[ind_very_dark] * am2[ind_very_dark] + pz

rclean = rclean /4. /(am1[ind_very_dark] + am2[ind_very_dark])
r0[ind_very_dark] = rclean

# =========== polluted snow  ====================================
ind_pol =  np.logical_or(ind_very_dark, ind_pol)
if np.any(ind_pol):
    subs_pol = np.argwhere(ind_pol)
    
    # approximation of the transcendental equation allowing closed-from solution
    #alb_sph[:,ind_pol] =   (toa_cor_o3[:,ind_pol] - r[:,ind_pol])/(t1[:,ind_pol]*t2[:,ind_pol]*r0[ind_pol] + ratm[:,ind_pol]*(toa_cor_o3[:,ind_pol] - r[:,ind_pol]))
    
    # solving iteratively the transcendental equation
    alb_sph[:,ind_pol] = 1
    
    def solver_wrapper(toa_cor_o3,tau, t1, t2, r0, ak1, ak2, ratm, r):
        def func_solv(albedo):
            return toa_cor_o3 - sl.alb2rtoa(albedo, t1, t2, r0, ak1, ak2, ratm, r)
        # it is assumed that albedo is in the range 0.1-1.0
        return sl.zbrent(func_solv, 0.1, 1, 100, 1.e-6)
    
    solver_wrapper_v = np.vectorize(solver_wrapper)
    # loop over all bands except band 19, 20
    for i_channel in np.append(np.arange(18), [20]):
        alb_sph[i_channel,ind_pol] = solver_wrapper_v(
                toa_cor_o3[i_channel,ind_pol],
                tau[i_channel,ind_pol], 
                t1[i_channel,ind_pol], 
                t2[i_channel,ind_pol],
                r0[ind_pol], ak1[ind_pol], 
                ak2[ind_pol],
                ratm[i_channel,ind_pol], 
                r[i_channel,ind_pol])
        
        ind_bad = alb_sph[i_channel,:,:]==-999
        alb_sph[i_channel,ind_bad] = np.nan
        isnow[ind_bad]= -i_channel
    
    # INTERNal CHECK FOR CLEAN PIXELS
    # Are reprocessed as clean
    ind_clear_pol1 = np.logical_and(ind_pol, alb_sph[0,:,:]>0.98)
    ind_clear_pol2 = np.logical_and(ind_pol, alb_sph[1,:,:]>0.98)
    ind_clear_pol = np.logical_or(ind_clear_pol1, ind_clear_pol2)
    isnow[ind_clear_pol]= 7
    for i_channel in range(21):
        alb_sph[i_channel,ind_clear_pol] = np.exp(-np.sqrt(4.*1000.*al[ind_clear_pol] * np.pi * bai[i_channel] / w[i_channel] )) 
        
    # re-defining polluted pixels
    ind_pol =  np.logical_and(ind_pol, isnow!=7)
    
    #retrieving snow impurities        
    ntype, bf, conc = sl.snow_impurities(alb_sph, bal)

    # alex   09.06.2019
    # reprocessing of albedo to remove gaseous absorption using linear polynomial approximation in the range 753-778nm.
    # Meaning: alb_sph[12],alb_sph[13] and alb_sph[14] are replaced by a linear  interpolation between alb_sph[11] and alb_sph[15]
    afirn=(alb_sph[15,ind_pol]-alb_sph[11,ind_pol])/(w[15]-w[11])
    bfirn=alb_sph[15,ind_pol]-afirn*w[15]
    alb_sph[12,ind_pol] = bfirn + afirn*w[12]
    alb_sph[13,ind_pol] = bfirn + afirn*w[13]
    alb_sph[14,ind_pol] = bfirn + afirn*w[14]             

    # BAV 09-02-2020: 0.5 to 0.35
    # pixels that are clean enough in channels 18 19 20 and 21 are not affected by pollution, the analytical equation can then be used
    ind_ok =  np.logical_and(ind_pol, toa_cor_o3[20,:,:]>0.35)
    for i_channel in range(17,21):
        alb_sph[i_channel,ind_ok] = np.exp(-np.sqrt(4.*1000.*al[ind_ok] * np.pi * bai[i_channel] / w[i_channel] ))
    # Alex, SEPTEMBER 26, 2019
    # to avoid the influence of gaseous absorption (water vapor) we linearly interpolate in the range 885-1020nm for bare ice cases only (low toa[20])
    # Meaning: alb_sph[18] and alb_sph[19] are replaced by a linear interpolation between alb_sph[17] and alb_sph[20]
    delx=w[20]-w[17]
    bcoef=(alb_sph[20,ind_pol]-alb_sph[17,ind_pol])/delx
    acoef=alb_sph[20,ind_pol]-bcoef*w[20]
    alb_sph[18,ind_pol] = acoef + bcoef*w[18]
    alb_sph[19,ind_pol] = acoef + bcoef*w[19]

# ========= derivation of plane albedo and reflectance =========== 
rp = np.power (alb_sph, ak1)
refl =r0* np.power(alb_sph, (ak1*ak2/r0))

ind_all_clean = np.logical_or(ind_clean, isnow == 7)

## CalCULATION OF BBA of clean snow

# old method: integrating equation
#BBA_v = np.vectorize(sl.BBA_calc_clean)
#p1,p2,s1,s2 = BBA_v(al[ind_all_clean], ak1[ind_all_clean])
#
## visible(0.3-0.7micron)
#rp1[ind_all_clean]=p1/sol1_clean
#rs1[ind_all_clean]=s1/sol1_clean
## near-infrared (0.7-2.4micron)
#rp2[ind_all_clean]=p2/sol2
#rs2[ind_all_clean]=s2/sol2
## shortwave(0.3-2.4 micron)
#rp3[ind_all_clean]=(p1+p2)/sol3_clean
#rs3[ind_all_clean]=(s1+s2)/sol3_clean

# approximation
# planar albedo
#rp1 and rp2 not derived anymore
rp3[ind_all_clean]=sl.plane_albedo_sw_approx(D[ind_all_clean],am1[ind_all_clean])
#     spherical albedo
#rs1 and rs2 not derived anymore
rs3[ind_all_clean]= sl.spher_albedo_sw_approx(D[ind_all_clean])
    
# calculation of the BBA for the polluted snow
rp1[ind_pol], rp2[ind_pol], rp3[ind_pol] = sl.BBA_calc_pol(
        rp[:, ind_pol], asol, sol1_pol, sol2, sol3_pol)
rs1[ind_pol], rs2[ind_pol], rs3[ind_pol] = sl.BBA_calc_pol(
        alb_sph[:, ind_pol], asol, sol1_pol, sol2, sol3_pol)
               
#%% Output
WriteOutput(BXXX,   'O3_SICE',   InputFolder)
WriteOutput(D,      'grain_diameter',InputFolder)
WriteOutput(area,   'snow_specific_area', InputFolder)
WriteOutput(al,   'al',     InputFolder)
WriteOutput(r0,   'r0',InputFolder)
WriteOutput(isnow,'diagnostic_retrieval',InputFolder)
WriteOutput(conc, 'conc',InputFolder)
WriteOutput(rp3,  'albedo_bb_planar_sw',InputFolder)
WriteOutput(rs3,  'albedo_bb_spherical_sw',InputFolder)

for i in np.append(np.arange(11), np.arange(15,21)):
# for i in np.arange(21):
    WriteOutput(alb_sph[i,:,:],    'albedo_spectral_spherical_'+str(i+1).zfill(2), InputFolder)
    WriteOutput(rp[i,:,:],    'albedo_spectral_planar_'+str(i+1).zfill(2), InputFolder)
    WriteOutput(refl[i,:,:],   'rBRR_'+str(i+1).zfill(2), InputFolder)

print("End SICE.py %s --- %s CPU seconds ---" % (InputFolder, time.process_time() - start_time))

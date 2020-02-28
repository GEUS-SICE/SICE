# pySICEv1.0
# 
# from FORTRAN VERSION 3.4
# Nov. 11, 2019

# BAV 09-092-2020 (bav@geus.dk)
# Latest update
# From Alex's side:
# corrected bugs reported by bav
# Change of certain threshold values
# Removal of the water vapor absorption
# zbrent not used for band 19 and 20. Interpolation is used instead.
# output of planar and spectral abedo fixed
# 
# 
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
import sys

start_time = time.time()
InputFolder = sys.argv[1] + '/'
#def sice(folder):
#    InputFolder = folder

#%% ========= input tif ================
print("Reading input ")

Oa01 = rio.open(InputFolder+'r_TOA_01.tif')
meta = Oa01.meta

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

ozone_vod = genfromtxt('./tg_vod.dat', delimiter='   ',skip_header=2)
tozon = ozone_vod[range(21),1]
aot = 0.1

   
#%%    start_time = time.time()

# declaring variables
BXXX, isnow, D, area, al, r0, isnow, conc, ntype, rp1, rp2, rp3, rs1, rs2, rs3 =  \
vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, \
vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, vaa*np.nan, \
vaa*np.nan, vaa*np.nan, vaa*np.nan

alb_sph, rp, refl =  toa*np.nan, toa*np.nan, toa*np.nan

#%% solar flux calculation
print('solar flux calculation')
from constants import w, bai,f0,f1,f2,bet,gam
from sice_lib import sol
 
sol0 = (f0 + f1*np.exp(-bet * 0.4) + f2*np.exp(-gam * 0.4))*0.1

# solar flux calculation
# sol1      visible(0.3-0.7micron)
# somehow, a different sol1 needs to be used for clean snow and polluted snow
sol1_clean= sol(0.7) - sol(0.4) + sol0
sol1_pol = sol(0.7) - sol(0.3)
# sol2      near-infrared (0.7-2.4micron)
# same for clean and polluted
sol2 = sol(2.4) - sol(0.7)

# sol3      shortwave(0.3-2.4 micron)
# sol3 is also different for clean snow and polluted snow
sol3_clean = sol1_clean  +  sol2
sol3_pol   = sol1_pol  +  sol2

# asol specific band
asol = sol(0.865) - sol(0.7)

#%%
# =========== ozone scattering  ====================================
BXXX, toa_cor_o3 = sl.ozone_scattering(ozone,tozon, sza, vza,toa)

# Filtering pixels unsuitable for retrieval
#    if ((cloud_an_gross[i] == 1) or (cloud_an_137[i] == 1) or (cloud_an_thin_cirrus[i] == 1)): continue

isnow[sza>75] = 100
isnow[toa_cor_o3[20, :,:] > 0.76] = 101
isnow[toa_cor_o3[20, :,:] < 0.1] = 102
for i_channel in range(21):
    toa_cor_o3[i_channel, np.logical_not(np.isnan(isnow))] = np.nan

vaa[np.logical_not(np.isnan(isnow))] = np.nan
saa[np.logical_not(np.isnan(isnow))] = np.nan
sza[np.logical_not(np.isnan(isnow))] = np.nan
vza[np.logical_not(np.isnan(isnow))] = np.nan
height = height.astype(float)
height[np.logical_not(np.isnan(isnow))] = np.nan

# =========== view geometry and atmosphere propeties  ==============
raa, am1, am2, ak1, ak2, amf, co = sl.view_geometry(vaa, saa, sza, vza, aot, height)

tau, p, g = sl.aerosol_properties(aot, height, co)
        
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
D[D<D_thresh] = np.nan

# =========== clean snow  ====================================
# for that we calculate the theoretical reflectance at band 1 of a surface with:
# r0 = 1, a (albedo) = 1, ak1 = 1, ak2 = 1
rs_1 = sl.alb2rtoa(1, tau[0,:,:], g[0,:,:], p[0,:,:], amf, am1, am2, 1, 1, 1)

# we then compare it to the observed toa[0] value
ind_clean = toa_cor_o3[0,:,:] >= rs_1
isnow[ind_clean] = 0
      
# STEP 4a: clean snow retrieval
alpha = 4.*np.pi*bai/w   
absor = g*np.nan

# the spherical albedo derivation: alb_sph
al_clean = al
al_clean[isnow!=0] = np.nan
for i_channel in range(21):
    absor[i_channel,:,:] = 1000.*alpha[i_channel]*al_clean
    alb_sph[i_channel, :,:] = np.exp(-np.sqrt(absor[i_channel, :, :]))
    alb_sph[i_channel, absor[i_channel,:,:] <=  1.e-6] = 1.0
    
# ========== very dirty snow  ====================================
ind_pol = toa_cor_o3[0,:,:] < rs_1
isnow[ind_pol] = 1

ind_very_dark = np.logical_and(toa_cor_o3[20]<0.4, ind_pol)
isnow[ind_very_dark] = 6

am11=np.sqrt(1.-am1[ind_very_dark]**2.)
am12=np.sqrt(1.-am2[ind_very_dark]**2.)

tz=np.arccos(-am1[ind_very_dark] * am2[ind_very_dark] + \
             am11 * am12 * np.cos(raa[ind_very_dark]*np.pi/180.))\
             *180./np.pi
             
pz=11.1*np.exp(-0.087*tz)+1.1*np.exp(-0.014*tz)

rclean = 1.247 + 1.186 *(am1[ind_very_dark]+am2[ind_very_dark]) + \
5.157 * am1[ind_very_dark] * am2[ind_very_dark] + pz

rclean = rclean /4. /(am1[ind_very_dark] + am2[ind_very_dark])

r0_save = r0
r0[ind_very_dark] = rclean

# =========== polluted snow  ====================================
ind_pol_ok = np.argwhere(ind_pol)
# loop over all bands except band 13, 14, 15, 19, 20
# meaning index [12, 13, 14, 18, 19]    
def solver_wrapper(toa_cor_o3,tau, g, p, amf, am1, am2, r0, ak1, ak2):
    def func_solv(albedo):
        return toa_cor_o3 - sl.alb2rtoa(albedo, tau, g, p, amf, am1, am2, r0, ak1, ak2)
    # it is assumed that albedo is in the range 0.1-1.0
    return sl.zbrent(func_solv, 0.1, 1, 100, 1.e-6)

solver_wrapper_v = np.vectorize(solver_wrapper)

from tqdm import tqdm

for i_channel in tqdm(np.append(np.arange(12), [15, 16, 17, 20])):
    print(i_channel)
    alb_sph[i_channel,ind_pol] = solver_wrapper_v(toa_cor_o3[i_channel,ind_pol],
           tau[i_channel,ind_pol], g[i_channel,ind_pol], p[i_channel,ind_pol], 
           amf[ind_pol], am1[ind_pol], am2[ind_pol], r0[ind_pol], ak1[ind_pol], ak2[ind_pol])
    
    ind_bad = alb_sph[i_channel,:,:]==1
    alb_sph[i_channel,ind_bad] = 1
    isnow[ind_bad]= -i_channel

# INTERNal CHECK FOR CLEAN PIXELS
# Update bav 2020: these high albedo polluted pixels were originally
# reporcessed as clean pixels now they are just left as nan
ind_bad = alb_sph[0,ind_pol_ok[:,0], ind_pol_ok[:,1]]>0.98
isnow[ind_pol_ok[ind_bad,0], ind_pol_ok[ind_bad,1]]= 7

ind_bad = alb_sph[1,ind_pol_ok[:,0], ind_pol_ok[:,1]]>0.98
isnow[ind_pol_ok[ind_bad,0], ind_pol_ok[ind_bad,1]]= 7

for i in range(21):
    alb_sph[i,isnow==7] = np.nan

#retrieving snow impurities        
ntype, bf, conc = sl.snow_impurities(alb_sph, bal)

# alex   09.06.2019
# reprocessing of albedo to remove gaseous absorption
# using linear polynomial approximation in the range 753-778nm
# Meaning:
# alb_sph[12],alb_sph[13] and alb_sph[14] are replaced by a linear 
# interpolation between alb_sph[11] and alb_sph[15]
    # update BAV 2020: interpolation not done. leave NaN instead
    #    x1=w[11]
    #    x2=w[15]
    #         
    #    y1=alb_sph[11]
    #    y2=alb_sph[15]
    #          
    #    afirn=(y2-y1)/(x2-x1)
    #    bfirn=y2-afirn*x2
    #    
    #    alb_sph[range(12,15)] = bfirn + afirn*w[range(12,15)]

# BAV 09-02-2020: 0.5 to 0.35
ind_ok =  toa_cor_o3[20]>=0.35
ii_ok, jj_ok = np.unravel_index(ind_ok,np.shape(toa[20,:,:]))

for i_channel in range(17,21):
    alb_sph[i_channel, ii_ok, jj_ok] = np.exp(-np.sqrt(4.*1000. \
            *al[ii_ok, jj_ok] * np.pi * bai[i_channel] / w[i_channel] ))

# Update bav 2020: no interpolation done for bad output on bands 19 and 20      
#    ind_nok =  toa[20]<0.35
#    ii_nok, jj_nok = np.unravel_index(ind_nok,np.shape(toa[20,:,:]))
#        # ***********CORRECTION FOR VERSION 2.2*********************
#        # Alex, SEPTEMBER 26, 2019
#        # to avoid the influence of gaseous absorption (water vapor)
#        # we linearly interpolate in the range 885-1020nm
#        # for bare ice cases only (low toa[20])
#        # Meaning:
#        # alb_sph[18] and alb_sph[19] are replaced by a linear 
#        # interpolation between alb_sph[17] and alb_sph[20]
#        delx=w[20]-w[17]
#        bcoef=(alb_sph[20]-alb_sph[17])/delx
#        acoef=alb_sph[20]-bcoef*w[20]
#        
#        alb_sph[range(18,20)] = acoef+bcoef*w[range(18,20)]
    # ***********************END of MODIFICATION**************   

# ========= derivation of plane albedo and reflectance ===========  
for i_channel in range(21):
    rp[i_channel,:,:] = alb_sph[i_channel,:,:]**ak1
          
# derivation of snow reflectance function                      
    refl[i_channel,:,:]=r0*alb_sph[i_channel,:,:]**(ak1*ak2/r0)

# STEP  5
# CalCULATION OF BBA of clean snow
BBA_v = np.vectorize(sl.BBA_calc_clean)
rp1[isnow == 0], rp2[isnow == 0], rp3[isnow == 0], rs1[isnow == 0], rs2[isnow == 0], rs3[isnow == 0] =\
BBA_v(al[isnow == 0].flatten(), ak1[isnow == 0].flatten(), sol1_clean, sol2, sol3_clean)

# calculation of the BBA for the polluted snow
ind_all_polluted = np.logical_or(isnow == 1, isnow == 7, isnow == 6)

rp1[ind_all_polluted], rp2[ind_all_polluted], rp3[ind_all_polluted]= \
sl.BBA_calc_pol(rp[:, ind_all_polluted], asol, sol1_pol, sol2, sol3_pol)

rs1[ind_all_polluted], rs2[ind_all_polluted], rs3[ind_all_polluted] = \
sl.BBA_calc_pol(alb_sph[:, ind_all_polluted], asol, sol1_pol, sol2, sol3_pol)
               
#%% Output

WriteOutput(BXXX,   '03_SICE',   InputFolder)
WriteOutput(D,      'D',InputFolder)
WriteOutput(area,   'area', InputFolder)
for i in range(21):
    WriteOutput(refl[i,:,:],   'r_BOA_'+str(i+1).zfill(2), InputFolder)

#WriteOutput(al,   'al',     InputFolder)
WriteOutput(r0,   'r0',InputFolder)
WriteOutput(isnow,'isnow',InputFolder)
#WriteOutput(conc, 'conc',InputFolder)
WriteOutput(alb_sph[0,:,:],'alb_sph_1',InputFolder)
#WriteOutput(rp1,  'rp1',InputFolder)
#WriteOutput(rp2,  'rp2',InputFolder)
WriteOutput(rp3,    'SnBBA',InputFolder)
WriteOutput(rs1,  'rs1',InputFolder)
WriteOutput(rs2,  'rs2',InputFolder)
WriteOutput(rs3,  'rs3',InputFolder)
#for i in np.arange(21): WriteOutput(alb_sph[:,i],    'alb_sph_'+str(i+1), InputFolder)
#for i in np.arange(21): WriteOutput(rp[:,i],    'rp_'+str(i+1), InputFolder)

print("End SICE.py %s --- %s seconds ---" % (InputFolder, time.time() - start_time))

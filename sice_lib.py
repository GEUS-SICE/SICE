# -*- coding: utf-8 -*-
"""
Created on Mon Oct 14 16:58:31 2019
Update 07032019

 pySICE library
 contains:
     alb2rtoa                  calculates TOA reflectance from surface albedo
     salbed                    calculates ratm for albedo correction (?)
     zbrent                    equation solver
     quad_func                 calculation of quadratic parameters
     funp                      snow spectral planar and spherical albedo function

 requires:
     constants.py               contains constants needed to run the functions below

 This code retrieves snow / ice  albedo and related snow products for clean Arctic
 atmosphere. The errors increase with the load of pollutants in air.
 Alexander  KOKHANOVSKY
 a.kokhanovsky@vitrocisetbelgium.com
 Translated to python by Baptiste Vandecrux (bav@geus.dk)

@author: bav@geus.dk
"""

# pySICEv1.6
#
# from FORTRAN VERSION 5
# March 31, 2020

# Latest update of python scripts: 22-10-2021 (bav@geus.dk)
# - code optimization by Ghislain Picard

# Older update of python scripts: 29-04-2021 (bav@geus.dk)
# - Fixed a bug in the indexing of the polluted pixels for which the spherical albedo equation could not be solved.  Solved the oultiers visible in bands 12-15 and 19-20 and  expended the BBA calculation to few pixels that fell out of the index.
# -compression of output
# - new backscatter fraction from Alex
# - new format for tg_vod.dat file

# **************************************************
# Inputs:
# toa_cor_o3[i_channel]            spectral OLCI TOA reflectance at 21 channels (R=pi*I_reflec/cos(SZA)/E_0)
# tozon [i_channel]          spectral ozone vertical optical depth at the fixed ozone concentration 404.59DU
# voda[i_channel]            spectral water vapour vertical optical depth [not needed anymore] at the
#                            fixed concentration 3.847e+22 molecules per square sm
#
# Outputs:
# snow characteristics:
# isnow                     0 = clean snow, 1 = polluted snow
# ntype                     pollutant type: 1(soot), 2( dust), 3 and 4 (other or mixture)
# conc                      pollutant concentration is defined as the volumetric concentration
#                           of pollutants devided by the volumetric concentration of ice grains
# bf                        normalized absorption coefficient of pollutants ay 1000nm ( in inverse mm)
# bm                        Angstroem absorption coefficient of pollutants ( around 1 - for soot, 3-7 for dust)
#
# alb_sph(i),i=1,21)        spherical albedo
# (rp(i),i=1,21)            planar albedo
# (refl(i),i=1,21)          relfectance (boar)
#
# D                         diamater of grains(mm)
# area                      specific surface area (kg/m/m)
# al                        effective absorption length(mm)
# r0                        reflectance of a semi-infinite non-absorbing snow layer
#
# plane BroadBand Albedo (BBA)
# rp1                       visible(0.3-0.7micron)
# rp2                       near-infrared (0.7-2.4micron)
# rp3                       shortwave(0.3-2.4 micron)shortwave(0.3-2.4 micron)
#
# spherical BBA
# rs1                       visible(0.3-0.7micron)
# rs2                       near-infrared (0.7-2.4micron)
# rs3                       shortwave(0.3-2.4 micron)shortwave(0.3-2.4 micron)
#
# Ozone retrieval:
# BXXX                      retrieved total ozone from OLCI measurements
# totadu                    ECMWF total column ozone in Dobson Unit
# toa_cor_03                       ozone-corrected OLCI toa relfectances
#
# Constants required:
# xa, ya                    ice refractive index ya at wavelength xa
# w                         OLCI channels
# bai                       Imaginary part of ice refrative index at OLCI channels
#
# Functions required:
# alb2rtoa                  calculates TOA reflectance from surface albedo
# salbed                    calculates ratm for albedo correction (?)
# zbrent                    equation solver
# sol                       solar spectrum
# analyt_func               calculation of surface radiance
# quad_func                 calculation of quadratic parameters
# funp                      snow spectral planar and spherical albedo function

import os
import xarray as xr
import numpy as np
import numba
from constants_optim import wls, bai, xa, ya, f0, f1, f2, bet, gam, coef1, coef2, coef3, coef4
from constants_optim import sol1_clean, sol2, sol3_clean, sol1_pol, sol3_pol, asol, bandcoord
os.environ['PYTROLL_CHUNK_SIZE'] = '256'


def process(OLCI_scene, compute_polluted=True, **kwargs):
    angles = view_geometry(OLCI_scene)
    OLCI_scene = ozone_correction(OLCI_scene)
    OLCI_scene, snow = prepare_processing(OLCI_scene)
    aerosol = aerosol_properties(OLCI_scene.elevation, angles.cos_sa, aot=0.1)
    OLCI_scene, angles, snow = snow_properties(OLCI_scene, angles, snow)
    atmosphere = prepare_coef(aerosol, angles)
    OLCI_scene, snow = clean_snow_albedo(OLCI_scene, angles, aerosol, atmosphere, snow)
    if compute_polluted:
        OLCI_scene, snow, impurities = polluted_snow_albedo(OLCI_scene, angles, aerosol, atmosphere, snow)
    snow = compute_plane_albedo(OLCI_scene, snow, angles, compute_polluted=compute_polluted)

    return snow


def process_by_chunk(OLCI_scene, chunk_size=150000, compute_polluted=True):
    size = OLCI_scene.sza.shape[0]
    nchunks = int(max(np.floor(size / chunk_size), 1))
    OLCI_chunks = OLCI_scene.chunk({'band': 21, 'xy': chunk_size})
    # snow_chunks = OLCI_chunks.map_blocks(process,kwargs={}, template = snow_template)
    xy_chunk_indexes = np.array(OLCI_chunks.chunks['xy']).cumsum()

    diameter = []
    area = []
    rp3 = []
    rs3 = []
    isnow = []
    r0 = []
    al = []
    for i in range(len(xy_chunk_indexes)-1):
        print(f"{i+1} / {nchunks}")
        chunk = OLCI_scene.isel(xy=slice(xy_chunk_indexes[i], xy_chunk_indexes[i+1]))
        snow_chunk = process(chunk)
        diameter.append(snow_chunk.diameter)
        area.append(snow_chunk.area)
        rp3.append(snow_chunk.rp3)
        rs3.append(snow_chunk.rs3)
        isnow.append(snow_chunk.isnow)
        r0.append(snow_chunk.r0)
        al.append(snow_chunk.r0)
        del snow_chunk
    snow = xr.Dataset()
    snow['diameter'] = xr.concat(diameter, dim='xy')
    snow['area'] = xr.concat(area, dim='xy')
    snow['rp3'] = xr.concat(rp3, dim='xy')
    snow['rs3'] = xr.concat(rs3, dim='xy')
    snow['isnow'] = xr.concat(isnow, dim='xy')
    snow['r0'] = xr.concat(r0, dim='xy')
    snow['al'] = xr.concat(al, dim='xy')
    return snow


def view_geometry(OLCI_scene):
    # transfer of OLCI relative azimuthal angle to the definition used in
    # radiative transfer code
    # raa       relative azimuth angle
    # sza       solar zenith angle
    # vza       viewing zenith angle
    # cos_sa       cosine of the scattering angle
    # ak1
    # ak2
    raa = 180.-(OLCI_scene.vaa-OLCI_scene.saa)
    sin_sza = np.sin(np.deg2rad(OLCI_scene.sza))
    sin_vza = np.sin(np.deg2rad(OLCI_scene.vza))
    cos_sza = np.cos(np.deg2rad(OLCI_scene.sza))
    cos_vza = np.cos(np.deg2rad(OLCI_scene.vza))
    ak1 = 3.*(1.+2.*cos_sza)/7
    ak2 = 3.*(1.+2.*cos_vza)/7
    cos_raa = np.cos(np.deg2rad(raa))
    inv_cos_za = 1./cos_sza+1./cos_vza
    cos_sa = -cos_sza*cos_vza + sin_sza*sin_vza*cos_raa

    angles = xr.Dataset()
    angles['raa'] = raa
    angles['cos_sza'] = cos_sza
    angles['cos_vza'] = cos_vza
    angles['ak1'] = ak1
    angles['ak2'] = ak2
    angles['inv_cos_za'] = inv_cos_za
    angles['cos_sa'] = cos_sa
    return angles


def ozone_correction(OLCI_scene, write_ozone=False):
    # water and ozone spectral optical density
    # water_vod = genfromtxt('./tg_water_vod.dat', delimiter='   ')
    # self.voda = xr.DataArray(water_vod[0:21, 1], coords=[bandcoord])
    ozone_vod = np.genfromtxt('./tg_vod.dat', delimiter='   ')
    tozon = xr.DataArray(ozone_vod[0:21, 1], coords=[bandcoord])

    OLCI_scene['BXXX'], OLCI_scene['toa'] = molecular_absorption(OLCI_scene.ozone, tozon, OLCI_scene.sza, OLCI_scene.vza, OLCI_scene.toa)
    OLCI_scene.drop('ozone')  # don't use anymore
    return OLCI_scene


def molecular_absorption(ozone, tozon, sza, vza, toa):
    # Correcting TOA reflectance for ozone absorption
    eps = 1.55
    # ecmwf ozone from OLCI file (in Kg.m-2) to DOBSON UNITS
    # 1 kg O3 / m2 = 46696.24  DOBSON Unit (DU)
    totadu = 46696.24 * ozone

    inv_cos_za = 1. / np.cos(np.deg2rad(sza)) + 1. / np.cos(np.deg2rad(vza))

    BX = (toa.sel(band=20)**(1 - eps)) * (toa.sel(band=16)**eps) / toa.sel(band=6)
    BXXX = np.log(BX) / 1.11e-4 / inv_cos_za
    BXXX = BXXX.where((BXXX >= 0) & (BXXX <= 500), 999)

    # bav 09-02-2020: now water scattering not accounted for
    # kg/m**2. transfer to mol/cm**2
    #    roznov = 2.99236e-22  # 1 moles Ozone = 47.9982 grams
    # water vapor optical depth
    #    vap = water/roznov
    #    AKOWAT = vap/3.847e+22#    tvoda = np.exp(inv_cos_za*voda*AKOWAT)

    # tvoda = tozon * 0 + 1
    tvoda = 1

    toa_cor_o3 = toa * tvoda * np.exp(inv_cos_za * tozon * totadu / 404.59)

    return BXXX, toa_cor_o3


def prepare_processing(OLCI_scene):
    # Filtering pixels unsuitable for retrieval
    snow = xr.Dataset()
    snow['isnow'] = xr.where(OLCI_scene.toa[20] < 0.1, 102, np.nan)
    snow.isnow[OLCI_scene.sza > 75] = 100

    mask = np.isnan(snow.isnow)
    OLCI_scene['toa'] = OLCI_scene.toa.where(mask)
    OLCI_scene['vaa'] = OLCI_scene.vaa.where(mask)
    OLCI_scene['saa'] = OLCI_scene.saa.where(mask)
    OLCI_scene['sza'] = OLCI_scene.sza.where(mask)
    OLCI_scene['vza'] = OLCI_scene.vza.where(mask)
    OLCI_scene['elevation'] = OLCI_scene.elevation.where(mask)

    return OLCI_scene, snow


def aerosol_properties(height, cos_sa, aot=0.1):
    # Atmospheric optical thickness
    tauaer = aot * (wls / 0.5)**(-1.3)

    g0 = 0.5263
    g1 = 0.4627
    wave0 = 0.4685
    gaer = g0 + g1 * np.exp(-wls / wave0)
    pr = 0.75 * (1. + cos_sa**2)

    taumol = wls**(-4.05) * np.minimum(1, np.exp(-height / 7400)) * 0.00877
    tau = tauaer + taumol

    # aerosol asymmetry parameter
    g = tauaer * gaer / tau

    # HG phase function for aerosol
    pa = (1 - g**2) / (1. - 2. * g * cos_sa + g**2)**1.5
    p = (taumol * pr + tauaer * pa) / tau   # the order is critical to have the right order of dims (band, xy)

    aerosol = xr.Dataset()
    aerosol['tau'] = tau
    aerosol['p'] = p
    aerosol['g'] = g
    aerosol['gaer'] = gaer
    aerosol['taumol'] = taumol
    aerosol['tauaer'] = tauaer
    return aerosol


def snow_properties(OLCI_scene, angles, snow):
    # retrieval of snow properties ( R_0, size of grains from OLCI channels 865[17] and 1020nm[21] assumed not influenced by atmospheric scattering and absorption processes)
    # imaginary part of the ice refractive index at 1020nm
    akap2 = 2.25e-6
    # bulk absoprtion coefficient of ice at 1020nm
    alpha2 = 4.*np.pi*akap2 / 1.020
    # imaginary part of the ice refractive index at 865nm
    # akap1=2.4e-7
    # bulk absoprtion coefficient of ice at 865nm
    # alpha1=4.*np.pi*akap1/0.865

    # eps = 1/(1-np.sqrt(alpha1/alpha2))
    eps = 1.549559365010611
    # consequently: 1-eps = 1/(1-np.sqrt(alpha2/alpha1))

    # reflectivity of nonabsorbing snow layer
    rr1 = OLCI_scene.toa.sel(band=16)
    rr2 = OLCI_scene.toa.sel(band=20)
    r0 = (rr1**eps)*(rr2**(1.-eps))

    # effective absorption length(mm)
    bal = (np.log(rr2/r0)/(angles.ak1*angles.ak2/r0))**2/alpha2
    al = bal/1000.

    # effective grain size(mm):diameter
    # xi/(1-g) = 9.2
    D = al/(9.2*16/9)
    # snow specific area ( dimension: m*m/kg)
    area = 6./D/0.917

    # filtering small D
    diameter_thresh = 0.01

    valid = D >= diameter_thresh
    snow.isnow[~valid & np.isnan(snow.isnow)] = 104
    OLCI_scene['toa'] = OLCI_scene.toa.where(valid)
    snow['diameter'] = D.where(valid)
    snow['area'] = area.where(valid)
    snow['al'] = al.where(valid)
    snow['r0'] = r0.where(valid)
    snow['bal'] = bal.where(valid)
    angles = angles.where(valid)
    return OLCI_scene, angles, snow


def prepare_coef(aerosol, angles):

    otherdims = tuple([d for d in aerosol.tau.dims if d != 'band'])
    inputdims = [('band',) + otherdims] * 3 + [otherdims] * 3
    outputdims = [('band',) + otherdims] * 4

    args = aerosol.tau, aerosol.g, aerosol.p, angles.cos_sza, angles.cos_vza, angles.inv_cos_za
    t1, t2, ratm, r = xr.apply_ufunc(prepare_coef_numpy, *args, input_core_dims=inputdims, output_core_dims=outputdims)

    atmosphere = xr.Dataset()
    atmosphere['t1'] = t1
    atmosphere['t2'] = t2
    atmosphere['ratm'] = ratm
    atmosphere['r'] = r
    return atmosphere


@numba.jit(nopython=True, cache=True)
def prepare_coef_numpy(tau, g, p, cos_sza, cos_vza, inv_cos_za):
    one_g_tau = (1 - g) * tau

    # SOBOLEV
    b1 = 1. + 1.5 * cos_sza + (1. - 1.5 * cos_sza) * np.exp(-tau / cos_sza)
    b2 = 1. + 1.5 * cos_vza + (1. - 1.5 * cos_vza) * np.exp(-tau / cos_vza)

    sumcos = cos_sza + cos_vza

    astra = (1. - np.exp(- tau * inv_cos_za)) / sumcos / 4.
    oskar = 4. + 3. * one_g_tau
	# multiple scattering contribution to the atmospheric reflectance
    rms = 1. - b1 * b2 / oskar + (3. * (1. + g) * (cos_sza * cos_vza) - 2. * sumcos) * astra

    r = p * astra + rms

    wa1 = 1.10363
    wa2 = -6.70122
    wx0 = 2.19777
    wdx = 0.51656
    bex = np.exp((g - wx0) / wdx)

    # backscattering fraction
    arg = - 0.5 * one_g_tau / ((wa1 - wa2) / (1. + bex) + wa2)
    
    # atmospheric backscattering fraction
    # t1*t2 is the 2-ways atmospheric transmittance (from the sun to the surface and to the satellite)
    # t1[i,:,:] = np.exp(-(1.-g[i,:,:])*tau[i,:,:]/cos_sza/2.)
    # t2[i,:,:] = np.exp(-(1.-g[i,:,:])*tau[i,:,:]/cos_vza/2.)
    t1 = np.exp(arg / cos_sza)
    t2 = np.exp(arg / cos_vza)

    # SALBED
    #    ratm = salbed(tau, g)
    a_s = (.18016, -0.18229, 0.15535, -0.14223)
    bs = (.58331, -0.50662,  -0.09012, 0.0207)
    cs = (0.21475, -0.1, 0.13639, -0.21948)
    als = (0.16775, -0.06969, 0.08093, -0.08903)
    bets = (1.09188, 0.08994, 0.49647, -0.75218)

    a_cst = a_s[0] + a_s[1] * g
    b_cst = bs[0] + bs[1] * g
    c_cst = cs[0] + cs[1] * g
    al_cst = als[0] + als[1] * g
    bet_cst = bets[0] + bets[1] * g

    for n in range(2, 4):
        if n == 2:
            gg = g ** 2
        else:
            gg *= g
        a_cst += a_s[n] * gg
        b_cst += bs[n] * gg
        c_cst += cs[n] * gg
        al_cst += als[n] * gg
        bet_cst += bets[n] * gg

    ratm = tau * (a_cst * np.exp(-tau / al_cst) + b_cst * np.exp(-tau / bet_cst) + c_cst)
    return t1, t2, ratm, r


def alb2rtoa(a, t1, t2, r0, ak1, ak2, ratm, r):
    # Function that calculates the theoretical reflectance from a snow spherical albedo a
    # This function can then be solved to find optimal snow albedo
    # Inputs:
    # a                     Surface albedo
    # r0                    reflectance of a semi-infinite non-absorbing snow layer
    #
    # Outputs:
    # rs                  surface reflectance at specific channel
    surf = t1 * t2 * r0 * a**(ak1 * ak2 / r0) / (1 - a * ratm)
    rs = r + surf
    return rs


def clean_snow_albedo(OLCI_scene, angles, aerosol, atmosphere, snow):
    # =========== clean snow  ====================================
    # for that we calculate the theoretical reflectance at band 1 of a surface with:
    # r0 = 1, a (albedo) = 1, ak1 = 1, ak2 = 1
    # t1 and t2 are the backscattering fraction
    snow['rs_1'] = alb2rtoa(1, atmosphere.t1.sel(band=0), atmosphere.t2.sel(band=0), 1, 1, 1, atmosphere.ratm.sel(band=0), atmosphere.r.sel(band=0))

    # we then compare it to the observed toa[0] value
    snow['ind_clean'] = OLCI_scene.toa.sel(band=0) >= snow.rs_1
    snow.isnow[snow.ind_clean] = 0

    snow['ind_pol'] = OLCI_scene.toa.sel(band=0) < snow.rs_1

    # clean snow spherical albedo derivation: alb_sph
    snow['alb_sph'] = np.minimum(np.exp(-np.sqrt(1000. * 4. * np.pi * (bai / wls * snow.al))), 1)
    return OLCI_scene, snow


def polluted_snow_albedo(OLCI_scene, angles, aerosol, atmosphere, snow):
    if not np.any(snow.ind_pol):
        impurities = xr.Dataset()
        impurities['ntype'] = xr.full_like(OLCI_scene.sza, np.nan)
        impurities['bf'] = xr.full_like(OLCI_scene.sza, np.nan)
        impurities['conc'] = xr.full_like(OLCI_scene.sza, 0)
        return OLCI_scene, snow, impurities

    snow.isnow[snow.ind_pol] = 1
    #  very dirty snow
    ind_very_dark = (OLCI_scene.toa.sel(band=20) < 0.4) & snow.ind_pol
    snow.isnow[ind_very_dark] = 6

    def compute_rclean(cos_sza, cos_vza, cos_sa, raa):
        am11 = np.sqrt(1.-cos_sza**2.)
        am12 = np.sqrt(1.-cos_vza**2.)

        theta = np.arccos(-cos_sza * cos_vza + am11 * am12 * np.cos(raa*3.14159/180.)) * 180./np.pi
        # theta = np.rad2deg(np.arccos(cos_sa))

        pz = 11.1 * np.exp(-0.087 * theta) + 1.1 * np.exp(-0.014 * theta)

        sumcos = cos_sza + cos_vza
        rclean = 1.247 + 1.186 * sumcos + 5.157 * cos_sza * cos_vza + pz

        return rclean / 4. / sumcos

    snow['r0'] = snow.r0.where(~ind_very_dark, compute_rclean(angles.cos_sza, angles.cos_vza, angles.cos_sa, angles.raa))

    # approximation of the transcendental equation allowing closed-from solution
    # alb_sph[:,ind_pol] =   (toa_cor_o3[:,ind_pol] - r[:,ind_pol]) (t1[:,ind_pol]*t2[:,ind_pol]*r0[ind_pol] + ratm[:,ind_pol]*(toa_cor_o3[:,ind_pol] - r[:,ind_pol]))

    # solving iteratively the transcendental equation
    iind_pol = dict(xy=np.arange(len(snow.ind_pol))[snow.ind_pol])
    snow.alb_sph[iind_pol] = 1

    def solver_wrapper(toa_cor_o3, tau, t1, t2, r0, ak1, ak2, ratm, r):
        # it is assumed that albedo is in the range 0.1-1.0
        return zbrent(0.1, 1, args=(t1, t2, r0, ak1, ak2, ratm, r, toa_cor_o3), max_iter=30, tolerance=2e-4)

    solver_wrapper_v = np.vectorize(solver_wrapper)

    # loop over all bands except band 19, 20
    for i_channel in np.append(np.arange(18), [20]):
        #print('band=', i_channel)
        snow.alb_sph.sel(band=i_channel)[iind_pol] = solver_wrapper_v(
            OLCI_scene.toa.sel(band=i_channel)[iind_pol],
            aerosol.tau.sel(band=i_channel)[iind_pol],
            atmosphere.t1.sel(band=i_channel)[iind_pol],
            atmosphere.t2.sel(band=i_channel)[iind_pol],
            snow.r0[iind_pol],
            angles.ak1[iind_pol], angles.ak2[iind_pol],
            atmosphere.ratm.sel(band=i_channel)[iind_pol],
            atmosphere.r.sel(band=i_channel)[iind_pol]
        )
        ind_bad = snow.alb_sph.sel(band=i_channel) == -999
        snow.isnow[ind_bad] = -i_channel
    snow['alb_sph'] = snow.alb_sph.where(snow.isnow >= 0)

    # INTERNal CHECK FOR CLEAN PIXELS
    # Are reprocessed as clean
    ind_clear_pol = ((snow.alb_sph.sel(band=0) > 0.98) | (snow.alb_sph.sel(band=1) > 0.98)) & snow.ind_pol
    snow.isnow[ind_clear_pol] = 7

    snow['alb_sph'] = snow.alb_sph.where(~ind_clear_pol, np.exp(-np.sqrt(4. * 1000. * np.pi * snow.al * (bai / wls))))

    # re-defining polluted pixels
    snow['ind_pol'] = snow.ind_pol & (snow.isnow != 7)
    iind_pol = dict(xy=np.arange(len(snow.ind_pol))[snow.ind_pol])

    # retrieving snow impurities
    impurities = xr.Dataset()
    impurities['ntype'], impurities['bf'], impurities['conc'] = snow_impurities(snow.alb_sph, snow.bal)

    # alex   09.06.2019
    # reprocessing of albedo to remove gaseous absorption using linear polynomial approximation in the range 753-778nm.
    # Meaning: alb_sph[12],alb_sph[13] and alb_sph[14] are replaced by a linear  interpolation between alb_sph[11] and alb_sph[15]
    afirn = (snow.alb_sph.sel(band=15)[iind_pol] - snow.alb_sph.sel(band=11)[iind_pol]) / (wls.sel(band=15) - wls.sel(band=11))
    bfirn = snow.alb_sph.sel(band=15)[iind_pol] - afirn * wls.sel(band=15)

    for b in [12, 13, 14]:
        snow.alb_sph.sel(band=b)[iind_pol] = bfirn + afirn * wls.sel(band=b)

    # BAV 09-02-2020: 0.5 to 0.35
    # pixels that are clean enough in channels 18 19 20 and 21 are not affected by pollution, the analytical equation can then be used
    ind_ok = (OLCI_scene.toa.sel(band=20) > 0.35) & snow.ind_pol
    iind_ok = dict(xy=np.arange(len(ind_ok))[ind_ok])

    for b in range(17, 21):
        snow.alb_sph.sel(band=b)[iind_ok] = np.exp(-np.sqrt(4.*1000. * np.pi * snow.al[iind_ok] * (bai.sel(band=b) / wls.sel(band=b))))

    # Alex, SEPTEMBER 26, 2019
    # to avoid the influence of gaseous absorption (water vapor) we linearly interpolate in the range 885-1020nm for bare ice cases only (low toa[20])
    # Meaning: alb_sph[18] and alb_sph[19] are replaced by a linear interpolation between alb_sph[17] and alb_sph[20]
    bcoef = (snow.alb_sph.sel(band=20)[iind_pol] - snow.alb_sph.sel(band=17)[iind_pol]) / (wls.sel(band=20) - wls.sel(band=17))
    acoef = snow.alb_sph.sel(band=20)[iind_pol] - bcoef * wls.sel(band=20)

    for b in [18, 19]:
        snow.alb_sph.sel(band=b)[iind_pol] = acoef + bcoef * wls.sel(band=b)
    return OLCI_scene, snow, impurities


def snow_impurities(alb_sph, bal):
    # analysis of snow impurities
    # ( the concentrations below 0.0001 are not reliable )
    # bf    normalized absorption coefficient of pollutants ay 1000nm ( in inverse mm)
    # bm    Angstroem absorption coefficient of pollutants ( around 1 - for soot, 3-7 for dust)

    ind_nonan = ~np.isnan(alb_sph.sel(band=0)) & ~np.isnan(alb_sph.sel(band=1))

    p1 = np.log(alb_sph.sel(band=0))**2
    p2 = np.log(alb_sph.sel(band=1))**2
    bm = np.log(p1 / p2) / np.log(wls.sel(band=1) / wls.sel(band=0))

    # type of pollutants
    ntype = 1 + (bm > 1.2)     # 1=soot, 2 = dust

    soda = (wls.sel(band=0)**bm).where(bm >= 0.1)
    bf = soda * p1 / bal

    # normalized absorption coefficient of pollutants at the wavelength  1000nm
    k_abs_0 = p1 / bal
    # bal   -effective absorption length in microns

    B_soot = 1.6        # enhancement factors for soot
    B_ice = 0.9       # enhancement factors for ice grains
    alfa_soot = 4. * np.pi * 0.47 / wls.sel(band=0)  # bulk soot absorption coefficient at 1000nm
    k_dust = 0.01       # volumetric absorption coefficient of dust

    conc = (ntype == 1) * B_soot * k_abs_0 / B_ice / alfa_soot + \
           (ntype == 2) * B_soot * k_abs_0 / k_dust

    ntype = ntype.where(bm > 0.5, 3)  # type is other or mixture
    ntype = ntype.where(bm < 10., 4)  # type is other or mixture

    return ntype.where(ind_nonan), bf.where(ind_nonan), conc.where(ind_nonan)


@numba.jit(nopython=True, cache=True)
def f(albedo, t1, t2, r0, ak1, ak2, ratm, r, toa_cor_o3):
    surf = t1 * t2 * r0 * albedo**(ak1 * ak2 / r0) / (1 - albedo * ratm)
    rs = r + surf
    return toa_cor_o3 - rs  # sl.alb2rtoa(albedo, t1, t2, r0, ak1, ak2, ratm, r)


@numba.jit(nopython=True, cache=True)
def zbrent(x0, x1, args=(), max_iter=100, tolerance=1e-6):
    # Equation solver using Brent's method
    # https://en.wikipedia.org/wiki/Brent%27s_method
    # Brent’s is essentially the Bisection method augmented with Inverse
    # Quadratic Interpolation whenever such a step is safe. At it’s worst case
    # it converges linearly and equal to Bisection, but in general it performs
    # superlinearly; it combines the robustness of Bisection with the speedy
    # convergence and inexpensive computation of Quasi-Newtonian methods.
    # Because of this, you’re likely to find Brent’s as a default root-finding
    # algorithm in popular libraries. For example, MATLAB’s fzero, used to find
    # the root of a nonlinear function, employs a variation of Brent’s.
    # Python script from https://nickcdryan.com/2017/09/13/root-finding-algorithms-in-python-line-search-bisection-secant-newton-raphson-boydens-inverse-quadratic-interpolation-brents/

    fx0 = f(x0, *args)
    fx1 = f(x1, *args)

#    print(str(fx0) + ", " + str(fx1))
    if ((fx0 * fx1) > 0):
        #        print("Root not bracketed "+str(fx0)+", "+str(fx1))
        #        assert ((fx0 * fx1) <= 0), ("-----Root not bracketed"+str(fx0)+", "+str(fx1))
        return -999

    if abs(fx0) < abs(fx1):
        x0, x1 = x1, x0
        fx0, fx1 = fx1, fx0

    x2, fx2 = x0, fx0

    d = x2  # any value is fine. It is not used at the first iteration

    mflag = True
    steps_taken = 0

    while steps_taken < max_iter and abs(x1-x0) > tolerance:
        fx0 = f(x0, *args)
        fx1 = f(x1, *args)
        fx2 = f(x2, *args)

        if fx0 != fx2 and fx1 != fx2:
            L0 = (x0 * fx1 * fx2) / ((fx0 - fx1) * (fx0 - fx2))
            L1 = (x1 * fx0 * fx2) / ((fx1 - fx0) * (fx1 - fx2))
            L2 = (x2 * fx1 * fx0) / ((fx2 - fx0) * (fx2 - fx1))
            new = L0 + L1 + L2

        else:
            new = x1 - ((fx1 * (x1 - x0)) / (fx1 - fx0))

        if ((new < ((3 * x0 + x1) / 4) or new > x1) or
            (mflag == True and (abs(new - x1)) >= (abs(x1 - x2) / 2)) or
            (mflag == False and (abs(new - x1)) >= (abs(x2 - d) / 2)) or
            (mflag == True and (abs(x1 - x2)) < tolerance) or
                (mflag == False and (abs(x2 - d)) < tolerance)):
            new = (x0 + x1) / 2
            mflag = True

        else:
            mflag = False

        fnew = f(new, *args)
        d, x2 = x2, x1

        if (fx0 * fnew) < 0:
            x1 = new
        else:
            x0 = new

        if abs(fx0) < abs(fx1):
            x0, x1 = x1, x0

        steps_taken += 1

    return x1


def compute_plane_albedo(OLCI_scene, snow, angles, compute_polluted=True):
    # ========= derivation of plane albedo and reflectance ===========
    snow['rp'] = snow.alb_sph ** angles.ak1
    snow['refl'] = snow.r0 * snow.alb_sph ** (angles.ak1 * angles.ak2 / snow.r0)

    ind_all_clean = snow.ind_clean | (snow.isnow == 7)

    # CalCULATION OF BBA of clean snow

    # old method: integrating equation
    # BBA_v = np.vectorize(sl.BBA_calc_clean)
    # p1,p2,s1,s2 = BBA_v(al[ind_all_clean], ak1[ind_all_clean])
    #
    # visible(0.3-0.7micron)
    # rp1[ind_all_clean]=p1/sol1_clean
    # rs1[ind_all_clean]=s1/sol1_clean
    # near-infrared (0.7-2.4micron)
    # rp2[ind_all_clean]=p2/sol2
    # rs2[ind_all_clean]=s2/sol2
    # shortwave(0.3-2.4 micron)
    # rp3[ind_all_clean]=(p1+p2)/sol3_clean
    # rs3[ind_all_clean]=(s1+s2)/sol3_clean

    # approximation
    # planar albedo
    # rp1 and rp2 not derived anymore

    # rp3[ind_all_clean] = sl.plane_albedo_sw_approx(D[ind_all_clean], cos_sza[ind_all_clean])
    snow['rp3'] = plane_albedo_sw_approx(snow.diameter, angles.cos_sza).where(ind_all_clean)
    #     spherical albedo
    # rs1 and rs2 not derived anymore
    snow['rs3'] = spher_albedo_sw_approx(snow.diameter).where(ind_all_clean)

    if compute_polluted:
        # calculation of the BBA for the polluted snow
        iind_pol = dict(xy=np.arange(len(snow.ind_pol))[snow.ind_pol])

        # rp1[iind_pol], rp2[iind_pol], rp3[iind_pol] = sl.BBA_calc_pol(rp[iind_pol], asol, sol1_pol, sol2, sol3_pol)
        # rs1[iind_pol], rs2[iind_pol], rs3[iind_pol] = sl.BBA_calc_pol(alb_sph[iind_pol], asol, sol1_pol, sol2, sol3_pol)

        _, _, snow.rp3[iind_pol] = BBA_calc_pol(snow.rp[iind_pol], asol, sol1_pol, sol2, sol3_pol)
        _, _, snow.rs3[iind_pol] = BBA_calc_pol(snow.alb_sph[iind_pol], asol, sol1_pol, sol2, sol3_pol)
        return snow


def funp(x, al, sph_calc, ak1):
    #     Spectral planar albedo
    # Inputs:
    # x                     input wavelength (should work with any)
    # ak1
    # al                    absorption length
    # sph_calc              sph_calc= 0 for planar =1 for spherical
    #
    # Constants:
    # xa(168),ya(168)       imaginary part (ya) of the refraction index at specified wavelength (xa)
    #
    # Outputs:
    # f1*funcs              ?
    #
    # bav 2020
    # using numpy interpolation

    y = np.interp(x, xa, ya)

    dega = 1000. * al * 4.*np.pi*y/x
    pow = np.sqrt(dega)

    if (pow >= 1.e-6):
        rsd = np.exp(-pow)
    else:
        rsd = 1.

    if (sph_calc == 0):
        rs = rsd**ak1
    elif (sph_calc == 1):
        rs = rsd

    if (x < 0.4):
        x = 0.4
    funcs = f0 + f1 * np.exp(-x * bet) + f2 * np.exp(-x * gam)

    return rs * funcs


def plane_albedo_sw_approx(D, cos_sza):
    anka = 0.7389 - 0.1783 * cos_sza + 0.0484 * cos_sza**2.
    banka = 0.0853 + 0.0414 * cos_sza - 0.0127 * cos_sza**2.
    canka = 0.1384 + 0.0762 * cos_sza - 0.0268 * cos_sza**2.
    diam1 = 187.89 - 69.2636 * cos_sza + 40.4821 * cos_sza**2.
    diam2 = 2687.25 - 405.09 * cos_sza + 94.5 * cos_sza**2.
    return anka + banka * np.exp(-1000 * D / diam1) + canka * np.exp(-1000 * D / diam2)


def spher_albedo_sw_approx(D):
    anka = 0.6420
    banka = 0.1044
    canka = 0.1773
    diam1 = 158.62
    diam2 = 2448.18
    return anka + banka * np.exp(-1000 * D / diam1) + canka * np.exp(-1000 * D / diam2)


def BBA_calc_clean(al, ak1):
    # for clean snow
    # plane albedo
    sph_calc = 0  # planar
    # visible(0.3-0.7micron)

    def func_integ(x):
        return funp(x, al, sph_calc, ak1)

    p1 = qsimp(func_integ, 0.3, 0.7)

    # near-infrared (0.7-2.4micron)
#        p2 = trapzd(func_integ,0.7,2.4, 20)
    p2 = qsimp(func_integ, 0.7, 2.4)

    # spherical albedo
    sph_calc = 1  # spherical calculation

    def func_integ(x):
        return funp(x, al, sph_calc, ak1)

    # visible(0.3-0.7micron)
#        s1 = trapzd(func_integ,0.3,0.7, 20)
    s1 = qsimp(func_integ, 0.3, 0.7)
    # near-infrared (0.7-2.4micron)
#        s2 = trapzd(func_integ,0.7,2.4, 20)
    s2 = qsimp(func_integ, 0.7, 2.4)
    # shortwave(0.3-2.4 micron)
    # END of clean snow bba calculation
    return p1, p2, s1, s2


@numba.jit(nopython=True)
def qsimp(func, a, b):
    # integrate function between a and b using simpson's method.
    # works as fast as scipy.integrate quad
    eps = 1.e-3
    jmax = 20
    ost = -1.e30
    os = -1.e30
    for j in range(jmax):
        if (j == 0):
            st = 0.5 * (b - a) * (func(a) + func(b))
        else:
            it = 2**(j - 1)
            tnm = it
            delta = (b - a) / tnm
            x = a+0.5 * delta
            sum = 0.
            for jj in range(it):
                sum = sum + func(x)
                x = x + delta
            st = 0.5*(st + (b - a) * sum / tnm)
        s = (4.*st - ost) / 3.
        if (j > 4):
            if (np.abs(s - os) < eps * np.abs(os)):
                return s
            if (s == 0) and (os == 0.):
                return s
        os = s
        ost = st
    print("Max iteration reached")
    return s


def BBA_calc_pol(alb, asol, sol1_pol, sol2, sol3_pol):
    # polluted snow
    # NEW CODE FOR BBA OF BARE ICE
    # alb is either the planar or spherical albedo

    # ANAlYTICal EQUATION FOR THE NOMINATOR
    # integration over 3 segments

    # segment 1
    # QUADRATIC POLYNOMIal for the range 400-709nm
    # input wavelength
    #    alam2=w[0]
    #    alam3=w[5]
    #    alam5=w[10]
    #    alam6=w[11]
    #    alam7=w[16]
    #    alam8=w[20]

    alam2 = 0.4
    alam3 = 0.56
    alam5 = 0.709
    alam6 = 0.753
    alam7 = 0.865
    alam8 = 1.02

    # input reflectances
    r2 = alb[0, :]
    r3 = alb[5, :]
    r5 = alb[10, :]
    r6 = alb[11, :]
    r7 = alb[16, :]
    r8 = alb[20, :]

    sa1, a1, b1, c1 = quad_func(alam2, alam3, alam5, r2, r3, r5)
    ajx1 = a1*sol1_pol
    ajx2 = b1*coef1
    ajx3 = c1*coef2

    aj1 = ajx1 + ajx2 + ajx3
    # segment 2.1
    # QUADRATIC POLYNOMIal for the range 709-865nm
    sa1, a2, b2, c2 = quad_func(alam5, alam6, alam7, r5, r6, r7)
    ajx1 = a2 * asol
    ajx2 = b2 * coef3
    ajx3 = c2 * coef4

    aj2 = ajx1 + ajx2 + ajx3    # segment 2.2
    # exponential approximation for the range 865- 2400 nm
    z1 = 0.865
    z2 = 2.4
    rati = r7 / r8
    alasta = (alam8 - alam7) / np.log(rati)
    an = 1. / alasta
    p = r7 * np.exp(alam7 / alasta)

    aj31 = (1. / an) * (np.exp(-an * z2) - np.exp(-an * z1))
    aj32 = (1. / (bet + an)) * (np.exp(-(bet + an) * z2) - np.exp(-(an + bet) * z1))
    aj33 = (1. / (gam + an)) * (np.exp(-(gam + an) * z2) - np.exp(-(an + gam) * z1))
    aj3 = (-f0 * aj31 - f1 * aj32 - f2 * aj33) * p

    BBA_vis = aj1 / sol1_pol
    BBA_nir = (aj2 + aj3) / sol2  # here segment 2.1 and 2.2 are summed
    BBA_sw = (aj1 + aj2 + aj3) / sol3_pol

    return BBA_vis, BBA_nir, BBA_sw


def quad_func(x0, x1, x2, y0, y1, y2):
    # quadratic function used for the polluted snow BBA calculation
    # see BBA_calc_pol
    # compatible with arrays
    d1 = (x0 - x1) * (x0 - x2)
    d2 = (x1 - x0) * (x1 - x2)
    d3 = (x2 - x0) * (x2 - x1)

    a1 = x1 * x2 * y0 / d1 + x0 * x2 * y1 / d2 + x0 * x1 * y2 / d3
    b1 = -(x1 + x2) * y0 / d1 - (x0 + x2) * y1 / d2 - (x0 + x1) * y2 / d3
    c1 = y0 / d1 + y1 / d2 + y2 / d3
    x = x1
    sa = a1 + b1 * x + c1 * x * x
    return sa, a1, b1, c1

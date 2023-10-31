# pySICEv2.1
#
# from FORTRAN VERSION 6.4
# Sept. 2022
#
# This code retrieves snow/ice  albedo and related snow products for clean Arctic
# atmosphere. The errors increase with the load of pollutants in air.
# Alexander  KOKHANOVSKY
# a.kokhanovsky@vitrocisetbelgium.com
# adapted to Python 3
# by Baptiste Vandecrux
# bav@geus.dk
#
# Latest update of python scripts: 15-08-2022 (bav@geus.dk)
#    - new values for iaginary part of refractive index of ice
#    - hard coded tg_vod.dat in constants
#
# Older update of python scripts: 22-10-2021 (bav@geus.dk)
# - code optimization by Ghislain Picard
#
# Older update of python scripts: 29-04-2021 (bav@geus.dk)
# - Fixed a bug in the indexing of the polluted pixels for which the spherical albedo equation could not be solved.  Solved the oultiers visible in bands 12-15 and 19-20 and  expended the BBA calculation to few pixels that fell out of the index.
# -compression of output
# - new backscatter fraction from Alex
# - new format for tg_vod.dat file
# **************************************************
#              How to run
# from command line:
#    > python sice.py [input data folder] [output folder]
# from spyder consol
#    > %run sice.py [input data folder] [output folder]
#
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
#
# Outputs:
# snow characteristics:
# isnow                     0 = clean snow, 1 = polluted snow
# ntype                     pollutant type: 1(soot), 2( dust), 3 and 4 (other or mixture)
# conc                      pollutant concentration is defined as the volumetric concentration
#                           of pollutants devided by the volumetric concentration of ice grains
# polut                        normalized absorption coefficient of pollutants ay 1000nm ( in inverse mm)
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
# rp1                       visible(0.33-0.7micron)
# rp2                       near-infrared (0.7-2.4micron)
# rp3                       shortwave(0.33-2.4 micron)shortwave(0.33-2.4 micron)
#
# spherical BBA
# rs1                       visible(0.33-0.7micron)
# rs2                       near-infrared (0.7-2.4micron)
# rs3                       shortwave(0.33-2.4 micron)shortwave(0.33-2.4 micron)
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
# salbed                    calculates albatm for albedo correction (?)
# zbrent                    equation solver
# sol                       solar spectrum
# analyt_func               calculation of surface radiance
# quad_func                 calculation of quadratic parameters
# funp                      snow spectral planar and spherical albedo function
import numpy as np
import sys
import time
import os
import xarray as xr
import numba

try:
    from pysice.sice_io1 import (
        sice_io,
        write_output,
        parse_args,
        get_input_folder,
        get_dem_folder,
        get_output_folder,
    )
except ImportError:
    from sice_io1 import (
        sice_io,
        write_output,
        parse_args,
        get_input_folder,
        get_dem_folder,
        get_output_folder,
    )

try:
    from pysice.constants2 import (
        wls,
        bai,
        xa,
        ya,
        f0,
        f1,
        f2,
        bet,
        gam,
        thv0,
        sol_vis,
        sol_nir,
        sol_sw,
        asol,
        cabsoz,
    )
except ImportError:
    from constants2 import (
        wls,
        bai,
        xa,
        ya,
        f0,
        f1,
        f2,
        bet,
        gam,
        thv0,
        sol_vis,
        sol_nir,
        sol_sw,
        asol,
        cabsoz,
    )

np.seterr(divide="ignore")
np.seterr(invalid="ignore")
os.environ["PYTROLL_CHUNK_SIZE"] = "256"


def view_geometry(OLCI_scene):
    # transfer of OLCI relative azimuthal angle to the definition used in
    # radiative transfer code
    # raa       relative azimuth angle
    # sza       solar zenith angle
    # vza       viewing zenith angle
    # cos_sa       cosine of the scattering angle
    # u1        escape function applied to SZA (from sun to surface)
    # u2        escape function applied to VZA (from surface to satellite)
    raa = 180.0 - (OLCI_scene.vaa - OLCI_scene.saa)
    sin_sza = np.sin(np.deg2rad(OLCI_scene.sza))
    sin_vza = np.sin(np.deg2rad(OLCI_scene.vza))
    cos_sza = np.cos(np.deg2rad(OLCI_scene.sza))
    cos_vza = np.cos(np.deg2rad(OLCI_scene.vza))
    # u1 = 3.*(1.+2.*cos_sza)/7
    # u2 = 3.*(1.+2.*cos_vza)/7
    # new escape functions (update 2022):
    u1 = 3 / 5 * cos_sza + 1 / 3 + np.sqrt(cos_sza) / 3.0
    u2 = 3 / 5 * cos_vza + 1 / 3 + np.sqrt(cos_vza) / 3.0
    cos_raa = np.cos(np.deg2rad(raa))
    inv_cos_za = 1.0 / cos_sza + 1.0 / cos_vza
    cos_sa = -cos_sza * cos_vza + sin_sza * sin_vza * cos_raa
    theta = np.arccos(cos_sa) * 180 / np.pi

    angles = xr.Dataset()
    angles["raa"] = raa
    angles["cos_sza"] = cos_sza
    angles["cos_vza"] = cos_vza
    angles["u1"] = u1
    angles["u2"] = u2
    angles["inv_cos_za"] = inv_cos_za
    angles["cos_sa"] = cos_sa
    angles["theta"] = theta
    return angles


def rinff(cos_sza, cos_vza, theta):
    # this is the "theoretical" value for R0, the reflectance of a
    # semi-infinite non-absorbing snow layer
    a = 1.247
    b = 1.186
    c = 5.157
    p = 11.1 * np.exp(-0.087 * theta) + 1.1 * np.exp(-0.014 * theta)
    return (
        (a + b * (cos_sza + cos_vza) + c * cos_sza * cos_vza + p)
        / 4.0
        / (cos_sza + cos_vza)
    )


def prepare_processing(OLCI_scene, angles, compute_polluted=True):
    # Filtering pixels unsuitable for retrieval
    snow = xr.Dataset()
    snow["isnow"] = OLCI_scene["sza"] * np.nan
    snow["isnow"] = xr.where(OLCI_scene.toa.sel(band=20) < 0.1, 102, snow.isnow)
    snow["isnow"] = xr.where(OLCI_scene.toa.sel(band=0) < 0.2, 103, snow.isnow)
    snow["isnow"] = xr.where(OLCI_scene.sza > 80, 100, snow.isnow)
    snow["isnow"] = xr.where(OLCI_scene["sza"].isnull(), 999, snow.isnow)

    mask = snow.isnow.isnull()
    OLCI_scene["toa"] = OLCI_scene.toa.where(mask)
    OLCI_scene["vaa"] = OLCI_scene.vaa.where(mask)
    OLCI_scene["saa"] = OLCI_scene.saa.where(mask)
    OLCI_scene["sza"] = OLCI_scene.sza.where(mask)
    OLCI_scene["vza"] = OLCI_scene.vza.where(mask)
    OLCI_scene["elevation"] = OLCI_scene.elevation.where(mask)

    # snow indexes
    snow["ndsi"] = (OLCI_scene.toa.sel(band=16) - OLCI_scene.toa.sel(band=20)) / (
        OLCI_scene.toa.sel(band=16) + OLCI_scene.toa.sel(band=20)
    )
    snow["ndbi"] = (OLCI_scene.toa.sel(band=0) - OLCI_scene.toa.sel(band=20)) / (
        OLCI_scene.toa.sel(band=0) + OLCI_scene.toa.sel(band=20)
    )

    # case of not 100% snow cover:
    snow["isnow"] = xr.where(snow.isnow.isnull(), 1, snow.isnow)

    if compute_polluted:
        msk = OLCI_scene.toa.sel(band=0) < thv0
        snow["isnow"] = xr.where(msk & (snow.isnow == 1), 3, snow.isnow)

        # scaling factor for patchy snow at 400nm
        psi = rinff(angles["cos_sza"], angles["cos_vza"], angles["theta"])
        # factor=snow fraction ( SMALLER THAN 1.0):
        snow["factor"] = xr.where(msk, OLCI_scene.toa.sel(band=0) / psi, 1)

        # snow TOA corrected for snow fraction
        OLCI_scene["toa"] = xr.where(
            msk, OLCI_scene["toa"] / snow["factor"], OLCI_scene["toa"]
        )
    else:
        snow["factor"] = OLCI_scene["sza"] * 0 + 1
    return OLCI_scene, snow


def snow_properties(OLCI_scene, angles, snow):
    # retrieval of snow properties ( R_0, size of grains from OLCI channels 865[17] and 1020nm[21] assumed not influenced by atmospheric scattering and absorption processes)
    # imaginary part of the ice refractive index at 865 and 1020nm
    akap3 = 2.40e-7
    akap4 = 2.25e-6
    # bulk absoprtion coefficient of ice at 1020nm
    alt3 = 4.0 * np.pi * akap3 / 0.865
    alt4 = 4.0 * np.pi * akap4 / 1.02
    eps = 1 / (1 - np.sqrt(alt3 / alt4))
    # consequently: 1-eps = 1/(1-np.sqrt(alpha2/alpha1))

    # reflectivity of nonabsorbing snow layer
    rr1 = OLCI_scene.toa.sel(band=16)
    rr2 = OLCI_scene.toa.sel(band=20)
    
    rr_th4 = OLCI_scene.toa.sel(band=3)
    rr_th21 = OLCI_scene.toa.sel(band=20)
    
    r0 = (rr1 ** eps) * (rr2 ** (1.0 - eps))
    
    th = (rr_th4 - rr_th21)/(rr_th21 + rr_th4)

    # effective absorption length(mm)
    bal = (np.log(rr2 / r0) / (angles.u1 * angles.u2 / r0)) ** 2 / alt4
    al = bal / 1000.0

    # effective grain size(mm):diameter
    # B/(1-g) = 9.2
    D = al / (9.2 * 16 / 9)
    # Alex 2022:
    # B/(1-g) = 9
    # D = al / 16
    # snow specific area ( dimension: m*m/kg)
    area = 6.0 / D / 0.917

    # filtering small D
    diameter_thresh = 0.1
    valid = D >= diameter_thresh
    snow["isnow"] = xr.where((D < 0.1) & (snow.isnow < 100), 104, snow.isnow)
    OLCI_scene["toa"] = OLCI_scene.toa.where(valid)
    snow["diameter"] = D.where(valid)
    snow["area"] = area.where(valid)
    snow["al"] = al.where(valid)
    snow["r0"] = r0.where(valid)
    snow["th"] = th.where(valid)
    snow["bal"] = bal.where(valid)
    angles = angles.where(valid)
    return OLCI_scene, angles, snow


def aerosol_properties(height, cos_sa, aot, aer_ang):
    # Atmospheric optical thickness
    tauaer = (aot * (wls / 0.5) ** (-aer_ang)).transpose()
    # gaer = g0 + g1 * np.exp(-wls / wave0)
    gaer = 0.5263 + 0.4627 * np.exp(-wls / 0.4685)
    pr = 0.75 * (1.0 + cos_sa ** 2)

    # 2021 version:
    # taumol = wls**(-4.05) * np.minimum(1, np.exp(-height / 7400)) * 0.00877
    # MOLEC = 1 version:
    taumol = 0.008735 * wls ** (-4.08) * xr.ones_like(height)
    taumol = xr.where(
        (height * xr.ones_like(wls) / 6000) > 0, taumol * np.exp(-height / 6000), taumol
    )
    # MOLEC = 0 version:
    # taumol=0.0053/wls**(4.0932)

    tau = tauaer + taumol

    # HG phase function for aerosol
    # pa = (1 - g**2) / (1. - 2. * g * cos_sa + g**2)**1.5
    # p = (taumol * pr + tauaer * pa) / tau   # the order is critical to have the right order of dims (band, xy)
    g11 = 0.80
    g22 = -0.45
    pa1 = (1 - g11 * g11) / (1.0 - 2.0 * g11 * cos_sa + g11 * g11) ** 1.5
    pa2 = (1 - g22 * g22) / (1.0 - 2.0 * g22 * cos_sa + g22 * g22) ** 1.5
    cp = (gaer - g11) / (g11 - g22)
    pa = cp * pa1 + (1.0 - cp) * pa2

    pr = 0.75 * (1.0 + cos_sa * cos_sa)
    p = (taumol * pr + tauaer * pa) / tau

    # aerosol asymmetry parameter
    g = tauaer * gaer / tau

    aerosol = xr.Dataset()
    aerosol["tau"] = tau
    aerosol["p"] = p
    aerosol["g"] = g
    aerosol["gaer"] = gaer
    aerosol["taumol"] = taumol
    aerosol["tauaer"] = tauaer
    return aerosol


def prepare_coef(aerosol, angles):
    args = (
        aerosol.tau,
        aerosol.g,
        aerosol.p.transpose(),
        angles.cos_sza,
        angles.cos_vza,
        angles.inv_cos_za,
        aerosol.gaer,
        aerosol.taumol.transpose(),
        aerosol.tauaer,
    )
    inputdims = tuple([d.dims for d in args])
    outputdims = [aerosol.tau.dims, aerosol.tauaer.dims, aerosol.tau.dims]
    t1t2, albatm, r = xr.apply_ufunc(
        prepare_coef_numpy,
        *args,
        input_core_dims=inputdims,
        output_core_dims=outputdims,
    )

    # t1t2, albatm, r = prepare_coef_xarray(
    #     aerosol.tau,
    #     aerosol.g,
    #     aerosol.p,
    #     angles.cos_sza,
    #     angles.cos_vza,
    #     angles.inv_cos_za,
    #     aerosol.gaer,
    #     aerosol.taumol,
    #     aerosol.tauaer,
    # )

    atmosphere = xr.Dataset()
    atmosphere["t1t2"] = t1t2
    atmosphere["albatm"] = albatm
    atmosphere["r"] = r
    return atmosphere


@numba.jit(nopython=True, cache=True)
def prepare_coef_numpy(tau, g, p, cos_sza, cos_vza, inv_cos_za, gaer, taumol, tauaer):
    # atmospheric reflectance
    b1 = 1.0 + 1.5 * cos_sza + (1.0 - 1.5 * cos_sza) * np.exp(-tau / cos_sza)
    b2 = 1.0 + 1.5 * cos_vza + (1.0 - 1.5 * cos_vza) * np.exp(-tau / cos_vza)

    sumcos = cos_sza + cos_vza

    astra = (1.0 - np.exp(-tau * inv_cos_za)) / sumcos / 4.0
    oskar = 4.0 + 3.0 * (1 - g) * tau
    # multiple scattering contribution to the atmospheric reflectance
    rms = (
        1.0
        - b1 * b2 / oskar
        + (3.0 * (1.0 + g) * (cos_sza * cos_vza) - 2.0 * sumcos) * astra
    )

    ratm = p * astra + rms  # called ratm in new fortran code

    # atmospheric transmittance (updated 2022)
    tz = 1.0 + gaer ** 2 + (1.0 - gaer ** 2) * np.sqrt(1.0 + gaer ** 2)
    Baer = 0.5 + gaer * (gaer ** 2 - 3.0) / tz / 2.0
    # if gaer >= 1.e-3:
    #     Baer=(1 - gaer) * ((1 + gaer) / np.sqrt(1.+gaer**2) - 1) / 2 / gaer
    Baer[gaer >= 0.001] = (
        (1 - gaer) * ((1 + gaer) / np.sqrt(1.0 + gaer ** 2) - 1) / 2 / gaer
    )
    B = (0.5 * taumol +(Baer * tauaer.transpose()).transpose()) / tau
    t1t2 = np.exp(-B * tau / cos_sza) * np.exp(-B * tau / cos_vza)

    # atmospheric spherical albedo (updated 2022)
    gasa = 0.5772157
    y = (1.0 + tau) * tau * np.exp(-tau) / 4.0
    z3 = tau ** 2 * (-np.log(tau) - gasa)
    z4 = tau ** 2 * (tau - tau ** 2 / 4 + tau ** 3 / 18)
    Z = z3 + z4
    W1 = 1 + (1.0 + 0.5 * tau) * Z / 2 - y
    W2 = 1 + 0.75 * tau * (1.0 - g)
    albatm = 1 - W1 / W2
    return t1t2, albatm, ratm


# def prepare_coef_xarray(tau, g, p, cos_sza, cos_vza, inv_cos_za, gaer, taumol, tauaer):
#     # atmospheric reflectance
#     b1 = 1.0 + 1.5 * cos_sza + (1.0 - 1.5 * cos_sza) * np.exp(-tau / cos_sza)
#     b2 = 1.0 + 1.5 * cos_vza + (1.0 - 1.5 * cos_vza) * np.exp(-tau / cos_vza)

#     sumcos = cos_sza + cos_vza

#     astra = (1.0 - np.exp(-tau * inv_cos_za)) / sumcos / 4.0
#     oskar = 4.0 + 3.0 * (1 - g) * tau
#     # multiple scattering contribution to the atmospheric reflectance
#     rms = (
#         1.0
#         - b1 * b2 / oskar
#         + (3.0 * (1.0 + g) * (cos_sza * cos_vza) - 2.0 * sumcos) * astra
#     )

#     ratm = p * astra + rms  # called ratm in new fortran code

#     # atmospheric transmittance (updated 2022)
#     tz = 1.0 + gaer ** 2 + (1.0 - gaer ** 2) * np.sqrt(1.0 + gaer ** 2)
#     Baer = 0.5 + gaer * (gaer ** 2 - 3.0) / tz / 2.0
#     # if gaer >= 1.e-3:
#     #     Baer=(1 - gaer) * ((1 + gaer) / np.sqrt(1.+gaer**2) - 1) / 2 / gaer
#     Baer = xr.where(
#         gaer >= 0.001,
#         (1 - gaer) * ((1 + gaer) / np.sqrt(1.0 + gaer ** 2) - 1) / 2 / gaer,
#         Baer,
#     )
#     B = (0.5 * taumol + Baer * tauaer) / tau
#     t1t2 = np.exp(-B * tau / cos_sza) * np.exp(-B * tau / cos_vza)

#     # atmospheric spherical albedo (updated 2022)
#     gasa = 0.5772157
#     y = (1.0 + tau) * tau * np.exp(-tau) / 4.0
#     z3 = tau ** 2 * (-np.log(tau) - gasa)
#     z4 = tau ** 2 * (tau - tau ** 2 / 4 + tau ** 3 / 18)
#     Z = z3 + z4
#     W1 = 1 + (1.0 + 0.5 * tau) * Z / 2 - y
#     W2 = 1 + 0.75 * tau * (1.0 - g)
#     albatm = 1 - W1 / W2
#     return t1t2, albatm, ratm


def snow_albedo_solved(
    OLCI_scene, angles, aerosol, atmosphere, snow, compute_polluted=True
):
    snow["alb_sph"] = OLCI_scene.toa * np.nan
    snow["rp"] = OLCI_scene.toa * np.nan
    snow["refl"] = OLCI_scene.toa * np.nan

    # solving iteratively the transcendental equation
    # Update 2022: for all pixels!

    if snow.r0.notnull().any():
        iind_solved = dict(xy=snow.xy.values[snow.r0.notnull().values])
        snow.alb_sph.loc[iind_solved] = 1
    
        def solver_wrapper(toa, tau, t1t2, r0, u1, u2, albatm, r):
            # it is assumed that albedo is in the range 0.1-1.0
            return zbrent(
                0.1,
                1,
                args=(t1t2, r0, u1, u2, albatm, r, toa),
                max_iter=100,
                tolerance=1e-10,
            )
    
        solver_wrapper_v = np.vectorize(solver_wrapper)
    
        # loop over all bands
        for i_channel in range(21):
            snow.alb_sph.sel(band=i_channel).loc[iind_solved] = solver_wrapper_v(
                OLCI_scene.toa.sel(band=i_channel).loc[iind_solved],
                aerosol.tau.sel(band=i_channel).loc[iind_solved],
                atmosphere.t1t2.sel(band=i_channel).loc[iind_solved],
                snow.r0.loc[iind_solved],
                angles.u1.loc[iind_solved],
                angles.u2.loc[iind_solved],
                atmosphere.albatm.sel(band=i_channel).loc[iind_solved],
                atmosphere.r.sel(band=i_channel).loc[iind_solved],
            )
    
            ind_bad = snow.alb_sph.sel(band=i_channel) < 0
            snow.alb_sph.loc[dict(band=i_channel)] = xr.where(
                ind_bad, 1, snow.alb_sph.sel(band=i_channel)
            )
    
        # correcting the retrived spherical albedo for fractional snow cover
        snow["rp"] = snow.factor * (snow.alb_sph ** angles.u1)
        snow["refl"] = (
            snow.factor * snow.r0 * snow.alb_sph ** (angles.u1 * angles.u2 / snow.r0)
        )
        snow["alb_sph"] = snow["factor"] * snow["alb_sph"]
    
        if compute_polluted:
            ind_no_nan = snow["isnow"].notnull()
            snow["isnow"] = xr.where(snow.alb_sph.sel(band=0) > 0.98, 1, snow.isnow)
            snow["isnow"] = xr.where(
                (snow.alb_sph.sel(band=0) <= 0.98) & (snow.factor > 0.99), 2, snow.isnow
            )
            snow["isnow"] = xr.where(
                (snow.alb_sph.sel(band=0) <= 0.98) & (snow.factor <= 0.99), 3, snow.isnow
            )
            snow["isnow"] = snow["isnow"].where(ind_no_nan)
    return OLCI_scene, snow


@numba.jit(nopython=True, cache=True)
def f(albedo, t1t2, r0, u1, u2, albatm, ratm, toa):
    rsurf = t1t2 * r0 * albedo ** (u1 * u2 / r0) / (1 - albedo * albatm)
    r = ratm + rsurf
    return toa - r


def snow_impurities(snow):
    # analysis of snow impurities
    # ( the concentrations below 0.0001 are not reliable )
    # polut    normalized absorption coefficient of pollutants ay 1000nm ( in inverse mm)
    # bm    Angstroem absorption coefficient of pollutants ( around 1 - for soot, 3-7 for dust
    r1 = snow.alb_sph.sel(band=0)
    r2 = snow.alb_sph.sel(band=3)

    ind_nonan = ~np.isnan(r1) & ~np.isnan(r2)

    p1 = np.log(r1) ** 2
    p2 = np.log(r2) ** 2
    msk = (r1 <= 0.999) & (r2 <= 0.999)
    zara = xr.where(msk, p1 / p2, 1)

    # 1-retrieved absorption Angström exponent (AAE):
    bm = np.log(zara) / np.log(wls.sel(band=3) / wls.sel(band=0))
    bm = xr.where(bm <= 0.9, 0, bm)

    # 2-retrieved pollution load coefficient (PLC), 1/mm:
    polut = xr.where(bm > 0.9, wls.sel(band=0) ** bm * p1 / snow.al, 0)

    # type of pollutants
    ntype = 2 - (bm >= 1.2)  # 1=dust, 2 = soot, 0 = no impurity retrieved
    ntype = xr.where(bm > 0.9, ntype, 0)

    # special case of soot impurities:
    msk_soot = (bm > 0) & (bm < 1.2)
    aload_ppm = xr.where(msk_soot, polut / 2.06e3, 0)

    msk_low_soot = msk_soot & (aload_ppm <= 2)
    aload_ppm = xr.where(msk_low_soot, 0, aload_ppm)
    bm = xr.where(msk_low_soot, 0, bm)
    polut = xr.where(msk_low_soot, 0, polut)

    msk = msk_soot & (snow.factor < 0.99)
    snow["isnow"] = xr.where(msk, 3, snow.isnow)

    # DUST IMPURITIES:
    # 3- retrieved effective diameter of dust grains:
    deff = 39.7373 - 11.8195 * bm + 0.8325 * bm * bm
    # 4- retrieved volumetric absorption coefficient of dust impurities
    # at the wavelength 1 micron      (1/mm)
    absor1 = 10.916 - 2.0831 * bm + 0.5441 * bm * bm
    # mass absorption coefficient (MAC) of dust in snow ( cm**3/g/mm)
    densi = 2.65 / 0.917
    aload = 1.8 * densi * polut / absor1
    # 5- retrieved impurity load (ppmw- ppm weight):
    aload_ppm = 1.0e6 * aload
    # 6- retrieved mass absorption coefficient (MAC) of dust in snow at 1000nm(m**2/g)
    dens2 = 2.65  # density of dust
    absor1000 = absor1 / dens2 * 1.0e-3
    # 7-retrieved mass absorption coefficient (MAC) of dust in snow at 660nm(m**2/g)
    absef660 = absor1000 * (0.660) ** (-bm)

    # no retrieval for too low impurity load (below 2ppm):
    msk_low_imp = (aload_ppm <= 2) & (bm >= 1.2)
    deff = xr.where(msk_low_imp, 0, deff)
    absor1 = xr.where(msk_low_imp, 0, absor1)
    absef660 = xr.where(msk_low_imp, 0, absef660)
    absor1000 = xr.where(msk_low_imp, 0, absor1000)
    bm = xr.where(msk_low_imp, 0, bm)
    polut = xr.where(msk_low_imp, 0, polut)
    aload_ppm = xr.where(msk_low_imp, 0, aload_ppm)

    aload_ppm = xr.where(bm < 0.9, 0, aload_ppm)
    bm = xr.where(bm > 10, 0, bm)
    aload_ppm = xr.where(bm > 10, 0, aload_ppm)
    bm = xr.where(bm < 0.9, 0, bm)

    impurities = xr.Dataset()
    impurities["ntype"] = ntype.where(ind_nonan)
    impurities["polut"] = polut.where(ind_nonan)
    impurities["bm"] = bm.where(ind_nonan)
    impurities["aload_ppm"] = aload_ppm.where(ind_nonan)
    impurities = xr.where(snow.isnow != 3, impurities, 0)
    return impurities


def snow_albedo_direct(angles, aerosol, atmosphere, snow, impurities):
    # direct caluclation including impurities
    # not sure where it is used

    alpha = 1000.0 * 4.0 * np.pi * (bai / wls)
    sdu = impurities.polut * wls ** (-impurities.bm)
    snow["alb_sph_direct"] = snow.factor * np.exp(-np.sqrt((alpha + sdu) * snow.al))
    snow["rp_direct"] = snow.alb_sph_direct ** angles.u1
    snow["refl_direct"] = (
        snow.factor * snow.r0 * snow.alb_sph_direct ** (angles.u1 * angles.u2 / snow.r0)
    )
    return snow


def ozone_retrieval(OLCI_scene, snow, angles):
    tt620 = OLCI_scene.toa.sel(band=6) / snow.refl_direct.sel(band=6)
    # calculation of gaseous vertical optical depth:
    vodka = -np.log(tt620) / angles.inv_cos_za
    tocos = vodka.where(vodka > 0) * 9349.3
    difoz = 100 * (tocos - OLCI_scene.ozone / 2.1415e-5) / tocos
    snow["tocos"] = tocos
    snow["difoz"] = np.abs(difoz)
    return snow


def spectral_toa_modelling(OLCI_scene, snow, angles, atmosphere):
    # snow reflectance at 620nm in absence of ozone absorption:
    DARM = 4.0 * np.pi * 8.58e-9 / (1.0e-3 * 0.620)
    reska = np.exp(-np.sqrt(DARM * snow.al))
    rozone = snow.r0 * np.exp(
        -(angles.u1 * angles.u2 / snow.r0) * np.sqrt(DARM * snow.al)
    )

    # gaseous transmittance at 620nm:
    TOAOZ = atmosphere.r.sel(band=6) + atmosphere.t1t2.sel(band=6) * rozone / (
        1.0 - reska * atmosphere.albatm.sel(band=6)
    )
    T620 = OLCI_scene.toa.sel(band=6) / TOAOZ

    # calculation of gaseous transmittance at 620, 940, and 761nm:
    tt761 = OLCI_scene.toa.sel(band=12) / snow.refl_direct.sel(band=12)
    tt940 = OLCI_scene.toa.sel(band=19) / snow.refl_direct.sel(band=19)

    # calculation of TOA reflectance at 620 nm
    r_toa_mod = atmosphere.r + atmosphere.t1t2 * snow.r0 * snow.factor * (
        snow.alb_sph / snow.factor
    ) ** (angles.u1 * angles.u2 / snow.r0) / (
        1 - (snow.alb_sph / snow.factor) * atmosphere.albatm
    )

    r_toa_mod = xr.where(snow.alb_sph > 0.05, r_toa_mod, 1)

    tt620 = OLCI_scene.toa.sel(band=6) / r_toa_mod.sel(band=6)

    abs620 = 4.4871e-2
    tozone = T620 ** (cabsoz / abs620)

    TOX = xr.ones_like(r_toa_mod)
    TVODA = xr.ones_like(r_toa_mod)
    TOX.loc[{'band': 12}] = (tt761 ** 1).values
    TOX.loc[{'band': 13}] = tt761 ** 0.532
    TOX.loc[{'band': 14}] = tt761 ** 0.074
    TVODA.loc[{'band': 18}] = tt940 ** 0.25
    TVODA.loc[{'band': 19}] = tt940 ** 1.0
    r_toa_mod = r_toa_mod * TVODA * TOX * tozone * snow.factor

    # calculating difference between modelled and observed r_TOA
    band_list = np.arange(21)
    SE = (OLCI_scene.toa.sel(band=band_list) - r_toa_mod.sel(band=band_list)) ** 2
    RMSE = np.sqrt(SE.mean(dim="band"))
    cv1 = 100 * RMSE / OLCI_scene.toa.mean(dim="band")

    band_list = np.append(np.arange(12), np.array([15, 16, 17, 20]))
    SE = (OLCI_scene.toa.sel(band=band_list) - r_toa_mod.sel(band=band_list)) ** 2
    RMSE = np.sqrt(SE.mean(dim="band"))
    cv2 = 100 * RMSE / OLCI_scene.toa.sel(band=band_list).mean(dim="band")

    snow["cv1"] = cv1
    snow["cv2"] = cv2
    return snow


def compute_BBA(OLCI_scene, snow, angles, compute_polluted=True):
    # CalCULATION OF BBA of clean snow
    # Original method: Recalculating spectrum and integrating it.
    # This is the exact, but slow mehtod to calculate clean snow BBA.
    # For each clean pixel, the derived spectrum is caluclated from u1, al and
    # the imaginary part of the refraction index at specified wavelength.
    # This scaling is done in function funp below. Then this function is
    # integrated uing the qsimp method.
    # BBA_v = np.vectorize(BBA_calc_clean)
    # p1,p2,s1,s2 = BBA_v(al[ind_all_clean], u1[ind_all_clean])
    #
    # visible(0.33-0.7micron)
    # rp1[ind_all_clean]=p1/sol_vis
    # rs1[ind_all_clean]=s1/sol_vis
    # near-infrared (0.7-2.4micron)
    # rp2[ind_all_clean]=p2/sol_nir
    # rs2[ind_all_clean]=s2/sol_nir
    # shortwave(0.33-2.4 micron)
    # rp3[ind_all_clean]=(p1+p2)/sol_sw
    # rs3[ind_all_clean]=(s1+s2)/sol_sw

    # 2022 exact:
    # snow['rp3'] = snow['al']*np.nan
    # snow['rs3'] = snow['al']*np.nan

    # ind_clean = (snow.isnow == 1)
    # iind_clean = np.arange(len(ind_clean))[ind_clean]
    # for i in iind_clean:
    #     if np.isnan(snow.al[{'xy':i}]):
    #         continue

    #     _, _, snow.rp3[{'xy':i}] = BBA_calc_clean(float(snow.al[{'xy':i}].values),
    #                                               float(angles.u1[{'xy':i}].values), mode='planar')
    #     _, _, snow.rs3[{'xy':i}] = BBA_calc_clean(snow.al[{'xy':i}].values,
    #                                               angles.u1[{'xy':i}].values, mode='spherical')

    # 2022 approximation:
    # planar albedo
    # rp1 and rp2 not derived anymore
    snow["rp3"] = 0.5271 + 0.3612 * np.exp(-angles.u1 * np.sqrt(0.02350 * snow.al))
    # rvis = np.exp(-angles.u1*np.sqrt (7.86e-5*snow.al))
    # rnir = 0.2335+0.56*np.exp(-angles.u1*np.sqrt(0.0327*snow.al))

    # spherical albedo
    # rs1 and rs2 not derived anymore
    snow["rs3"] = 0.5271 + 0.3612 * np.exp(-np.sqrt(0.02350 * snow.al))
    # rviss = np.exp(-np.sqrt (7.86e-5*snow.al))
    # rnirs = 0.2335+0.56*np.exp(-np.sqrt(0.0327*snow.al))

    if compute_polluted:
        # calculation of the BBA for the polluted snow
        ind_pol = (snow.isnow == 2) | (snow.isnow == 3)
        iind_pol = dict(xy=snow.xy.values[ind_pol])

        # rp1[iind_pol], rp2[iind_pol], rp3[iind_pol] = BBA_calc_pol(rp[iind_pol], asol, sol_vis, sol_nir, sol_sw)
        # rs1[iind_pol], rs2[iind_pol], rs3[iind_pol] = BBA_calc_pol(alb_sph[iind_pol], asol, sol_vis, sol_nir, sol_sw)
        _, _, snow.rp3.loc[iind_pol] = BBA_calc_pol(
            snow.rp.loc[iind_pol].values.T, asol, sol_vis, sol_nir, sol_sw
        )
        _, _, snow.rs3.loc[iind_pol] = BBA_calc_pol(
            snow.alb_sph.loc[iind_pol].values.T, asol, sol_vis, sol_nir, sol_sw
        )
    msk = OLCI_scene.toa.sel(band=0) < thv0
    snow["rp3"] = xr.where(msk, snow["rp3"] * snow.factor, snow["rp3"])
    # rvis = xr.where(msk, rvis*snow.factor, rvis)
    # rnir = xr.where(msk, rnir*snow.factor, rnir)

    snow["rs3"] = xr.where(msk, snow["rs3"] * snow.factor, snow["rs3"])
    # rviss = xr.where(msk, rviss*snow.factor, rviss)
    # rnirs = xr.where(msk, rnirs*snow.factor, rnirs)
    return snow


@numba.jit(nopython=True)
def funp(x, al, sph_calc, u1):
    #     Spectral planar albedo
    # Original way to recalculate the spectral albedo from al, u1 and the
    # ice refraction index.
    # Currently not used. But do not remove.
    # Inputs:
    # x                     input wavelength (should work with any)
    # u1
    # al                    absorption length
    # sph_calc              sph_calc= 0 for planar =1 for spherical
    #
    # Constants:
    # xa(168),ya(168)       imaginary part (ya) of the refraction index at specified wavelength (xa)
    #
    # Outputs:
    # f1*solar_flux
    # bav 2020
    # using numpy interpolation

    y = np.interp(x, xa, ya)
    dega = 1000.0 * al * 4.0 * np.pi * y / x
    pow = np.sqrt(dega)
    if pow >= 1.0e-6:
        rsd = np.exp(-pow)
    else:
        rsd = 1.0

    rs = rsd
    if sph_calc == 0:
        rs = rsd ** u1

    if x < 0.33:
        solar_flux = 0
    else:
        solar_flux = f0 + f1 * np.exp(-x * bet) + f2 * np.exp(-x * gam)
    return rs * solar_flux


def BBA_calc_clean(al, u1, mode="spherical"):
    # CalCULATION OF BBA of clean snow
    # Original method: Recalculating spectrum and integrating it.
    # This is the exact, but slow mehtod to calculate clean snow BBA.
    # For each clean pixel, the derived spectrum is caluclated from u1, al and
    # the imaginary part of the refraction index at specified wavelength.
    # This scaling is done in function funp below. Then this function is
    # integrated uing the qsimp method.
    # Currently not used. But do not remove.

    if mode == "spherical":
        sph_calc = 1  # spherical BBA
    elif mode == "planar":
        sph_calc = 0  # planar BBA

    def func_integ(x):
        return funp(x, al, sph_calc, u1)

    # visible(0.33-0.7micron)
    flux_vis = qsimp(func_integ, 0.33, 0.7)

    # near-infrared (0.7-2.4micron)
    flux_nir = qsimp(func_integ, 0.7, 2.4)

    # shortwave(0.3-2.4 micron)
    bba_vis = flux_vis / sol_vis
    bba_nir = flux_nir / sol_nir
    bba_sw = (flux_vis + flux_nir) / sol_sw
    return bba_vis, bba_nir, bba_sw


# @numba.jit(nopython=False)
def qsimp(func, a, b):
    # integrate function between a and b using simpson's method.
    # works as fast as scipy.integrate quad
    eps = 1.0e-3
    jmax = 20
    ost = -1.0e30
    os = -1.0e30
    for j in range(jmax):
        if j == 0:
            st = 0.5 * (b - a) * (func(a) + func(b))
        else:
            it = 2 ** (j - 1)
            tnm = it
            delta = (b - a) / tnm
            x = a + 0.5 * delta
            sum = 0.0
            for jj in range(it):
                sum = sum + func(x)
                x = x + delta
            st = 0.5 * (st + (b - a) * sum / tnm)
        s = (4.0 * st - ost) / 3.0
        if j > 4:
            if np.abs(s - os) < eps * np.abs(os):
                return s
            if (s == 0) and (os == 0.0):
                return s
        os = s
        ost = st
    print("Max iteration reached")
    return s


@numba.jit(nopython=True, cache=True)
def BBA_calc_pol(alb, asol, sol_vis, sol_nir, sol_sw):
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

    # QUADRATIC POLYNOMIal for the range 400-709nm
    # on this section r_fit(lambda) = a1 + b1 * lambda + c1 * lambda**2
    _, a1, b1, c1 = quad_func(alam2, alam3, alam5, r2, r3, r5)
    coef1, coef2 = analyt_func(0.33, 0.7)
    ajx1 = a1 * sol_vis
    ajx2 = b1 * coef1
    ajx3 = c1 * coef2

    aj1 = ajx1 + ajx2 + ajx3

    # QUADRATIC POLYNOMIal for the range 709-865nm
    # on this section r_fit(lambda) = a2 + b2 * lambda + c2 * lambda**2
    _, a2, b2, c2 = quad_func(alam5, alam6, alam7, r5, r6, r7)
    coef3, coef4 = analyt_func(0.7, 0.865)
    ajx1 = a2 * asol
    ajx2 = b2 * coef3
    ajx3 = c2 * coef4
    aj2 = ajx1 + ajx2 + ajx3

    # exponential approximation for the range 865- 2400 nm
    # on this section r_fit(lambda) = p * exp(-an * lambda)
    rati = r7 / r8
    alasta = (alam8 - alam7) / np.log(rati)
    an = 1.0 / alasta
    p = r7 * np.exp(alam7 / alasta)

    z1 = 0.865
    z2 = 2.4
    aj31 = (1.0 / an) * (np.exp(-an * z2) - np.exp(-an * z1))
    aj32 = (1.0 / (bet + an)) * (np.exp(-(bet + an) * z2) - np.exp(-(an + bet) * z1))
    aj33 = (1.0 / (gam + an)) * (np.exp(-(gam + an) * z2) - np.exp(-(an + gam) * z1))
    aj3 = (-f0 * aj31 - f1 * aj32 - f2 * aj33) * p

    BBA_vis = aj1 / sol_vis
    BBA_nir = (aj2 + aj3) / sol_nir  # here segment 2.1 and 2.2 are summed
    BBA_sw = (aj1 + aj2 + aj3) / sol_sw

    return BBA_vis, BBA_nir, BBA_sw


@numba.jit(nopython=True, cache=True)
def analyt_func(z1, z2):
    # analystical integration of the solar flux
    # see BBA_calc_pol
    # compatible with array
    ak1 = (z2 ** 2 - z1 ** 2) / 2
    ak2 = (z2 / bet + 1 / bet ** 2) * np.exp(-bet * z2) - (
        z1 / bet + 1 / bet ** 2
    ) * np.exp(-bet * z1)
    ak3 = (z2 / gam + 1 / gam ** 2) * np.exp(-gam * z2) - (
        z1 / gam + 1 / gam ** 2
    ) * np.exp(-gam * z1)

    am1 = (z2 ** 3 - z1 ** 3) / 3
    am2 = (z2 ** 2 / bet + 2 * z2 / bet ** 2 + 2 / bet ** 3) * np.exp(-bet * z2) - (
        z1 ** 2 / bet + 2 * z1 / bet ** 2 + 2 / bet ** 3
    ) * np.exp(-bet * z1)
    am3 = (z2 ** 2 / gam + 2 * z2 / gam ** 2 + 2 / gam ** 3) * np.exp(-gam * z2) - (
        z1 ** 2 / gam + 2 * z1 / gam ** 2 + 2 / gam ** 3
    ) * np.exp(-gam * z1)

    return (f0 * ak1 - f1 * ak2 - f2 * ak3), (f0 * am1 - f1 * am2 - f2 * am3)


@numba.jit(nopython=True, cache=True)
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
    sa = a1 + b1 * x1 + c1 * x1 * x1
    return sa, a1, b1, c1


@numba.jit(nopython=True, cache=True)
def zbrent(x0, x1, args=(), max_iter=100, tolerance=1e-12):
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
    if (fx0 * fx1) > 0:
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

    while steps_taken < max_iter and abs(x1 - x0) > tolerance:
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

        if (
            (new < ((3 * x0 + x1) / 4) or new > x1)
            or (mflag == True and (abs(new - x1)) >= (abs(x1 - x2) / 2))
            or (mflag == False and (abs(new - x1)) >= (abs(x2 - d) / 2))
            or (mflag == True and (abs(x1 - x2)) < tolerance)
            or (mflag == False and (abs(x2 - d)) < tolerance)
        ):
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


def process(OLCI_scene, compute_polluted=True, no_qc=False, no_oz=False, **kwargs):
    angles = view_geometry(OLCI_scene)
    OLCI_scene, snow = prepare_processing(
        OLCI_scene, angles, compute_polluted=compute_polluted
    )
    OLCI_scene, angles, snow = snow_properties(OLCI_scene, angles, snow)
    if 'aot' not in OLCI_scene.keys():
        print('Using default AOT value')
        OLCI_scene['aot'] = OLCI_scene.sza*0 + 0.07
        OLCI_scene['aer_ang'] = OLCI_scene.sza*0 + 1.3
        
    aerosol = aerosol_properties(OLCI_scene.elevation, angles.cos_sa, OLCI_scene.aot, OLCI_scene.aer_ang)
    atmosphere = prepare_coef(aerosol, angles)

    # first guess for the snow spherical albedo
    OLCI_scene, snow = snow_albedo_solved(
        OLCI_scene, angles, aerosol, atmosphere, snow, compute_polluted=compute_polluted
    )

    # retrieving snow impurities
    if compute_polluted:
        impurities = snow_impurities(snow)
        for v in list(impurities.keys()):  # copy impurities data to snow
            snow[v] = impurities[v].drop_vars('band')

        snow = snow_albedo_direct(angles, aerosol, atmosphere, snow, impurities)

    snow = compute_BBA(OLCI_scene, snow, angles, compute_polluted=compute_polluted)

    if not no_oz:
        snow = ozone_retrieval(OLCI_scene, snow, angles)
    if not no_qc:
        snow = spectral_toa_modelling(OLCI_scene, snow, angles, atmosphere)
    return snow


def process_by_chunk(
    OLCI_scene,
    chunk_size=150000,
    compute_polluted=True,
    no_qc=False,
    no_oz=False,
):
    size = OLCI_scene.sza.shape[0]
    nchunks = int(max(np.floor(size / chunk_size), 1))
    OLCI_chunks = OLCI_scene.chunk({"band": 21, "xy": chunk_size})
    # snow_chunks = OLCI_chunks.map_blocks(process,kwargs={}, template = snow_template)
    xy_chunk_indexes = np.append(0, np.array(OLCI_chunks.chunks["xy"]).cumsum())

    snow = xr.Dataset()

    for i in range(len(xy_chunk_indexes) - 1):
        print(f"{i+1} / {nchunks+1}")
        # define chunk
        chunk = OLCI_scene.isel(xy=slice(xy_chunk_indexes[i], xy_chunk_indexes[i + 1]))

        if chunk.sza.notnull().sum() == 0:
            continue
        # process chunk
        snow_chunk = process(
            chunk, compute_polluted=compute_polluted, no_qc=no_qc, no_oz=no_oz
        )

        if len(snow) == 0:
            snow = snow_chunk.copy()
        else:
            snow = xr.concat([snow, snow_chunk], dim="xy")
        del snow_chunk

    return snow


def proc(inputfolder, demfolder, outputfolder = None, clean_snow = None, no_qc = None, no_oz = None):
    # debug:
    # InputPath = '../data/5_km_res/'
    # OutputFolder = '../data/5_km_res/pySICEv2.1_qc'
    # import argparse
    # args = argparse.ArgumentParser()
    # args.clean_snow = False
    # args.no_qc = False
    # args.no_oz = False
    
    

    #args = parse_args(sys.argv[1:])
    InputPath = get_input_folder(inputfolder)
    DemPath = get_dem_folder(demfolder)
    OutputFolder = get_output_folder(outputfolder)
    
    if not OutputFolder:
        OutputFolder = InputPath
    
    if clean_snow:
        print("Retrieving all pixels as clean snow")
        no_qc = True
        no_oz = True
    if no_qc:
        print("No quality check")
    if no_oz:
        print("No ozone retrieval")

    #print("Start pysice.py")
    #print("Input folder:", InputPath)
    #print("DEM folder:", DemPath)
    #print("Output folder:", OutputFolder)

    OLCI_reader = sice_io(InputPath,DemPath)
    OLCI_reader.open_tif()
    OLCI_scene = OLCI_reader.olci_scene
    OLCI_meta = OLCI_reader.meta
    start_time = time.process_time()

    if len(OLCI_scene.xy) < 1000000:
        snow = process(
            OLCI_scene,
            compute_polluted=not clean_snow,
            no_qc=no_qc,
            no_oz=no_oz,
        )
    else:
        snow = process_by_chunk(
            OLCI_scene,
            chunk_size=500000,
            compute_polluted=not clean_snow,
            no_qc=no_qc,
            no_oz=no_oz,
        )

    duration = time.process_time() - start_time
    print("Time elapsed: ", duration)
    try:
        snow.isnow[snow.albedo_bb_spherical_sw < 0.565] = 3
    except:
        pass 
    write_output(snow, OutputFolder, OLCI_reader.dirname,OLCI_meta['crs_out'],OLCI_meta['transform_out'])


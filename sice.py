# pySICEv1.6
#
# from FORTRAN VERSION 5.2
# March 31, 2020
#
# Latest update of python scripts: 29-04-2020 (bav@geus.dk)
# - Fixed a bug in the indexing of the polluted pixels for which the spherical albedo equation could not be solved.  Solved the oultiers visible in bands 12-15 and 19-20 and  expended the BBA calculation to few pixels that fell out of the index.
# - compression of output
# - new backscatter fraction from Alex
# - new format for tg_vod.dat file
#
# This code retrieves snow/ice  albedo and related snow products for clean Arctic
# atmosphere. The errors increase with the load of pollutants in air.
# Alexander  KOKHANOVSKY
# a.kokhanovsky@vitrocisetbelgium.com
# **************************************************
#
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
# Ozone retrieval:
# BXXX                      retrieved total ozone from OLCI measurements
# totadu                    ECMWF total column ozone in Dobson Unit
# toa                       ozone-corrected OLCI toa relfectances
#
# snow characteristics:
# isnow                     0 = clean snow, 1 = polluted snow
# ntype                     pollutant type: 1(soot), 2( dust), 3 and 4 (other or mixture)
# conc                      pollutant concentration is defined as the volumetric concentration
#                           of pollutants devided by the volumetric concentration of ice grains
# bf                        normalized absorption coefficient of pollutants ay 1000nm ( in inverse mm)
# bm                        Angstroem absorption coefficient of pollutants around 1 - for soot, 3-7 for dust)
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
#
# spherical BBA
# rs1                       visible(0.3-0.7micron)
# rs2                       near-infrared (0.7-2.4micron)
# rs3                       shortwave(0.3-2.4 micron)shortwave(0.3-2.4 micron)
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
# trapzd                    trapezoidal rule for integral calculation
# funp                      snow spectral planar and spherical albedo function

import numpy as np
import sys
try:
    import sice_lib as sl
    from sice_io import sice_io, write_output
except ImportError:
    # caution: path[0] is reserved for script path (or '' in REPL)
    sys.path.insert(1, './pysice')
    import sice_lib as sl
    from sice_io import sice_io, write_output
import time

np.seterr(invalid='ignore')

if __name__ == '__main__':
    # if the script is called from the command line, then parsing the input path and
    # passing it to the main function
    InputPath = sys.argv[1]
    if len(sys.argv) == 3:
        OutputFolder = sys.argv[2]
    else:
        OutputFolder = sys.argv[1] + '/'
    print(InputPath)
    print(OutputFolder)
    print('---')

    OLCI_reader = sice_io(InputPath)
    OLCI_reader.open()
    OLCI_scene = OLCI_reader.olci_scene

    start_time = time.process_time()

    if len(OLCI_scene.xy) < 1000000:
        snow = sl.process(OLCI_scene)
    else:
        snow = sl.process_by_chunk(OLCI_scene, chunk_size=500000)

    duration = time.process_time() - start_time
    print('Time elapsed: ', duration)

    write_output(snow, OutputFolder, OLCI_reader.dirname)

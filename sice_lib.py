# -*- coding: utf-8 -*-
"""
Created on Mon Oct 14 16:58:31 2019
Update 07032019

 pySICEv1.1 library
 contains:
     pySICE                     main function
     alb2rtoa                  calculates TOA reflectance from surface albedo
     salbed                    calculates ratm for albedo correction (?)
     zbrent                    equation solver
     quad_func                 calculation of quadratic parameters
     funp                      snow spectral planar and spherical albedo function

 requires:
     constants.py               contains constants needed to run the functions below

@author: bav@geus.dk
"""
import numpy as np
from constants import w, bai, xa, ya, f0, f1, f2, bet, gam, coef1, coef2, coef3, coef4

#%% Main function
def pySICE(toa,am1, am2, raa, ak1, ak2, amf, tau, co, p, g,
           D, area, al, r0, bal,
           sol1_clean, sol1_pol, sol2, sol3_clean, sol3_pol, asol):
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
# This code retrieves snow/ice  albedo and related snow products for clean Arctic
# atmosphere. The errors increase with the load of pollutants in air.
# Alexander  KOKHANOVSKY
# a.kokhanovsky@vitrocisetbelgium.com
# Translated to python by Baptiste Vandecrux (bav@geus.dk)

# **************************************************
# Inputs:
# toa_cor_o3[i_channel]            spectral OLCI TOA reflectance at 21 channels (R=pi*I_reflec/cos(SZA)/E_0)
#
# Outputs: 
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
# funp                      snow spectral planar and spherical albedo function

    # allocating ouput variables
    alb_sph = np.array(w)*0+999
    rp      = alb_sph
    refl    = alb_sph
    
    isnow, conc, ntype, rp1, rp2, rp3, rs1, rs2, rs3 = \
    0, 0, 0, 0, 0, 0, 0, 0, 0

 # STEP 3
# checking for type of snow: clean or polluted
# for that we calculate the theoretical reflectance at channel 1 of a surface with:
# r0 = 1, a = 1, ak1 = 1, ak2 = 1
    i_channel = 0
    thv = alb2rtoa(1, tau[i_channel], 
             g[i_channel], p[i_channel], amf, am1, am2, 1, 1, 1) 

    alpha = 4.*np.pi*bai/w   

    # STEP 4a: clean snow retrieval
    isnow[toa[0]>=thv] = 0
    
    # we then compare it to the observed toa[0] value
    if (toa[0]>=thv):
                    
        # the spherical albedo derivation: alb_sph
        absor=1000.*alpha*al
        alb_sph[absor> 1.e-6] =np.exp(-np.sqrt(absor[absor> 1.e-6]))
        alb_sph[absor <=  1.e-6]=1.0
                                                  
    else:
            # STEP 4b
            # 2. polluted snow retrieval                      
            # it is assumed that albedo is in the range 0.1-1.0
            x1=0.1
    # BAV 09-02-2020: 1.2 to 1.0
            x2=1.0
                
            # could be parallelized
            for i_channel in range(21):
                if (i_channel != 18) and (i_channel != 19):
                    # the solution of transcendent equation to find spherical albedo: alb_sph
                    # solving rtoa[i_channel] - alb2rtoa(aledo) = 0
                    def func_solv(albedo):
                        return toa[i_channel] - alb2rtoa(albedo, tau[i_channel], 
                 g[i_channel], p[i_channel], amf, am1, am2, r0, ak1, ak2)
                        
                    alb_sph[i_channel] = zbrent(func_solv,x1,x2,100,1.e-6)
                    if (alb_sph[i_channel]==1):
                        isnow= 5
                else:
                    alb_sph[i_channel] = 0.001
                    
            # end loop channels
                                  
            # INTERNal CHECK FOR CLEAN np.piXELS
            # if (alb_sph[0]>0.98): #go to 9393 = use clean pixel retrieval
            # if (alb_sph[1]>0.98): #go to 9393 = use clean pixel retrieval
            if (alb_sph[0]>0.98):
                isnow= 7
            
            if (alb_sph[1]>0.98): 
                isnow= 7
                
            # analysis of snow impurities
            # ( the concentrations below 0.0001 are not reliable )        
            # bf    normalized absorption coefficient of pollutants ay 1000nm ( in inverse mm)
            # bm    Angstroem absorption coefficient of pollutants ( around 1 - for soot, 3-7 for dust)
            bm=0.0
            bf=0.0
                     
            p1=np.log(alb_sph[0])*np.log(alb_sph[0])
            p2=np.log(alb_sph[1])*np.log(alb_sph[1])
            bm=np.log( p1/p2)/np.log(w[1]/w[0])

            # type of pollutants
            ntype=0
            if (bm <= 1.2):   ntype=1   # soot
            if (bm>1.2):     ntype=2    # dust
    
            if (bm>=0.1):
                soda=(w[0])**bm
                bf=soda*p1/bal
                         
            # normalized absorption coefficient of pollutants at the wavelength  1000nm
            bff=p1/bal
            # bal   -effective absorption length in microns
           
            BBBB=1.6        # enhancement factors for soot
            FFFF= 0.9       # enhancement factors for ice grains
            alfa=4.*np.pi*0.47/w[0]  # bulk soot absorption coefficient at 1000nm
            DUST=0.01       # volumetric absorption coefficient of dust
                           
            if (ntype == 1): conc = BBBB*bff/FFFF/alfa
            if (ntype == 2): conc = BBBB*bff/DUST
            if (bm <= 0.5):    ntype=3 # type is other or mixture
            if (bm >= 10.):    ntype=4 # type is other or mixture
    
            # alex   09.06.2019
            # reprocessing of albedo to remove gaseous absorption
            # using linear polynomial approximation in the range 753-778nm
            # Meaning:
            # alb_sph[12],alb_sph[13] and alb_sph[14] are replaced by a linear 
            # interpolation between alb_sph[11] and alb_sph[15]
                 
            x1=w[11]
            x2=w[15]
                 
            y1=alb_sph[11]
            y2=alb_sph[15]
                  
            afirn=(y2-y1)/(x2-x1)
            bfirn=y2-afirn*x2
            
            alb_sph[range(12,15)] = bfirn + afirn*w[range(12,15)]
            
            # BAV 09-02-2020: 0.5 to 0.35
            if (toa[20]>=0.35):
                alb_sph[range(17,21)] = np.exp(-np.sqrt(4.*1000. \
                        *al * np.pi * bai[range(17,21)] / w[range(17,21)] ))
            else:
                # ***********CORRECTION FOR VERSION 2.2*********************
                # Alex, SEPTEMBER 26, 2019
                # to avoid the influence of gaseous absorption (water vapor)
                # we linearly interpolate in the range 885-1020nm
                # for bare ice cases only (low toa[20])
                # Meaning:
                # alb_sph[18] and alb_sph[19] are replaced by a linear 
                # interpolation between alb_sph[17] and alb_sph[20]
                delx=w[20]-w[17]
                bcoef=(alb_sph[20]-alb_sph[17])/delx
                acoef=alb_sph[20]-bcoef*w[20]
                
                alb_sph[range(18,20)] = acoef+bcoef*w[range(18,20)]
#                 ***********************END of MODIFICATION**************                   

#    # derivation of plane albedo                  
#    rp=alb_sph**ak1
#              
#    # derivation of snow reflectance function                      
#    refl=r0*alb_sph**(ak1*ak2/r0)
                
#%% =================================================
def prepare_coef(tau, g, p, am1, am2, amf):
    astra=tau*np.nan
    rms=tau*np.nan
    t1=tau*np.nan
    t2=tau*np.nan
    
    # SOBOLEV
    oskar=4.+3.*(1.-g)*tau
    b1=1.+1.5*am1+(1.-1.5*am1)*np.exp(-tau/am1)
    b2=1.+1.5*am2+(1.-1.5*am2)*np.exp(-tau/am2)
    
    for i in range(21):
        astra[i,:,:]=(1.-np.exp(-tau[i,:,:]*amf))/(am1+am2)/4.
        rms[i,:,:] = 1.- b1[i,:,:]*b2[i,:,:]/oskar[i,:,:]  \
        + (3.*(1.+g[i,:,:])*am1*am2 - 2.*(am1+am2))*astra[i,:,:]
        t1[i,:,:] = np.exp(-(1.-g[i,:,:])*tau[i,:,:]/am1/2.)
        t2[i,:,:] = np.exp(-(1.-g[i,:,:])*tau[i,:,:]/am2/2.)

    rss = p*astra
    r = rss + rms
    
    # SALBED
#    ratm = salbed(tau, g)
    a_s = (.18016,  -0.18229,  0.15535,     -0.14223)
    bs = (.58331,  -0.50662,  -0.09012,        0.0207)
    cs = (0.21475,   -0.1,  0.13639,            -0.21948)
    als = (0.16775, -0.06969,  0.08093,     -0.08903)
    bets = (1.09188,  0.08994,  0.49647,   -0.75218)
    
    a_cst =     a_s[0]*g**0  + a_s[1]*g**1 + a_s[2]*g**2 + a_s[3]*g**3
    b_cst =     bs[0]*g**0   + bs[1]*g**1 + bs[2]*g**2 + bs[3]*g**3
    c_cst =     cs[0]*g**0   + cs[1]*g**1 + cs[2]*g**2 + cs[3]*g**3
    al_cst=     als[0]*g**0  + als[1]*g**1 + als[2]*g**2 + als[3]*g**3
    bet_cst=    bets[0]*g**0 + bets[1]*g**1 + bets[2]*g**2 + bets[3]*g**3        
   
    ratm = tau*(a_cst*np.exp(-tau/al_cst)+b_cst*np.exp(-tau/bet_cst)+c_cst)
    return t1, t2, ratm, r, astra, rms
#%% ===========================================================================
def alb2rtoa_old(a, tau, g, p, amf, am1, am2, r0, ak1, ak2):
# Function that calculates the theoretical reflectance from a snow spherical albedo a
# This function can then be solved to find optimal snow albedo
# Inputs:
# a                     Surface albedo
# r0                    reflectance of a semi-infinite non-absorbing snow layer 
#
# Outputs:
# rs                  surface reflectance at specific channel 
        
    # SOBOLEV
    astra=(1.-np.exp(-tau*amf))/(am1+am2)/4.
    oskar=4.+3.*(1.-g)*tau
                       
    b1=1.+1.5*am1+(1.-1.5*am1)*np.exp(-tau/am1)
    b2=1.+1.5*am2+(1.-1.5*am2)*np.exp(-tau/am2)
                       
    rss = p*astra
    rms = 1.-b1*b2/oskar+(3.*(1.+g)*am1*am2-2.*(am1+am2))*astra
    r = rss + rms
               
    t1=np.exp(-(1.-g)*tau/am1/2.)
    t2=np.exp(-(1.-g)*tau/am2/2.)
    
    ratm = salbed_old(tau, g)
    surf = t1*t2*r0*a**(ak1*ak2/r0)/(1-a*ratm)
    rs=r + surf
    return rs,  astra, rms

#%% ===========================================================================
def salbed_old(tau, g):
    # SPHERICAL ALBEDO OF TERRESTRIAL ATMOSPHERE:      
    # bav: replaced as by a_s
    # inputs:
    # tau               directional albedo ?
    # g                 asymetry coefficient
    # outputs:
    # salbed            spherical albedo
    a_s = (.18016,  -0.18229,  0.15535,     -0.14223)
    bs = (.58331,  -0.50662,  -0.09012,        0.0207)
    cs = (0.21475,   -0.1,  0.13639,            -0.21948)
    als = (0.16775, -0.06969,  0.08093,     -0.08903)
    bets = (1.09188,  0.08994,  0.49647,   -0.75218)

    a=0.
    b=0.
    c=0.
    al=0.
    bet=0.
            
    for i in range(0,4):
        if (i==0): aks=1
        else: aks=g**i
        a=a  + a_s[i]*aks
        b=b  + bs[i]*aks
        c= c +cs[i]*aks
        al=al +als[i]*aks
        bet=bet +bets[i]*aks
    
    salbed = tau*(a*np.exp(-tau/al)+b*np.exp(-tau/bet)+c)
    return salbed
    
#%% ===========================================================================
def alb2rtoa(a, t1, t2, r0, ak1, ak2, ratm, r):
# Function that calculates the theoretical reflectance from a snow spherical albedo a
# This function can then be solved to find optimal snow albedo
# Inputs:
# a                     Surface albedo
# r0                    reflectance of a semi-infinite non-absorbing snow layer 
#
# Outputs:
# rs                  surface reflectance at specific channel     
    surf = t1*t2*r0*a**(ak1*ak2/r0)/(1-a*ratm)
    rs=r + surf
    return rs

#%% ===========================================================================
def salbed(tau, g):
    # WARNING: NOT USED ANYMORE
    # SPHERICAL ALBEDO OF TERRESTRIAL ATMOSPHERE:      
    # bav: replaced as by a_s
    # inputs:
    # tau               directional albedo ?
    # g                 asymetry coefficient
    # outputs:
    # salbed            spherical albedo
    a_s = (.18016,  -0.18229,  0.15535,     -0.14223)
    bs = (.58331,  -0.50662,  -0.09012,        0.0207)
    cs = (0.21475,   -0.1,  0.13639,            -0.21948)
    als = (0.16775, -0.06969,  0.08093,     -0.08903)
    bets = (1.09188,  0.08994,  0.49647,   -0.75218)

#    a=0.
#    b=0.
#    c=0.
#    al=0.
#    bet=0.
#            
#    for i in range(0,4):
#        if (i==0): aks=1
#        else: aks=g**i
#        a=a  + a_s[i]*aks
#        b=b  + bs[i]*aks
#        c= c +cs[i]*aks
#        al=al +als[i]*aks
#        bet=bet +bets[i]*aks
#    salbed = tau*(a*np.exp(-tau/al)+b*np.exp(-tau/bet)+c)
#    return salbed
    

    a =     a_s[0]*g**0  + a_s[1]*g**1 + a_s[2]*g**2 + a_s[3]*g**3
    b =     bs[0]*g**0   + bs[1]*g**1 + bs[2]*g**2 + bs[3]*g**3
    c =     cs[0]*g**0   + cs[1]*g**1 + cs[2]*g**2 + cs[3]*g**3
    al=     als[0]*g**0  + als[1]*g**1 + als[2]*g**2 + als[3]*g**3
    bet=    bets[0]*g**0 + bets[1]*g**1 + bets[2]*g**2 + bets[3]*g**3        
   
    salbed = tau*(a*np.exp(-tau/al)+b*np.exp(-tau/bet)+c)
    return salbed


#%% =====================================================================
def zbrent(f, x0, x1, max_iter=100, tolerance=1e-6):
    # Equation solver using Brent's method
    # https://en.wikipedia.org/wiki/Brent%27s_method
    # Brent’s is essentially the Bisection method augmented with Inverse 
    # Quadratic Interpolation whenever such a step is safe. At it’s worst case 
    #it converges linearly and equal to Bisection, but in general it performs 
    # superlinearly; it combines the robustness of Bisection with the speedy
    # convergence and inexpensive computation of Quasi-Newtonian methods. 
    # Because of this, you’re likely to find Brent’s as a default root-finding 
    # algorithm in popular libraries. For example, MATLAB’s fzero, used to find 
    # the root of a nonlinear function, employs a variation of Brent’s.
    # Python script from https://nickcdryan.com/2017/09/13/root-finding-algorithms-in-python-line-search-bisection-secant-newton-raphson-boydens-inverse-quadratic-interpolation-brents/
 
    fx0 = f(x0)
    fx1 = f(x1)
 
#    print(str(fx0) + ", " + str(fx1))
    if ((fx0 * fx1) > 0):
#        print("Root not bracketed "+str(fx0)+", "+str(fx1))
#        assert ((fx0 * fx1) <= 0), ("-----Root not bracketed"+str(fx0)+", "+str(fx1))
        return -999
 
    if abs(fx0) < abs(fx1):
        x0, x1 = x1, x0
        fx0, fx1 = fx1, fx0
 
    x2, fx2 = x0, fx0
 
    mflag = True
    steps_taken = 0
 
    while steps_taken < max_iter and abs(x1-x0) > tolerance:
        fx0 = f(x0)
        fx1 = f(x1)
        fx2 = f(x2)
 
        if fx0 != fx2 and fx1 != fx2:
            L0 = (x0 * fx1 * fx2) / ((fx0 - fx1) * (fx0 - fx2))
            L1 = (x1 * fx0 * fx2) / ((fx1 - fx0) * (fx1 - fx2))
            L2 = (x2 * fx1 * fx0) / ((fx2 - fx0) * (fx2 - fx1))
            new = L0 + L1 + L2
 
        else:
            new = x1 - ( (fx1 * (x1 - x0)) / (fx1 - fx0) )
 
        if ((new < ((3 * x0 + x1) / 4) or new > x1) or
            (mflag == True and (abs(new - x1)) >= (abs(x1 - x2) / 2)) or
            (mflag == False and (abs(new - x1)) >= (abs(x2 - d) / 2)) or
            (mflag == True and (abs(x1 - x2)) < tolerance) or
            (mflag == False and (abs(x2 - d)) < tolerance)):
            new = (x0 + x1) / 2
            mflag = True
 
        else:
            mflag = False
 
        fnew = f(new)
        d, x2 = x2, x1
 
        if (fx0 * fnew) < 0:
            x1 = new
        else:
            x0 = new
 
        if abs(fx0) < abs(fx1):
            x0, x1 = x1, x0
 
        steps_taken += 1
 
    return x1


#%% ================================================
# tozon [i_channel]         spectral ozone vertical optical depth at the fixed ozone concentration 404.59DU ( wavelength, VOD)
# voda[i_channel]           spectral water vapour vertical optical depth at the fixed concentration 3.847e+22 molecules per square sm

# Outputs: 
# Ozone retrieval:
# BXXX                      retrieved total ozone from OLCI measurements
# totadu                    ECMWF total column ozone in Dobson Unit
# toa_cor_03                       ozone-corrected OLCI toa relfectances
    
def ozone_scattering(ozon,tozon,sza,vza,toa):
    scale = np.arccos(-1.)/180. # rad per degree
    eps = 1.55
    # ecmwf ozone from OLCI file (in Kg.m-2) to DOBSON UNITS 
    # 1 kg O3 / m2 = 46696.24  DOBSON Unit (DU)
    totadu = 46729.*ozon
                 
    amf = 1./np.cos(sza*scale)+1./np.cos(vza*scale)
          
    BX=(toa[20]**(1.-eps))  * (toa[16]**eps) / toa[6]
    BXXX=np.log(BX)/1.11e-4/amf
    BXXX[BXXX>500] = 999
    BXXX[BXXX<0] = 999
    
    # Correcting TOA reflectance for ozone and water scattering
    
                # bav 09-02-2020: now water scattering not accounted for
                # kg/m**2. transfer to mol/cm**2         
            #    roznov = 2.99236e-22  # 1 moles Ozone = 47.9982 grams  
                # water vapor optical depth      
            #    vap = water/roznov
            #    AKOWAT = vap/3.847e+22#    tvoda = np.exp(amf*voda*AKOWAT)
    tvoda=tozon*0+1
    toa_cor_o3=toa*np.nan;
    for i in range(21):
        toa_cor_o3[i,:,:] = toa[i,:,:]*tvoda[i]*np.exp(amf*tozon[i]*totadu/404.59)
    
    return BXXX, toa_cor_o3

#%% viewing characteristics and aerosol properties
# sza                       solar zenith angle
# vza                       viewing zenith angle
# saa                       solar azimuthal angle
# vaa                       viewing azimuthal angle
# raa                   Relative azimuth angle
# aot                       threshold value on aerosol optical thickness (aot) at 500nm
# height                    height of underlying surface(meters)

def view_geometry(vaa, saa, sza, vza, aot, height):
    # transfer of OLCI relative azimuthal angle to the definition used in
    # radiative transfer code  
    raa=180.-(vaa-saa)                  
    as1=np.sin(sza*np.pi/180.)
    as2=np.sin(vza*np.pi/180.)
    
    am1=np.cos(sza*np.pi/180.)
    am2=np.cos(vza*np.pi/180.)
                        
    ak1=3.*(1.+2.*am1)/7.
    ak2=3.*(1.+2.*am2)/7.
    
    cofi=np.cos(raa*np.pi/180.)
    amf=1./am1+1./am2
    co=-am1*am2+as1*as2*cofi
    return raa, am1, am2, ak1, ak2, amf, co
    
def aerosol_properties(aot, height, co):
    # Atmospheric optical thickness
    tauaer =aot*(w/0.5)**(-1.3)

    ad =height/7400.
    ak = height*0+1
    ak[ad > 1.e-6]=np.exp(-ad[ad > 1.e-6])
    
    taumol = np.tile(height*np.nan, (21,1,1))
    tau = np.tile(height*np.nan, (21,1,1))
    g = np.tile(height*np.nan, (21,1,1))
    pa = np.tile(height*np.nan, (21,1,1))
    p = np.tile(height*np.nan, (21,1,1))

    for i in range(21):
        taumol[i,:,:] = ak*0.00877/w[i]**(4.05)
        tau[i,:,:] = tauaer[i] + taumol[i,:,:]
    
        # snow asymmetry parameter
        g0=0.5263
        g1=0.4627
        wave0=0.4685
        gaer=g0+g1*np.exp(-w/wave0)
        g[i,:,:]=tauaer[i]*gaer[i]/tau[i,:,:]
        
        # HG phase function for aerosol
        pa[i,:,:]=(1-g[i,:,:]**2)/(1.-2.*g[i,:,:]*co+g[i,:,:]**2)**1.5
        pr=0.75*(1.+co**2)
        p[i,:,:]=(taumol[i,:,:]*pr + tauaer[i]*pa[i,:,:])/tau[i,:,:]
    
    return tau, p, g

#%% snow properties
def snow_properties(toa, ak1, ak2):
        # retrieval of snow properties ( R_0, size of grains from OLCI channels 865[17] and 1020nm[21]
    # assumed not influenced by atmospheric scattering and absorption processes)                       
    
    akap2=2.25e-6                    
    alpha2=4.*np.pi*akap2/1.020                        
    eps = 1.549559365010611
    
    # reflectivity of nonabsorbing snow layer 
    rr1=toa[16,:,:]   
    rr2=toa[20,:,:]
    r0 = (rr1**eps)*(rr2**(1.-eps))
                           
    # effective absorption length(mm)
    bal = np.log(rr2/r0) * np.log(rr2/r0)/alpha2/(ak1*ak2/r0)**2
    al = bal/1000.
    
    # effective grain size(mm):diameter
    D=al/16.36              
    # snow specific area ( dimension: m*m/kg)
    area=   6./D/0.917
    return  D, area, al, r0, bal

#%% snow_imputirities
def snow_impurities(alb_sph, bal):
        # analysis of snow impurities
    # ( the concentrations below 0.0001 are not reliable )        
    # bf    normalized absorption coefficient of pollutants ay 1000nm ( in inverse mm)
    # bm    Angstroem absorption coefficient of pollutants ( around 1 - for soot, 3-7 for dust)
    bm=np.nan*bal
    bf=bm
             
    p1=np.log(alb_sph[0,:,:])*np.log(alb_sph[0,:,:])
    p2=np.log(alb_sph[1,:,:])*np.log(alb_sph[1,:,:])
    bm=np.log( p1/p2)/np.log(w[1]/w[0])

    # type of pollutants
    ntype=np.nan*bal
    ntype[bm <= 1.2]=1   # soot
    ntype[bm > 1.2]=2    # dust

    soda = bm*np.nan
    soda[bm>=0.1]=(w[0])**bm[bm>=0.1]
    bf=soda*p1/bal
                 
    # normalized absorption coefficient of pollutants at the wavelength  1000nm
    bff=p1/bal
    # bal   -effective absorption length in microns
   
    BBBB=1.6        # enhancement factors for soot
    FFFF= 0.9       # enhancement factors for ice grains
    alfa=4.*np.pi*0.47/w[0]  # bulk soot absorption coefficient at 1000nm
    DUST=0.01       # volumetric absorption coefficient of dust

    conc = bal*np.nan
    conc[ntype == 1] = BBBB*bff[ntype == 1]/FFFF/alfa
    conc[ntype == 2] = BBBB*bff[ntype == 2]/DUST
    ntype[bm <= 0.5] = 3 # type is other or mixture
    ntype[bm >= 10.] = 4 # type is other or mixture
    return ntype, bf, conc

#%% =====================================================================     
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

    y = np.interp(x,xa,ya)

    dega = 1000.* al * 4.*np.pi*y/x
    pow = np.sqrt(dega)
         
    if (pow >= 1.e-6): rsd = np.exp(-pow)
    else: rsd=1.
         
    if (sph_calc == 0):     rs = rsd**ak1
    elif (sph_calc == 1):   rs = rsd

    if (x < 0.4):  
        x = 0.4
    funcs = f0+ f1*np.exp(-x*bet)+ f2*np.exp(-x*gam)
     
    return rs*funcs

#%%   CalCULATION OF BBA for clean pixels
def BBA_calc_clean(al, ak1):
    # for clean snow
    # plane albedo
    sph_calc = 0 # planar
    # visible(0.3-0.7micron)
    def func_integ(x):
        return funp(x, al, sph_calc, ak1)
    
    p1 = qsimp(func_integ,0.3,0.7)
    
    # near-infrared (0.7-2.4micron)
#        p2 = trapzd(func_integ,0.7,2.4, 20)
    p2 = qsimp(func_integ,0.7,2.4)
     
    # spherical albedo
    sph_calc = 1 # spherical calculation
    
    def func_integ(x):
        return funp(x, al, sph_calc, ak1)
    
    # visible(0.3-0.7micron)
#        s1 = trapzd(func_integ,0.3,0.7, 20)
    s1 = qsimp(func_integ,0.3,0.7)
    # near-infrared (0.7-2.4micron)
#        s2 = trapzd(func_integ,0.7,2.4, 20)
    s2 = qsimp(func_integ,0.7,2.4)
    # shortwave(0.3-2.4 micron)
    # END of clean snow bba calculation
    return p1,p2,s1,s2

#%% ===============================
def qsimp(func,a,b):
    # integrate function between a and b using simpson's method. 
    # works as fast as scipy.integrate quad
    eps=1.e-3
    jmax=20
    ost=-1.e30
    os= -1.e30
    for j in range(jmax):
        if (j==0):
            st=0.5*(b-a)*(func(a)+func(b))
        else:
            it=2**(j-1)
            tnm=it
            delta=(b-a)/tnm
            x=a+0.5*delta
            sum=0.
            for jj in range(it):
                sum=sum+func(x)
                x=x+delta
            st=0.5*(st+(b-a)*sum/tnm)
        s=(4.*st-ost)/3.
        if (j>4):
            if (abs(s-os)<eps*abs(os)):
                return s
            if (s==0) and (os==0.):
                return s
        os=s
        ost=st
    print("Max iteration reached")
    return s

#%% Calculation f BBA for polluted snow

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
    
    alam2=0.4
    alam3=0.56
    alam5=0.709
    alam6=0.753
    alam7=0.865
    alam8=1.02
  
    #input reflectances
    r2 =alb[0,:]
    r3 =alb[5,:]
    r5 =alb[10,:]
    r6=alb[11,:]
    r7=alb[16,:]
    r8=alb[20,:]
    
    sa1, a1, b1, c1 = quad_func(alam2,alam3,alam5, r2 ,r3,r5)
    ajx1 = a1*sol1_pol
    ajx2 = b1*coef1
    ajx3 = c1*coef2

    aj1 = ajx1 + ajx2 + ajx3
    # segment 2.1
    # QUADRATIC POLYNOMIal for the range 709-865nm        
    sa1, a2, b2, c2 = quad_func(alam5,alam6,alam7,r5,r6,r7)
    ajx1 = a2*asol
    ajx2 = b2*coef3
    ajx3 = c2*coef4

    aj2 = ajx1 + ajx2 + ajx3    # segment 2.2
    # exponential approximation for the range 865- 2400 nm
    z1=0.865
    z2=2.4
    rati=r7/r8
    alasta = (alam8-alam7)/np.log(rati)
    an=1./alasta
    p   = r7 * np.exp(alam7/alasta)
    
    aj31=(1./an)*(np.exp(-an*z2)-np.exp(-an*z1))
    aj32=(1./(bet+an))*(np.exp(-(bet+an)*z2)-np.exp(-(an+bet)*z1))
    aj33=(1./(gam+an))*(np.exp(-(gam+an)*z2)-np.exp(-(an+gam)*z1))
    aj3=(-f0*aj31-f1*aj32-f2*aj33)*p
    
    BBA_vis = aj1/sol1_pol
    BBA_nir = (aj2+aj3)/sol2 #here segment 2.1 and 2.2 are summed
    BBA_sw   = (aj1+aj2+aj3)/sol3_pol 

    return BBA_vis,BBA_nir, BBA_sw

#%% ==========================================================================
def quad_func(x0,x1,x2,y0,y1,y2):
    # quadratic function used for the polluted snow BBA calculation
    # see BBA_calc_pol
    # compatible with arrays
    d1=(x0-x1)*(x0-x2)
    d2=(x1-x0)*(x1-x2)
    d3=(x2-x0)*(x2-x1)
    
    a1=x1*x2*y0/d1+x0*x2*y1/d2+x0*x1*y2/d3
    b1=-(x1+x2)*y0/d1-(x0+x2)*y1/d2-(x0+x1)*y2/d3
    c1=y0/d1+y1/d2+y2/d3
    x=x1
    sa=a1+b1*x+c1*x*x
    return sa, a1, b1, c1

# -*- coding: utf-8 -*-
"""
Created on Mon Oct 14 16:58:31 2019
 pySICE library
 contains:
     pySICE                     main function
     alb2rtoa                  calculates TOA reflectance from surface albedo
     salbed                    calculates ratm for albedo correction (?)
     zbrent                    equation solver
     sol                       solar spectrum
     analyt_func               calculation of surface radiance
     quad_func                 calculation of quadratic parameters
     funp                      snow spectral planar and spherical albedo function

 requires:
     constants.py               contains constants needed to run the functions below

@author: bav@geus.dk
"""
import numpy as np
from constants import w, bai, xa, ya,f0,f1,f2,bet,gam

#%% Main function
def pySICE(sza,vza,saa,vaa,height,toa,ozon,water,voda,tozon,aot):
# pySICE
# 
# VERSION 2.3
# 10-10-2019 
   
# This code retrieves snow/ice  albedo and related snow products for clean Arctic
# atmosphere. The errors increase with the load of pollutants in air.
# Alexander  KOKHANOVSKY
# a.kokhanovsky@vitrocisetbelgium.com
# Translated to python by Baptiste Vandecrux (bav@geus.dk)

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
# funp                      snow spectral planar and spherical albedo function

    # allocating ouput variables
    alb_sph = np.array(w)*0+999
    rp      = alb_sph
    refl    = alb_sph
    
    BXXX, isnow, D, area, al, r0, isnow, conc, ntype, rp1, rp2, rp3, rs1, rs2, rs3 = \
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    
    scale = np.arccos(-1.)/180. # rad per degree
    eps = 1.55
    # ecmwf ozone from OLCI file (in Kg.m-2) to DOBSON UNITS 
    # 1 kg O3 / m2 = 46696.24  DOBSON Unit (DU)
    totadu = 46729.*ozon
    
    # kg/m**2. transfer to mol/cm**2         
    roznov = 2.99236e-22  # 1 moles Ozone = 47.9982 grams  
    # water vapor optical depth      
    vap = water/roznov
    AKOWAT = vap/3.847e+22
              
    amf = 1./np.cos(sza*scale)+1./np.cos(vza*scale)
          
    BX=(toa[20]**(1.-eps))  * (toa[16]**eps) / toa[6]
    BXXX=np.log(BX)/1.11e-4/amf
    if (BXXX>500.): BXXX=999.
    if (BXXX<0): BXXX=999.
    
    # Correcting TOA reflectance for ozone and water scattering
    tvoda = np.exp(amf*voda*AKOWAT)
    toa = toa*tvoda*np.exp(amf*tozon*totadu/404.59)

    #        toa[i_channel] = toa[i_channel]*np.exp(amf*tozon[i_channel]*totadu/404.59)
             
    # bav 2019:
    #   here was filtered dark ice pixels. Now this should be dealt with outside python upstream.
    
    # transfer of OLCI relative azimuthal angle to the definition used in
    # radiative transfer code  
    raa=180.-(vaa-saa)                  
    pi=np.arccos(-1.)
    as1=np.sin(sza*pi/180.)
    as2=np.sin(vza*pi/180.)
    
    am1=np.cos(sza*pi/180.)
    am2=np.cos(vza*pi/180.)
                        
    ak1=3.*(1.+2.*am1)/7.
    ak2=3.*(1.+2.*am2)/7.
    
    cofi=np.cos(raa*pi/180.)
    amf=1./am1+1./am2
    co=-am1*am2+as1*as2*cofi
    # theta=np.arccos(co)*180./pi
    
    # Atmospheric optical thickness
    # ALEX 09.06.2019                    
    tauaer =aot*(w/0.5)**(-1.3)

    ad =height/7400.
    ak =1.
    if (ad > 1.e-6): ak=np.exp(-ad)
    taumol=ak*0.00877/w**(4.05)
    tau = tauaer + taumol
    
    # snow asymmetry parameter
    g0=0.5263
    g1=0.4627
    wave0=0.4685                       
    gaer=g0+g1*np.exp(-w/wave0)
    g=tauaer*gaer/tau
    
    # HG phase function for aerosol
    pa=(1-g*g)/(1.-2.*g*co+g*g)**1.5
    pr=0.75*(1.+co*co)
    p=(taumol*pr + tauaer*pa)/tau
        
    # STEP 1
    # calculation of NDSI, NDBI and flags
    # bav 2019:  Now done outside the python script
    
    # STEP 2                         
    # retrieval of snow properties ( R_0, size of grains from OLCI channels 865[17] and 1020nm[21]
    # assumed not influenced by atmospheric scattering and absorption processes)                       
    
    #akap1=2.40e-7
    akap2=2.25e-6                    
    #alpha1=4.*pi*akap1/0.865
    alpha2=4.*pi*akap2/1.020                        
    #b = np.sqrt(alpha1/alpha2)
    #eps=1./(1.-b)
    eps = 1.549559365010611
    
    # reflectivity of nonabsorbing snow layer 
    rr1=toa[16]   
    rr2=toa[20]
#    arr1=toa[0]
                          
    r0 = (rr1**eps)*(rr2**(1.-eps))
                           
    # effective absorption length(mm)
    bal = np.log(rr2/r0) * np.log(rr2/r0)/alpha2/(ak1*ak2/r0)**2
    al = bal/1000.
    
    # effective grain size(mm):diameter
    D=al/16.36
    
    if (D <= 0.1):
        isnow = 3
#       return BXXX, isnow, D, area, al, r0, isnow, conc, ntype,alb_sph, rp,refl, rp1, rp2, rp3, rs1, rs2, rs3
        return BXXX,  D, area, al, r0, isnow, conc, ntype,alb_sph, rp,refl, rp1, rp2, rp3, rs1, rs2, rs3
                        
    # here were removed unlikely grain diameters
              
    # snow specific area ( dimension: m*m/kg)
    area=   6./D/0.917
    
    # STEP 3
    # checking for type of snow: clean or polluted
    # for that we calculate the theoretical reflectance at channel 1 of a surface with:
    # r0 = 1, a = 1, ak1 = 1, ak2 = 1
    i_channel = 0
    thv = alb2rtoa(1, tau[i_channel], 
             g[i_channel], p[i_channel], amf, am1, am2, 1, 1, 1) 


    # we then compare it to the observed toa[0] value
    if (toa[0]>=thv):
        isnow=0           
        # STEP 4a: clean snow retrieval
        alpha = 4.*pi*bai/w   
                     
        # the spherical albedo derivation: alb_sph
        absor=1000.*alpha*al
        alb_sph[absor> 1.e-6] =np.exp(-np.sqrt(absor[absor> 1.e-6]))
        alb_sph[absor <=  1.e-6]=1.0
                                                  
    else:
            # STEP 4b
            # 2. polluted snow retrieval                      
            # it is assumed that albedo is in the range 0.1-1.0
            isnow=1           
            x1=0.1
            x2=1.2
    
            if (toa[20]<0.5):
                # alex AUGUST 7, 2019
                az=1.247
                bz=1.186
                cz=5.157
                
                am11=np.sqrt(1.-am1**2.)
                am12=np.sqrt(1.-am2**2.)
                
                tz=np.arccos(-am1*am2+am11*am12*np.cos( raa*np.pi/180.))*180./np.pi
                pz=11.1*np.exp(-0.087*tz)+1.1*np.exp(-0.014*tz)
                rclean=az+bz*(am1+am2)+cz*am1*am2+pz
                rclean=rclean/4./(am1+am2)
                
#                step=rclean/ak1/ak2
                # END OF CHANGE: AUGUST 7, 2019
                r0=rclean
                isnow = 6
            # could be parallelized
            for i_channel in range(21):
                # the solution of transcendent equation to find spherical albedo: alb_sph
                # solving rtoa[i_channel] - alb2rtoa(aledo) = 0
                def func_solv(albedo):
                    return toa[i_channel] - alb2rtoa(albedo, tau[i_channel], 
             g[i_channel], p[i_channel], amf, am1, am2, r0, ak1, ak2)
                    
                alb_sph[i_channel] = zbrent(func_solv,x1,x2,100,1.e-6)
                if (alb_sph[i_channel]==1):
                    isnow= 5
                # alb_sph[i_channel]=(toa[i_channel] /r0)**(1./(ak1*ak2/r0))
                # end loop channels
                      
            # INTERNal CHECK FOR CLEAN PIXELS
            # if (alb_sph[0]>0.98): #go to 9393 = use clean pixel retrieval
            # if (alb_sph[1]>0.98): #go to 9393 = use clean pixel retrieval
            if (alb_sph[0]>0.98):
                isnow= 7
            
            if (alb_sph[1]>0.98): 
                isnow= 7

            # unnecessary loop
            #for i_channel in range(21):
                
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
            # alaska=w[0]
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
            # end of unnecessary loop
    
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
    
            if (toa[20]>=0.5):
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
                # ***********************END of MODIFICATION**************                   

    # derivation of plane albedo                  
    rp=alb_sph**ak1
              
    # derivation of snow reflectance function                      
    refl=r0*alb_sph**(ak1*ak2/r0)
    
    # STEP  5
    # CalCULATION OF BBA
    # solar flux calculation
    wave1=0.3
    wave2=0.7
    wave3=2.4
    wosk=0.4       
    sol0 = (f0 + f1*np.exp(-bet * 0.4) + f2*np.exp(-gam * 0.4))*0.1
    
    # solar flux calculation
    # sol1      visible(0.3-0.7micron)
    # sol2      near-infrared (0.7-2.4micron)
    # sol3      shortwave(0.3-2.4 micron)
    sol1= sol(wave2) - sol(wosk) + sol0
    sol1b = sol(wave2) - sol(wave1)
    sol2 = sol(wave3) - sol(wave2)
    sol3= sol1  +  sol2
    sol3b= sol1b  +  sol2

    # Spectral integration to derive broadband albedos  
    if (isnow == 0):              
        # clean snow
        # plane albedo
        sph_calc = 0 # planar
        # visible(0.3-0.7micron)
       
        def func_integ(x):
            return funp(x, al, sph_calc, ak1)
        
        p1 = qsimp(func_integ,wave1,wave2)
        rp1=p1/sol1
        
        # near-infrared (0.7-2.4micron)
#        p2 = trapzd(func_integ,wave2,wave3, 20)
        p2 = qsimp(func_integ,wave2,wave3)
        rp2=p2/sol2
        
        # shortwave(0.3-2.4 micron)
        rp3=(p1+p2)/sol3
     
        # spherical albedo
        sph_calc = 1 # spherical calculation
        
        def func_integ(x):
            return funp(x, al, sph_calc, ak1)
        
        # visible(0.3-0.7micron)
#        s1 = trapzd(func_integ,wave1,wave2, 20)
        s1 = qsimp(func_integ,wave1,wave2)
        rs1=s1/sol1
        # near-infrared (0.7-2.4micron)
#        s2 = trapzd(func_integ,wave2,wave3, 20)
        s2 = qsimp(func_integ,wave2,wave3)
        rs2=s2/sol2
        # shortwave(0.3-2.4 micron)
        rs3=(s1+s2)/sol3
        # END of clean snow bba calculation

    if (isnow == 1) or (isnow == 7) or (isnow == 6):
        # polluted snow
        # NEW CODE FOR BBA OF BARE ICE
        # alEX 29.08.2019
        # this code calculates bba analytically
    
        # ANAlYTICal EQUATION FOR THE NOMINATOR
        # integration over 3 segments
        
        # segment 1
        # QUADRATIC POLYNOMIal for the range 400-709nm
        # input wavelength
        alam2=w[0]
        alam3=w[5]
        alam5=w[10]
        #input reflectances
        r2=toa[0]
        r3=toa[5]
        r5=toa[10]
        
        sa1, a1, b1, c1 = quad_func(alam2,alam3,alam5,r2,r3,r5)
        aj1 = analyt_func(0.3, 0.7, a1, b1, c1, sol1b)

        # segment 2.1
        # QUADRATIC POLYNOMIal for the range 709-865nm
        # input wavelength
        alam6=w[11]
        alam7=w[16]
        alam8=w[20]
        #input reflectances
        r6=toa[11]
        r7=toa[16]
        r8=toa[20]
        
        asol = sol(0.865) - sol(0.7)
        sa1, a2, b2, c2 = quad_func(alam5,alam6,alam7,r5,r6,r7)                     
        aj2 = analyt_func(0.7, 0.865, a2, b2, c2, asol)

        # segment 2.2
        # exponential approximation for the range 865- 2400 nm
        rati=r7/r8
        alasta=(alam8-alam7)/np.log(rati)
        an=1./alasta
        p   = r7*np.exp(alam7/alasta)
#        sa1 = p *np.exp(-alam8/alasta)
        
        z1=0.865
        z2=2.4
        
        aj31=(1./an)*(np.exp(-an*z2)-np.exp(-an*z1))
        aj32=(1./(bet+an))*(np.exp(-(bet+an)*z2)-np.exp(-(an+bet)*z1))
        aj33=(1./(gam+an))*(np.exp(-(gam+an)*z2)-np.exp(-(an+gam)*z1))
        aj3=(-f0*aj31-f1*aj32-f2*aj33)*p
                   
        rp1 = aj1/sol1b    
        rp2 = (aj2+aj3)/sol2 #here segment 2.1 and 2.2 are summed
        rp3   = (aj1+aj2+aj3)/sol3b        

    return BXXX, D, area, al, r0, isnow, conc, ntype,alb_sph, rp,refl, rp1, rp2, rp3, rs1, rs2, rs3
    
#%% ===========================================================================
def alb2rtoa(a, tau, g, p, amf, am1, am2, r0, ak1, ak2):
# Function that calculates the theoretical reflectance from a snow spherical albedo a
# This function can then be solved to find optimal snow albedo
# Inputs:
# a                     Surface albedo
# sza                   Solar zenith angle
# vza                   Viewing zenith angle
# raa                   Relative azimuth angle
# wave                  wavelength of the OLCI band considered: wave=w(isk) 
# r0                    reflectance of a semi-infinite non-absorbing snow layer 
# height                Height of the surface (m)
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
    
    ratm = salbed(tau, g)
    surf = t1*t2*r0*a**(ak1*ak2/r0)/(1-a*ratm)
    rs=r + surf
    return rs

#%% ===========================================================================
def salbed(tau, g):
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
        else: aks=g**[i]
        a=a  + a_s[i]*aks
        b=b  + bs[i]*aks
        c= c +cs[i]*aks
        al=al +als[i]*aks
        bet=bet +bets[i]*aks
    
    salbed = tau*(a*np.exp(-tau/al)+b*np.exp(-tau/bet)+c)
    return salbed

#%% =====================================================================
def zbrent(f, x0, x1, max_iter=50, tolerance=1e-5):
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
        return 1
 
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

#%% ==================================================================      
def sol(x):
    # SOLAR SPECTRUM at GROUND level
    # Inputs:
    # x         wave length in micrometer
    # Outputs: 
    # sol       solar spectrum in W m-2 micrometer-1 (?)
                            
    #    if (x < 0.4):
    #            x=0.4
            
    sol1a = f0*x
    sol1b = - f1*np.exp(-bet*x)/bet
    sol1c = - f2*np.exp(-gam*x)/gam
    return sol1a+sol1b+sol1c

#%% =====================================================================
def analyt_func(z1, z2, a, b, c, sol1):    
    ajx1=a*sol1

    ak1=(z2**2.-z1**2.)/2.
    ak2=(z2/bet+1./bet**2)*np.exp(-bet*z2) - (z1/bet+1./bet**2)*np.exp(-bet*z1)
    ak3=(z2/gam+1./gam**2)*np.exp(-gam*z2) - (z1/gam+1./gam**2)*np.exp(-gam*z1)
   
    ajx2=b*(f0*ak1  -f1*ak2  -f2*ak3 )
    
    am1=(z2**3.-z1**3.)/3.
    am2=(z2**2./bet+2.*z2/bet**2 +2./bet**3) *np.exp(-bet*z2)- (z1**2./bet+2.*z1/bet**2 +2./bet**3) *np.exp(-bet*z1)
    am3=(z2**2./gam+2.*z2/gam**2 +2./gam**3.)*np.exp(-gam*z2)- (z1**2./gam+2.*z1/gam**2 +2./gam**3.)*np.exp(-gam*z1)
    ajx3=c*(f0*am1 -f1*am2 -f2*am3)
                
    return ajx1+ajx2+ajx3

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
    # bav 2019
    #   replaced l and kss by k_closest
    #   replaced astra by y
    #   removed ks
 
    # tesing if x is close to available xa
    dif = abs(x-xa)
    if any(dif <= 1.e-6): 
        y = ya[(dif <= 1.e-6)]
    else:
        # otherwise interpolates
        k_closest = np.where(dif==dif.min())
        k_closest=k_closest[0]
        if len(k_closest)>1:
            # case when x is halfway between two xa
            k_closest=k_closest[0]
            
        if (x-xa[k_closest] <= 0):
            # if xa(k_closest) greater than x then we take the left interval
            x0=xa[k_closest-1]
            x1=xa[k_closest]
            y0=ya[k_closest-1]
            y1=ya[k_closest]
        else: 
            # if xa(k_closest) greater than x then we take the right interval
            x0=xa[k_closest]
            x1=xa[k_closest+1]
            y0=ya[k_closest]
            y1=ya[k_closest+1]
        y = y0+(x-x0)*(y1-y0)/(x1-x0)

    dega = 1000.* al * 4.*np.pi*y/x
    pow = np.sqrt(dega)
         
    if (pow >= 1.e-6): rsd = np.exp(-pow)
    else: rsd=1.
         
    if (sph_calc == 0):     rs = rsd**ak1
    elif (sph_calc == 1):   rs = rsd

    if (x < 0.4):  x = 0.4
    funcs = f0+f1*np.exp(-x*bet)+f2*np.exp(-x*gam)
     
    return rs*funcs

#%% ==========================================================================
def quad_func(x0,x1,x2,y0,y1,y2):
    d1=(x0-x1)*(x0-x2)
    d2=(x1-x0)*(x1-x2)
    d3=(x2-x0)*(x2-x1)

    a1=x1*x2*y0/d1+x0*x2*y1/d2+x0*x1*y2/d3
    b1=-(x1+x2)*y0/d1-(x0+x2)*y1/d2-(x0+x1)*y2/d3
    c1=y0/d1+y1/d2+y2/d3
    x=x1
    sa=a1+b1*x+c1*x*x
    return sa, a1, b1, c1

#%% ===============================
def qsimp(func,a,b):
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




from datetime import datetime
import json
import requests  # http://docs.python-requests.org/en/master/
import zipfile
import glob 
import os
import numpy as np
from pyproj import CRS,Transformer
import netCDF4 as nc 
from rasterio.transform import Affine
import rasterio as rio
import pandas as pd
from pyproj import CRS as CRSproj
import warnings
#from pyDataverse.api import NativeApi

def opentiff(filename):

    "Input: Filename of GeoTIFF File "
    "Output: xgrid,ygrid, data paramater of Tiff, the data projection"
    warnings.filterwarnings("ignore", category=FutureWarning)
    
    da = rio.open(filename)
    proj = CRSproj(da.crs)

    elevation = np.array(da.read(1),dtype=np.float32)
    nx,ny = da.width,da.height
    x,y = np.meshgrid(np.arange(nx,dtype=np.float32), np.arange(ny,dtype=np.float32)) * da.transform

    da.close()

    return x,y,elevation,proj

def to_netcdf(folder):
    
    BASE_PATH = os.path.abspath('..')
    UTIL_FOLDER = BASE_PATH + os.sep + 'util'
    meta = pd.read_csv(UTIL_FOLDER + os.sep + "nc_var_meta.csv")
    names = meta["names"] 
    longnames = meta["long_names"]
    units = meta["units"]
    transformer = Transformer.from_crs("EPSG:3413", "EPSG:4326")    
    
    files = glob.glob(folder + os.sep + "*.tif")
    rBRRfile = [f for f in files if f.split(os.sep)[-1] == "rBRR_01.tif"]
    output = [f.split(os.sep)[-1][:-4] for f in files]
    filename = folder.split(os.sep)[-1] + ".nc"
    ds = nc.Dataset(folder + os.sep + filename, 'w', format='NETCDF4')
    
    date = filename[9:-3].replace("_","-")
    current_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    x,y,z,proj = opentiff(files[0])
    x2,y2,z2,proj = opentiff(rBRRfile[0])
    
    
     
    lon_min,lat_min = transformer.transform(np.nanmin(x.ravel()), np.nanmin(y.ravel()))
    lon_max,lat_max = transformer.transform(np.nanmax(x.ravel()), np.nanmax(y.ravel()))

    lon,lat = transformer.transform(x,y)
    
    y = y[:,0]
    y_len = len(y)
    #print(f"Raw Y len: {y_len}")
    x = x[0,:]
    x_len = len(x)
    #print(f"Raw x len: {x_len}")
    
    y2 = y2[:,0] 
    y2_len = len(y2)
    #print(f"Model Y len: {y2_len}")
    x2 = x2[0,:]
    x2_len = len(x2)
    #print(f"model x len: {x2_len}")

    lon = lon[0,:]
    lat = lat[:,0]
    x_dim = ds.createDimension('x', len(x.ravel()))
    y_dim = ds.createDimension('y', len(y.ravel()))
    x2_dim = ds.createDimension('x2', len(x2.ravel()))
    y2_dim = ds.createDimension('y2', len(y2.ravel()))
    lat_var = ds.createVariable('lat', np.float32, ('y'), zlib=True)
    lat_var.units = 'degrees_north'
    lat_var.standard_name = 'latitude'
    lat_var.axis = 'Y'

    lon_var = ds.createVariable('lon', np.float64, ('x'), zlib=True)
    lon_var.units = 'degrees_east'
    lon_var.standard_name = 'longitude'
    lon_var.axis = 'X'

    x_var = ds.createVariable('x', np.float64, ('x') , zlib=True)
    x_var.units = 'meters'
    x_var.standard_name = 'x'
    x_var.axis = 'X'
    
    x2_var = ds.createVariable('x2', np.float64, ('x2') , zlib=True)
    x2_var.units = 'meters'
    x2_var.standard_name = 'x2'
    x2_var.axis = 'X'

    y_var = ds.createVariable('y', np.float64, ('y'), zlib=True)
    y_var.units = 'meters'
    y_var.standard_name = 'y'
    y_var.axis = 'Y'
    
    y2_var = ds.createVariable('y2', np.float64, ('y2'), zlib=True)
    y2_var.units = 'meters'
    y2_var.standard_name = 'y2'
    y2_var.axis = 'Y'

    crs_var = ds.createVariable('crs', 'i4')
    crs_var.standard_name = 'crs'
    crs_var.grid_mapping_name = 'x_y'
    crs_var.crs_wkt = proj.to_wkt()

    x_var[:] = x.ravel()
    y_var[:] = y.ravel()
    x2_var[:] = x2.ravel()
    y2_var[:] = y2.ravel()
    lon_var[:] = lon.ravel()
    lat_var[:] = lat.ravel()
    
    ds.instrument = "OLCI"
    ds.platform = "Sentinel-3A"
    ds.start_date_and_time = date + "T08:00:00Z"
    ds.end_date_and_time = date + "T16:00:00Z"
    ds.naming_authority = "geus.dk"
    ds.title = f'SICE Daily output for Greenland, {date}, pySICE v. 2.1'
    ds.summary = ''
    ds.keywords = 'Cryosphere > Land Ice > Land Ice Albedo > Reflectance > Greenland > Northern Hemisphere > Grain Size'
    ds.activity = 'Space Borne Instrument'
    ds.geospatial_lat_min = lat_min
    ds.geospatial_lat_max = lat_max
    ds.geospatial_lon_min = lon_min
    ds.geospatial_lon_max = lon_max
    ds.time_coverage_start = date + "T08:00:00Z"
    ds.time_coverage_end = date + "T16:00:00Z"
    ds.history = current_date + ' processed'
    ds.date_created = current_date
    ds.creator_type = "group"
    ds.creator_institution = "Geological Survey of Denmark and Greenland (GEUS)"
    ds.creator_email = " jeb@geus.dk, bav@geus.dk, rabni@geus.dk,adrien.wehrle@geo.uzh.ch"
    ds.creator_name = "Jason Box, Baptiste Vandecrux, Rasmus Bahbah Nielsen, Adrien Wehrlé"
    ds.creator_url = "https://orcid.org/0000-0003-2342-639X"
    ds.institution = "Geological Survey of Denmark and Greenland (GEUS)"
    ds.publisher_type = "Institute"
    ds.publisher_name = "Geological Survey of Denmark and Greenland (GEUS), Glaciology and Climate Department"
    ds.publisher_url = "geus.dk"
    ds.publisher_email= "jeb@geus.dk"
    ds.project = "Operational Sentinel-3 snow and ice products (SICE)"
    ds.license = "None"
   

    for f,o in zip(files,output):
        #print(o)
        x,y,z,proj = opentiff(f)
        if ((len(x[0,:]) == x_len) and (len(y[:,0]) == y_len)):
            z_out = ds.createVariable(o, 'f4', ('y', 'x'),zlib=True)
            #print("Raw format")
        else:
            z_out = ds.createVariable(o, 'f4', ('y2', 'x2'),zlib=True)
            #print("Model Format")
       
        for ii,nn in enumerate(names): 
            if o == nn: 
                print(f"File to Upload: {o}")
                
                z_out[:,:] = z
                z_out.standard_name = o
                z_out.long_name = longnames[ii]
                z_out.units = units[ii]
                
    ds.close()
    
    return folder + os.sep + filename

def dataverse_upload(folder,area):
    
    # --------------------------------------------------
    # Update the 4 params below to run this code
    # --------------------------------------------------
    
    BASE_PATH = os.path.abspath('..')
    UTIL_FOLDER = BASE_PATH + os.sep + 'util'
    
    dataverse_server = 'https://dataverse.geus.dk'
    api_key = ''
    
    #doi = pd.read_csv("GEUSdataverse_doi.csv")
    doi_csv = pd.read_csv(UTIL_FOLDER + os.sep + 'GEUSdataverse_doi.csv')
    doi = doi_csv[area][0]
    
    #api = NativeApi(dataverse_server,api_key)
    
    
    nc_file = to_netcdf(folder)
    fileup = {'file': open(nc_file, "rb")}

    
    
    output_filename = nc_file.split(os.sep)[-1]
    filedate =  nc_file[-13:-3]
    fileyear = filedate[:4]
    
    persistentId = doi
    
    
    url_persistent_id = '%s/api/datasets/:persistentId/add?persistentId=%s&key=%s' % (dataverse_server, persistentId, api_key)
    
    file_description = f"EDC SICE output: {output_filename}, date: {filedate}"
    
    params = dict(description=file_description,
                        directoryLabel=filedate)

    params_as_json_string = json.dumps(params)

    payload = dict(jsonData=params_as_json_string)

    r = requests.post(url_persistent_id,data = payload, files=fileup)
    
    print(r.json()['status'])
    
    if r.json()['status'] == 'ERROR':
            print(r.json())
    #else:
    #    resp = api.publish_dataset(doi, release_type "major")

 

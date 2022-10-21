# -*- coding: utf-8 -*-
"""
@author: bav@geus.dk

tip list:
    %matplotlib inline
    %matplotlib qt
    import pdb; pdb.set_trace()
"""

import os
from glob import glob
import xarray as xr
import netCDF4
import numpy as np
import rioxarray
import pandas as pd

try:
    import rasterio as rio
except ImportError:
    rio = None  # make rasterio optional at this stage


class sice_io(object):
    def __init__(self, dirname):

        self.dirname = dirname

        if dirname.endswith(".zarr"):
            self._get_size_zarr()
            self.open = self.open_zarr
        elif os.path.exists(os.path.join(dirname, 'Oa01_radiance.nc')):
            self._get_size_satpy()
            self.open = self.open_satpy
        elif os.path.exists(os.path.join(dirname, 'r_TOA_01.tif')):
            self._get_size_tif()
            self.open = self.open_tif
        elif dirname.endswith(".csv"):
            self.filepath = dirname
            self.open = self.open_csv
        else:
            csv_list = [file for file in os.listdir(dirname) if file.endswith('.csv')]
            if len(csv_list) == 1:
                self.filepath = os.path.join(dirname, csv_list[0])
                self.open = self.open_csv
            else:
                print("No tif, netcdf, (unique) csv or zarr file found in ", dirname)
    def open_csv(self):
        print(self.filepath)
        df = pd.read_csv(self.filepath)
        self.olci_scene = xr.Dataset(
            {"toa": (("xy", "band"), 
                     df[['Oa'+str(i).zfill(2) + '_reflectance' for i in range(1, 22)]].values),
             "sza": (("xy"),  df['sza'].values),
             "saa": (("xy"),  df['saa'].values),
             "vza": (("xy"),  df['vza'].values),
             "vaa": (("xy"),  df['vaa'].values),
             "ozone": (("xy"),  df['total_ozone'].values),
             "elevation": (("xy"),  df['elevation'].values),
             },
            coords={
                "xy": np.arange(df.shape[0]),
                "band": np.arange(0,21),
            },
        )
    def _open_tif(self, filename):
        return rio.open(os.path.join(self.dirname, filename))

    def _get_size_tif(self):
        self.meta = self._open_tif('r_TOA_01.tif').meta
        self.original_width = self.meta['width']
        self.original_height = self.meta['height']

    def open_tif(self, x0=0, y0=0, width=None, height=None):
        # # %% ========= input tif ===============
        if not os.path.isdir(self.dirname):
            raise Exception("dirname must be a directory")

        def read_tif(filename):
            chunks = None
            chunks = 'auto'
            # data = xr.open_rasterio(os.path.join(self.dirname, filename), chunks=chunks).squeeze(dim='band', drop=True)
            data = rioxarray.open_rasterio(os.path.join(self.dirname, filename), chunks=chunks).squeeze(dim='band', drop=True)

            if width is not None:
                data = data.isel(x=slice(x0, x0 + width))
            if height is not None:
                data = data.isel(y=slice(y0, y0 + height))

            return data.stack(xy=("x", "y")).compute()

        self.meta['transform'] = rio.transform.Affine(1.0, 0.0, 0.0, 0.0, -1.0, 0.0)  # to improve. This is invalid in some cases
        self.meta.update(compress='DEFLATE')
        self.toa = []
        for i in range(21):
            try:
                dat = read_tif(f'r_TOA_{i + 1:02}.tif')
            except:
                if i in [16, 20]:
                    raise Exception('Missing the necessary bands')
                else:
                    print('Cannot load ', 'r_TOA_'+str(i+1).zfill(2)+'.tif, replacing by nans')
                    dat = xr.full_like(self.toa[0], fill_value=np.nan)
            self.toa.append(dat)
        self.olci_scene = xr.Dataset()
        self.olci_scene['toa'] = xr.concat(self.toa, dim='band')
        # print("toa=", self.toa.coords)

        self.olci_scene['ozone'] = read_tif('O3.tif')
        # self.water = read_tif('WV.tif')  # save memory, it is not used
        self.olci_scene['sza'] = read_tif('SZA.tif')
        self.olci_scene['saa'] = read_tif('SAA.tif')
        self.olci_scene['vza'] = read_tif('OZA.tif')
        self.olci_scene['vaa'] = read_tif('OAA.tif')
        self.olci_scene['elevation'] = read_tif('height.tif').astype(np.float64)

        try:
            self.olci_scene['aot'] = read_tif('AOD_550.tif').fillna(0.1)
            self.olci_scene['aer_ang'] = read_tif('ANG.tif').fillna(1.3)
            print('Reading aerosol properties from file')
        except:
            self.olci_scene['aot'] = self.olci_scene['sza'] * 0 + 0.1
            self.olci_scene['aer_ang'] = self.olci_scene['sza'] * 0 + 1.3
            print('Default aerosol properties (AOT=0.1)')

        mask = ~np.isnan(self.olci_scene.toa.sel(band=0))
        self.olci_scene = self.olci_scene.where(mask)

        t = self.olci_scene.elevation.unstack('xy')
        self.meta['width'] = len(t.x)
        self.meta['height'] = len(t.y)

    def _get_size_satpy(self):
        filename = os.path.join(self.dirname, 'Oa01_radiance.nc')
        rootgrp = netCDF4.Dataset(filename, "r")
        self.original_width = rootgrp.dimensions['columns'].size
        self.original_height = rootgrp.dimensions['rows'].size

    def open_satpy(self, x0=0, y0=0, width=None, height=None, with_geom=True):
        import satpy  # this is not good practice but avoid satpy to be a compulsary dependence

        filenames = glob(os.path.join(self.dirname, "*.nc"))

        scene = satpy.Scene(reader="olci_l1b", filenames=filenames)

        variables = {
            'solar_azimuth_angle': 'saa',
            'solar_zenith_angle': 'sza',
            'satellite_azimuth_angle': 'vaa',
            'satellite_zenith_angle': 'vza',
            'total_ozone': 'ozone',
            'altitude': 'elevation'
        }

        scene.load(list(variables.keys()))

        islice = {}
        if width is not None:
            islice['x'] = slice(x0, x0 + width)
        if height is not None:
            islice['y'] = slice(y0, y0 + height)

        def get_var(variable):
            # return the variable and remove what needs to be remove
            data = scene[variable].isel(islice).compute().stack(xy=("x", "y"))
            data.attrs = {}  # remove attributes, due to some conflict with tà_zarr being unable to serialize datatime
            if 'crs' in data.coords:
                del data.coords['crs']  # idem. zarr complains
            return data

        self.olci_scene = xr.Dataset()
        if with_geom:
            scene.load(['longitude', 'latitude'])
            self.olci_scene = self.olci_scene.assign_coords(longitude=get_var('longitude'),
                                                            latitude=get_var('latitude'))
        for variable in variables:
            self.olci_scene[variables[variable]] = get_var(variable)

        scene.unload()  # maybe useless

        coef = 1 / np.cos(np.deg2rad(self.olci_scene['sza'])) / 100.

        bands = [f'Oa{i:02}' for i in range(1, 22)]
        scene.load(bands)

        scene.load([satpy.DataQuery(name=band, calibration='reflectance') for band in bands])
        toa = []
        for band in bands:
            toa.append(np.clip(get_var(band) * coef, 0, 1))
        self.olci_scene['toa'] = xr.concat(toa, dim='band')

        if 'crs' in self.olci_scene['toa'].coords:
            del self.olci_scene['toa'].coords['crs']  # idem. zarr complains

        scene.unload()  # probably useless

    def _get_size_zarr(self):
        ds = xr.open_zarr(self.dirname)
        self.original_width = len(ds.x)
        self.original_height = len(ds.y)

    def open_zarr(self, x0=0, y0=0, width=None, height=None, with_geom=True):

        variables = {
            'solar_azimuth_angle': 'saa',
            'solar_zenith_angle': 'sza',
            'satellite_azimuth_angle': 'vaa',
            'satellite_zenith_angle': 'vza',
            'total_ozone': 'ozone',
            'altitude': 'elevation'
        }

        ds = xr.open_zarr(self.dirname)

        islice = {}
        if width is not None:
            islice['x'] = slice(x0, x0 + width)
        if height is not None:
            islice['y'] = slice(y0, y0 + height)

        def get_var(variable):
            # return the variable and remove what needs to be remove
            return ds[variable].isel(islice).stack(xy=("x", "y")).compute()

        self.olci_scene = xr.Dataset()
        if with_geom:
            self.olci_scene['longitude'] = get_var('longitude')
            self.olci_scene['latitude'] = get_var('latitude')

        for variable in variables:
            self.olci_scene[variables[variable]] = get_var(variable)

        bands = [f'Oa{i:02}' for i in range(1, 22)]
        toa = []
        for band in bands:
            toa.append(get_var(band))
        self.olci_scene['toa'] = xr.concat(toa, dim='band')

    def to_geotif(self, extended_output=False, save_spectral=False):
        def write_output(var, var_name, in_folder, meta):
            # this functions write tif files based on a model file, here "Oa01"
            # opens a file for writing
            var = var.unstack(dim='xy').transpose('y', 'x')
            var.rio.to_raster(os.path.join(in_folder, var_name + '.tif'))
            # with rio.open(os.path.join(in_folder, var_name + '.tif'), 'w+', **meta) as dst:
            #     dst.write(var.astype('float32'), 1)

        # write_output(self.D, 'grain_diameter',self.dirname)
        write_output(6 / 0.917 / self.diameter, 'snow_specific_area', self.dirname, self.meta)
        write_output(self.rp3, 'albedo_bb_planar_sw', self.dirname, self.meta)
        write_output(self.rs3, 'albedo_bb_spherical_sw', self.dirname, self.meta)
        # write_output(self.longitude, 'longitude', self.dirname, self.meta)
        # write_output(self.latitude, 'latitude', self.dirname, self.meta)
        if isinstance(self.isnow, np.ndarray):
            self.isnow = xr.DataArray(self.isnow, coords=self.sza.coords)
        write_output(self.isnow, 'diagnostic_retrieval', self.dirname, self.meta)

        if extended_output:
            write_output(self.al, 'al', self.dirname, self.meta)
            write_output(self.r0, 'r0', self.dirname, self.meta)
            if hasattr(conc):
                write_output(self.conc, 'conc', self.dirname, self.meta)
            else:
                print("no conc")

        if save_spectral:
            # for i in np.arange(21):
            for b in np.append(np.arange(11), np.arange(15, 21)):
                write_output(self.alb_sph.sel(band=b), f'albedo_spectral_spherical_{b+1:02}', self.dirname, self.meta)
                write_output(self.rp.sel(band=b), f'albedo_spectral_planar_{b+1:02}', self.dirname, self.meta)
                write_output(self.refl.sel(band=b), f'rBRR_{b+1:02}', self.dirname, self.meta)

    def to_zarr(self, append_dim=None):
        ds = xr.Dataset({'snow_specific_area': 6 / 0.917 / self.diameter.unstack(dim='xy'),
                         'albedo_bb_planar_sw': self.rp3.unstack(dim='xy'),
                         'albedo_bb_spherical_sw': self.rs3.unstack(dim='xy')})

        if append_dim:
            mode = 'a'
            encodings = None
        else:
            mode = 'w'
            encodings = {v: {"dtype": "float32"} for v in ds.variables}

        output_path = self.dirname
        if output_path.endswith('.zarr'):
            output_path, _ = os.path.splitext(output_path)
        if output_path.endswith('.SEN3'):
            output_path, _ = os.path.splitext(output_path)
        ds.to_zarr(output_path + '.OUT.zarr', mode=mode, append_dim=append_dim, encoding=encodings, consolidated=True)


def write_output(snow, OutputFolder, filename):
    if filename.endswith('.csv'):
        print('\nText file output')
        data_out = pd.DataFrame()
        data_out['grain_diameter'] = snow.diameter.to_pandas()
        data_out['snow_specific_area']= snow.area.to_pandas()
        data_out['al'] = snow.al.to_pandas()
        data_out['r0'] = snow.r0.to_pandas()
        data_out['diagnostic_retrieval'] = snow.isnow.to_pandas()
        # data_out['conc'] = snow.conc.to_pandas()
        data_out['albedo_bb_planar_sw'] = snow.rp3.to_pandas()
        data_out['albedo_bb_spherical_sw'] = snow.rs3.to_pandas()
        # for i in np.append(np.arange(11), np.arange(15,21)):
        # for i in np.arange(21):
            # data_out['albedo_spectral_spherical_' + str(i + 1).zfill(2)] = snow.alb_sph[i,:,:]
        # for i in np.append(np.arange(11), np.arange(15,21)):
            # data_out['rBRR_'+str(i+1).zfill(2)] = snow.rp[i,:,:]
        data_out.to_csv(OutputFolder + '/out.csv')
        print(OutputFolder + '/out.csv')
    else:
        file_name_list = {
            "BXXX": "O3_SICE",
            "diameter": "grain_diameter",
            "area": "snow_specific_area",
            "al": "al",
            "r0": "r0",
            "isnow": "isnow",
            "conc": "conc",
            "rp3": "albedo_bb_planar_sw",
            "rs3": "albedo_bb_spherical_sw",
            "factor": "factor",
        }
        print('Printing out:')
        for var in ["diameter", "area", "rp3", "rs3", "isnow", "r0", "al"]:
            print(var)
            snow[var].unstack(dim="xy").transpose("y", "x").rio.to_raster(
                os.path.join(OutputFolder, file_name_list[var] + ".tif")
            )
        snow.alb_sph.sel(band=0).unstack(dim="xy").transpose("y", "x").rio.to_raster(OutputFolder+'/alb_sph_01_solved.tif')
        snow.rp.sel(band=0).unstack(dim="xy").transpose("y", "x").rio.to_raster(OutputFolder+'/alb_pl_01_solved.tif')
        # for var in ['BXXX', ]:
        #     var = OLCI_scene[var].unstack(dim='xy').transpose('y', 'x').rio.to_raster(os.path.join(OutputFolder, file_name_list[var] + '.tif'))

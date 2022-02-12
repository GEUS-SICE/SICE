#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO

Post processing, analysis and vizualisation of SICE outputs

TODOs:
  - comment and generate documentation
  - implement method for bare ice area and AAR computation
  - implement methods to generate simple visualisations

"""

import numpy as np
import rasterio
import glob
from typing import Union
import pathlib
import os
from collections import Counter
from multiprocessing import Pool
import time
import functools


class PostSICE:
    def __init__(
        self,
        dataset_path: str,
        regions: Union[list, None] = ["Greenland"],
        variables: list = ["albedo_bb_planar_sw", "snow_specific_surface_area"],
    ) -> None:

        self.working_directory = str(pathlib.Path().resolve())
        self.dataset_path = dataset_path
        self.variables = variables
        self.files = {}

        self.get_SICE_region_names()

        if not regions:
            self.get_available_regions()
        else:
            self.regions = regions

        self.get_files()
        self.get_generic_profiles()
        
        return None

    def timer(func):
        """Print the runtime of the decorated function"""

        @functools.wraps(func)
        def wrapper_timer(*args, **kwargs):
            start_time = time.perf_counter()  # 1
            value = func(*args, **kwargs)
            end_time = time.perf_counter()  # 2
            run_time = end_time - start_time  # 3
            print(f"Finished {func.__name__!r} in {run_time:.4f} secs")
            return value

    return wrapper_timer

    def get_SICE_region_names(self) -> list:

        SICE_masks = glob.glob(f"{self.working_directory}/masks/*_1km.tif")

        self.SICE_region_names = [
            mask.split(os.sep)[-1].split("_")[0] for mask in SICE_masks
        ]

        return self.SICE_region_names

    def get_available_regions(self) -> list:

        available_regions = [
            region
            for region in self.SICE_region_names
            if os.path.isdir(f"{self.dataset_path}/{region}")
        ]

        if available_regions:
            self.regions = available_regions
        else:
            print(
                "No region with processed SICE data detected, please provide"
                + "a list of region names"
            )

        return None

    def get_files(self) -> dict:

        for region in self.regions:

            self.files[region] = {
                variable: sorted(
                    glob.glob(f"{self.dataset_path}/{region}/*/{variable}.tif")
                )
                for variable in self.variables
            }

        return self.files

    def get_generic_profiles(self) -> list:

        self.generic_profiles = {
            region: rasterio.open(self.files[region][self.variables[0]][0]).profile
            for region in self.regions
        }

        return self.generic_profiles

    def get_BBA_combination_files(self) -> list:

        for region in self.regions:

            self.files[region]["BBA_combination"] = sorted(
                glob.glob(f"{self.dataset_path}/{region}/*/BBA_combination.tif")
            )

        return self.files

    def compute_BBA_combination(
        self, albedo_file, bands: list = ["01", "06", "17", "21"]
    ) -> None:
        def load_rasters_as_list(files):
            data = [rasterio.open(file).read(1) for file in files]
            return data

        planar_BBA = rasterio.open(albedo_file).read(1)

        region = albedo_file.split(os.sep)[-3]
        folder = albedo_file.rsplit(os.sep, 1)[0]
        r_TOA_files = [f"{folder}/r_TOA_{b}.tif" for b in bands]

        # compute only if all variables are available
        compute = np.prod([os.path.isfile(file) for file in r_TOA_files])

        if not compute:
            return None

        r_TOAs = load_rasters_as_list(r_TOA_files)

        r_TOAs_combination = np.sum(r_TOAs, axis=0) / 4

        empirical_BBA = 1.003 * r_TOAs_combination + 0.058

        planar_BBA[(planar_BBA < 0) & (planar_BBA > 1)] = np.nan

        BBA_combination = np.full_like(planar_BBA, np.nan)

        BBA_combination[:, :] = planar_BBA

        # integrate empirical_BBA when planar_BBA values are below bare ice albedo
        BBA_combination[planar_BBA <= 0.565] = empirical_BBA[planar_BBA <= 0.565]

        with rasterio.open(
            f"{folder}/BBA_combination.tif", "w", **self.generic_profiles[region]
        ) as dst:
            dst.write(planar_BBA, 1)

        return None

    @timer
    def compute_BBA_combinations_multiprocessing(self, nb_cores: int = 4) -> None:

        all_albedo_files = [
            self.files[region]["albedo_bb_planar_sw"]
            for region, values in self.files.items()
        ][0]

        with Pool(nb_cores) as p:
            p.map(self.compute_BBA_combination, all_albedo_files)

        return None

    def prepare_Lx_multiprocessing(self, variable: str) -> dict:

        multiprocessing_partitions = {}

        for region in self.regions:

            region_variable_files = np.array(self.files[region][variable])
            region_years = np.array(
                [f.split(os.sep)[-2][:4] for f in region_variable_files]
            )
            available_years = np.array(list(Counter(region_years).keys()))

            # split the list of files per year to get multiprocessing partitions
            partitions = [
                region_variable_files[region_years == year] for year in available_years
            ]
            multiprocessing_partitions[region] = partitions

        return multiprocessing_partitions

    def compute_Lx_product(self, files_to_process: list) -> None:
        def compute_L3_step(
            data_stack_arr: list,
            i: int,
            rolling_window: int = 10,
            deviation_threshold: float = 0.15,
            limit_valid_days: int = 4,
        ) -> Union[np.ndarray, None]:

            if (
                i < rolling_window / 2
                or i > np.shape(data_stack_arr)[-1] - rolling_window / 2
            ):
                return None

            low_boundary = i - int(rolling_window / 2)
            high_boundary = i + int(rolling_window / 2 + 1)
            # TODO: have to stack into an array
            window_data = data_stack_arr[:, :, low_boundary:high_boundary]

            # load albedo raster at the center of rolling_window
            BBA_center = window_data[:, :, int(rolling_window / 2)]

            # # commentmpute median for each pixel time series
            median_window = np.nanmedian(window_data, axis=2)

            # per-pixel deviations within rolling_window
            deviations = np.abs((BBA_center - median_window) / median_window)

            ldata = np.full_like(BBA_center, np.nan)

            ldata[deviations < deviation_threshold] = np.nanmean(window_data, axis=2)[
                deviations < deviation_threshold
            ]

            ldata[deviations >= deviation_threshold] = np.nan

            return ldata

        variable = files_to_process[0].split(os.sep)[-1].split(".")[0]

        # L3 step is a rolling window, therefore accessing several times the same matrix,
        # so let's open the entire data set beforehand for efficiency
        data_stack = [rasterio.open(file).read(1) for file in files_to_process]
        data_stack_arr = np.dstack(data_stack)
        
        region = files_to_process[0].split(os.sep)[-3]
        regional_mask = rasterio.open(
            f"{self.working_directory}/masks/{region}_1km.tif"
        ).read(1)

        output_path = (
            f"{files_to_process[0].rsplit(os.sep, 2)[0]}/L{self.level}_product_t/{variable}"
        )
        print(output_path)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        Lx_product = np.empty_like(regional_mask)
        Lx_product[:, :] = np.nan

        for i, data in enumerate(data_stack):

            date = files_to_process[i].split(os.sep)[-2]

            data[regional_mask != 220] = np.nan

            if self.level == 3:
                ldata = compute_L3_step(data_stack_arr, i)
                if isinstance(ldata, type(None)):
                    continue
            else:
                ldata = data.copy()

            print(ldata)

            if ("albedo" or "BBA") in variable:
                valid = [(ldata > 0) & (ldata < 1)]
            elif "area" in variable:
                valid = [(ldata > 0) & (ldata < 1)]
            elif "diameter" in variable:
                valid = [(ldata > 0) & (ldata < 1)]

            Lx_product[valid] = ldata[valid]

            with rasterio.open(
                f"{output_path}/{date}.tif",
                "w",
                compress="deflate",
                **self.generic_profiles[region],
            ) as dest:
                dest.write(Lx_product, 1)

        return None

    @timer
    def compute_Lx_products_multiprocessing(
        self, level: int = 2, nb_cores: int = 4, Lx_variables: Union[None, str] = None
    ):

        if not Lx_variables:
            Lx_variables = self.variables
        self.level = level

        for variable in Lx_variables:

            multiprocessing_iterators = self.prepare_Lx_multiprocessing(variable)

            for region, annual_iterators in multiprocessing_iterators.items():

                with Pool(nb_cores) as p:
                    p.map(self.compute_Lx_product, annual_iterators)

        return None

    def compute_bare_ice_area(self):
        return None

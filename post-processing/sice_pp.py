#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO

"""

import numpy as np
import rasterio
import glob
from typing import Union, Tuple
import pathlib
import os
from collecitons import Counter
from multiprocessing import Pool, freeze_support
from functools import partial

class SICEPostProcessing:
    def __init__(
        self,
        dataset_path: str,
        regions: Union[None, list] = None,
        variables: list = ["albedo_planar_sw", "grain_diameter"],
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

        return None

    def get_SICE_region_names(self) -> list:

        SICE_masks = glob.glob(f"{self.working_directory}/*_1km.tif")

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
                "No region with processed SICE data detected, please provide a\
                list of region names"
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

    def prepare_multiprocessing(self, variable: str) -> Tuple[list, list]:

        multiprocessing_partitions = []

        for region in self.regions:

            region_variable_files = np.array(self.files[region][variable])
            available_years = Counter(
                [f.split(os.sep)[-2][-4:] for f in region_variable_files]
            )

            # split the list of files to get multiprocessing partitions
            partitions = [
                region_variable_files[region_variable_files == year]
                for year in available_years
            ]
            multiprocessing_partitions.append(partitions)

        return multiprocessing_partitions


    def compute_L2_products(
        self, nb_cores: int = 4, L2_variables: Union[None, str] = None
    ):

        if not L2_variables:
            L2_variables = self.variables

        def compute_L2_product_multiproc(files_to_process: list, variable: str) -> None:

            ex_file = file_to_process[0]
            ex_reader = rasterio.open(ex_file)
            ex_data = ex_reader.read(1)
            output_meta = ex_reader.meta.copy()
            
            region = ex_file.split(os.sep)[-3]
            regional_mask = rasterio.open(f"{self.working_directory}/masks/{region}_1km.tif"

            output_path = f'{ex_file.rsplit(os.sep, 2)}/{region}/L2_product'
                                          
            L2_product = np.empty_like(ex_data)
            L2_product[:, :] = np.nan

            for file in files_to_process:

                date = file.split(os.sep)[-2]
                                          
                data = rasterio.open(file).read(1)
                data[regional_mask != 220] = np.nan
                                          
                if ("albedo" or "BBA") in variable:
                    valid = [(data > 0) & (data < 1)]
                elif "ssa" in variable:
                    valid = [(data > 0) & (data < 1)]
                elif "diameter" in variable:
                    valid = [(data > 0) & (data < 1)]

                L2_product[valid] = data[valid]

                with rasterio.open(
                    f"{output_path}/{date}.tif",
                    "w",
                    compress="deflate",
                    **out_meta,
                ) as dest:
                    dest.write(L2_product, 1)

            return None

        for variable in L2_variables:

            multiprocessing_iterators = self.prepare_multiprocessing(variable)

            start_time = time.time()
            start_local_time = time.ctime(start_time)

            with Pool(nb_cores) as p:
                p.map(partial(compute_L2_product_multiproc, b=variable),
                      multiprocessing_iterators)


            end_time = time.time()
            end_local_time = time.ctime(end_time)
            processing_time = (end_time - start_time) / 60
            print("--- Processing time: %s minutes ---" % processing_time)
            print("--- Start time: %s ---" % start_local_time)
            print("--- End time: %s ---" % end_local_time)
                                          

        return None


    def compute_BBA_combination(self):
        return None

    def compute_bare_ice_area(self):
        return None

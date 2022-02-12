#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO

"""

from psice import PostSICE

dataset_path = '/media/adrien/Elements/show_case_v14'

# %% check initialization

# one region, default variables
d1 = PostSICE(dataset_path=dataset_path, regions=['Greenland'])
assert isinstance(d1.files, dict)
assert len(d1.files) == 1
assert list(d1.files['Greenland'].keys()) == ['albedo_bb_planar_sw', 'snow_specific_surface_area']
assert len(d1.files['Greenland']['albedo_bb_planar_sw']) > 2
assert len(d1.files['Greenland']['snow_specific_surface_area']) > 2

# two regions, default variables
d2 = PostSICE(dataset_path=dataset_path, regions=['Greenland', 'Iceland'])
assert isinstance(d2.files, dict)
assert len(d2.files) == 2
assert list(d2.files['Iceland'].keys()) == ['albedo_bb_planar_sw', 'snow_specific_surface_area']
assert len(d2.files['Iceland']['albedo_bb_planar_sw']) > 2
assert len(d2.files['Iceland']['snow_specific_surface_area']) > 2

# all available regions, default variables
d3 = PostSICE(dataset_path=dataset_path)
assert isinstance(d3.files, dict)
assert len(d3.files) == 10
assert list(d3.files['NovayaZemlya'].keys()) == ['albedo_bb_planar_sw', 'snow_specific_surface_area']
assert len(d3.files['NovayaZemlya']['albedo_bb_planar_sw']) > 2
assert len(d3.files['NovayaZemlya']['snow_specific_surface_area']) > 2

# %% check multiprocessing preparation with d1
partitions = d1.prepare_multiprocessing('albedo_bb_planar_sw')
assert partitions
assert isinstance(partitions, dict)
assert list(partitions.keys()) == ['Greenland']

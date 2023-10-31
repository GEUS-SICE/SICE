# -*- coding: utf-8 -*-
"""
Created on Fri Oct 27 14:46:00 2023

@author: rabni
"""

import subprocess
import os
from datetime import datetime
import pandas as pd

months = ['03','04','05','06','07','08','09','10']

sday = 'YYYY-MM-DD'
enday = 'YYYY-MM-DD'

dates = pd.date_range(start=sday,end=enday).to_pydatetime().tolist()
dates = [d.strftime("%Y-%m-%d") for d in dates]
dates = [d for d in dates if d[5:7] in [ m for m in months]]

area = ['Greenland']

for a in area: 
    for d in dates:
        print(f"Processing {d}")
        subprocess.call(['python', 'pysicehub.py','-d', d, '-a', a, '-r', '500']) 
        print("Deleteing Raw Data and Output") 
        subprocess.call(['python', 'output_del.py']) 
        subprocess.call(['python', 'download_del.py']) 
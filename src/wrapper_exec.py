# -*- coding: utf-8 -*-
"""
Created on Mon Oct 30 09:18:38 2023

@author: rabni
"""
import argparse
import subprocess
import os
from datetime import datetime
import pandas as pd

def parse_arguments():
        parser = argparse.ArgumentParser(description='Date range excicuteable for the pySICE Module')
        parser.add_argument("-st","--sday", type=str,help="Please input the start day")
        parser.add_argument("-en","--eday", type=str,help="Please input the end day")
        parser.add_argument("-ar","--area", type=str,default='default',help="Please input the areas you want to process")
        args = parser.parse_args()
        return args
    
months = ['03','04','05','06','07','08','09','10']
args = parse_arguments() 

dates = pd.date_range(start=args.sday,end=args.eday).to_pydatetime().tolist()
dates = [d.strftime("%Y-%m-%d") for d in dates]
dates = [d for d in dates if d[5:7] in [ m for m in months]]

if args.area != "default":
    area_list = args.area
else:
    area_list = ['Greenland']

if type(area_list) == str:
    area_list = [area_list]     

for a in area_list: 
    for d in dates:
        print(f"Processing {d}")
        subprocess.call(['python', 'pysicehub.py','-d', d, '-a', a, '-r', '500']) 
        print("Deleteing Raw Data and Output") 
        subprocess.call(['python', 'output_del.py']) 
        subprocess.call(['python', 'download_del.py']) 
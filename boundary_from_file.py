# -*- coding: utf-8 -*-
"""
@author: Adrien Wehrlé, GEUS (Geological Survey of Denmark and Greenland)
"""

import numpy as np
import pandas as pd
import json
import argparse

parser = argparse.ArgumentParser(description='Boundary from file')
parser.add_argument('file', help='File used to create boundary: csv and geojson extensions implemented')

args = parser.parse_args()

def boundary_from_file(file):
    
    #extension extraction out of file name
    extension=file.split('.')[-1]
    
    #data loading
    if extension=='geojson':
        with open(file,encoding='utf8') as f:
            data = json.load(f)
            coordinates=data['features'][0]['geometry']['coordinates']
            #check for different coordinates organisation
            if len(np.shape(coordinates))!=2:
                coordinates=data['features'][0]['geometry']['coordinates'][0]
                if len(np.shape(coordinates))!=2:
                    coordinates=data['features'][0]['geometry']['coordinates'][0][0]
                
    elif extension=='csv':
        coordinates=pd.read_csv(file)
    else:
        print('ERROR: %s extension not implemented' %extension)
        return
    
    #boundary initialisation
    boundary=''
     
    #boundary creation out of coordinates
    if extension=='geojson':
        for i in range(0,np.shape(coordinates)[0]): 
            if i==np.shape(coordinates)[0]-1:    
                boundary=boundary+str(coordinates[i][0])+' '+str(coordinates[i][1])+','
                boundary=boundary+str(coordinates[0][0])+' '+str(coordinates[0][1])
            else:
                boundary=boundary+str(coordinates[i][0])+' '+str(coordinates[i][1])+','
                
    if extension=='csv':
        for i in range(0,coordinates.shape[0]): 
            if i==coordinates.shape[0]-1:
                boundary=boundary+str(coordinates.iloc[i][0])+' '+str(coordinates.iloc[i][1])+','
                boundary=boundary+str(coordinates.iloc[0][0])+' '+str(coordinates.iloc[0][1])
            else:
                boundary=boundary+str(coordinates.iloc[i][0])+' '+str(coordinates.iloc[i][1])+','
            
    return boundary
    

boundary=boundary_from_file(args.file)

import shutil 
import os
import numpy as np
import argparse
def parse_arguments():
        parser = argparse.ArgumentParser(description='')
        parser.add_argument("-f","--folder", type=str,default="output")
        args = parser.parse_args()
        return args
if __name__ == "__main__":  
    
    args = parse_arguments()
    
    folder = os.path.abspath('..') + os.sep + args.folder
    folders = os.listdir(folder)

    delete = ["2017","2018","2019","2020","2021","2022","2023"]
    
    folders_del = [[f for f in folders if y in f] for y in delete]
    folders_del = [item for sublist in folders_del for item in sublist]        
    #print(folders_del)

    for ff in folders_del:
        print(f'deleting {ff}')
        shutil.rmtree(folder + os.sep + ff)

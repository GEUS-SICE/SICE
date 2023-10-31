import shutil 
import os
import numpy as np
from multiprocessing import set_start_method,get_context
import argparse
def parse_arguments():
        parser = argparse.ArgumentParser(description='')
        parser.add_argument("-f","--folder", type=str,default=f"downloads{os.sep}500")
        args = parser.parse_args()
        return args

def deletefolders(folder,subfolder): 
    
    shutil.rmtree(folder + os.sep + subfolder)
    
    print("subfolder: ",subfolder," deleted")

if __name__ == "__main__":     

    args = parse_arguments()
    folder = os.path.abspath('..') + os.sep + args.folder
    folders = os.listdir(folder)

    delete = ["2017_","2018_","2019_","2020_","2021_","2022_","2023_"]

    folders_del = [[f for f in folders if y in f] for y in delete]
    folders_del = [item for sublist in folders_del for item in sublist] 

    try:
        set_start_method("spawn")
    except:
        pass

    for ff in folders_del:
        print("deleting in folder: ",ff)
        subf = os.listdir(folder + os.sep + ff)

        mainf = [folder + os.sep + ff for i in range(len(subf))]

        with get_context("spawn").Pool(12) as p:     
            p.starmap(deletefolders,zip(mainf,subf))

        shutil.rmtree(folder + os.sep +  ff)

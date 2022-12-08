#!/usr/bin/env python
"""
Created on Wed Mar  4 13:12:18 2020

@author: Adam Binch (abinch@sagarobotics.com)
"""
##########################################################################################
#%%
from __future__ import division
import os, pickle, yaml, numpy as np
import matplotlib.pyplot as plt


map_dir = "fb3eb0bc-733b-4a73-8f78-8b9a9ff74134"

hd = os.path.expanduser("~")
map_path = os.path.join(hd, ".sentor_maps", map_dir)     

_map = pickle.load(open(map_path + "/topic_map.pkl", "rb"))
        
with open(map_path + "/config.yaml","r") as f:
    config = yaml.safe_load(f)
    
    
masked_map = np.ma.array(_map, mask=np.isnan(_map))

plt.figure(1); plt.clf()
plt.imshow(masked_map.T)
plt.colorbar()
plt.gca().set_aspect("equal", adjustable="box")
plt.tight_layout()    
plt.show()

mu = np.sum(masked_map) / (np.size(masked_map) - np.count_nonzero(masked_map.mask))
print("config: {}".format(config))
print("\naveraged topic arg = {}".format(mu))
#%%
##########################################################################################
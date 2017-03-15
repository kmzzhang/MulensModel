"""
Plots data and model for MB15310 with residuals (no fitting). 

From Janczak et al. 2010, ApJ 711, 731

NOTE: residuals have not been implemented in model.py
"""
import glob
import os
import matplotlib.pyplot as pl

import MulensModel
from MulensModel.mulensdata import MulensData
from MulensModel.fit import Fit
from MulensModel.event import Event
from MulensModel.model import Model
from MulensModel.utils import Utils

#Read in MB15310 data files (see data/MB15310) as MulensData objects
MODULE_PATH = "/".join(MulensModel.__file__.split("/source")[:-1])
print('MODULE_PATH: {0}'.format(MODULE_PATH))

#Grabbing all data files in the MB08310 folder
files = glob.glob(MODULE_PATH+"/data/MB08310"+"/*.tbl")
datasets = []
labels = []
for file_ in files:
	data = MulensData(file_name=file_, comments=["\\","|"])	
	datasets.append(data)
        labels.append(os.path.basename(file_))

#Define basic point lens model
t_0 = 2454656.39975
u_0 = 0.00300
t_E = 11.14
t_star = 0.05487
rho = t_star/t_E
plens_model = Model(t_0=t_0, u_0=u_0, t_E=t_E, rho=rho)

#Combine the data and model into an event
ev = Event(datasets=datasets, model=plens_model)

#Plot the data and model
pl.figure()
ev.plot_model()
ev.plot_data()
pl.title('Data and Fitted Model (Default)')

#Plot the data and model (customized)
pl.figure()
t_start= t_0 - 3.
t_stop = t_0 + 1.
ev.plot_model(color='black',t_start=t_start, t_stop=t_stop)
ev.plot_data(
    label=labels, fmt='o', 
    color=['black', 'red', 'yellow', 'green', 'cyan', 'blue', 'purple'])
pl.ylim(19,15.2)
pl.xlim(t_start, t_stop)
pl.legend(loc='upper left')
pl.title('Data and Fitted Model (Custom)')

pl.show()

#Plot the residuals (not implemented)


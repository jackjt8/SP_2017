# -*- coding: utf-8 -*-
"""
Created on Wed Feb 21 17:14:14 2018

@author: jackj

Title: dataplot2 - Refined dataplot.py
"""

import gps_particle_data
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mpld
import matplotlib.gridspec as gridspec
from matplotlib.ticker import AutoMinorLocator

#signal comparison
from scipy import signal
from scipy.stats.stats import pearsonr
import scipy.fftpack
from scipy import interpolate
from scipy.optimize import curve_fit

from lmfit import  Model

from inspect import getsourcefile
from os.path import abspath

#in order to address memory issues...
import gc


def load_data(this_sat,cdstart,cdend,localpath):
    # Load data.
    ms = gps_particle_data.meta_search(this_sat,localpath) # Do not pass meta_search satlist. Single sat ~12GB of RAM.
    ms.load_local_data(cdstart,cdend)
    ms.clean_up() #deletes json files.
    print ''
    
    output_data = ms.get_all_data_by_satellite()
    del ms # save RAM once we are finished.
    gc.collect()
    
#    print output_data
#    print len(output_data[this_sat])
#    print output_data[this_sat] is not None
    
    
    if len(output_data[this_sat]) != 0: # Seems to throw NoneType for 2005-08-14 ->20
        ddata = output_data[this_sat]['dropped_data']
        index2drop = [i for i, j in enumerate(ddata) if j == 1]
        
        if len(ddata) * 0.5 <= len(index2drop): # ie we must have at least 50% usuable data.
            print 'High drop rate. Skipping.'
            return [0], [0], [0], [0], [0], [0], [0], [0], [0]
        
        del ddata # save RAM once we are finished.
        
        dday =  output_data[this_sat]['decimal_day']
        dday[:] = [x - 1 for x in dday] # apply the -1 offset to dday as well..
        dday_dropped = np.delete(dday,index2drop)

        year = output_data[this_sat]['year']
        
        
        temp_ecr = np.asarray(output_data[this_sat]['rate_electron_measured']) 
        temp2_ecr = np.delete(temp_ecr,index2drop,0)
        temp3_ecr = np.array([np.interp(dday, dday_dropped, temp2_ecr[:,i]) for i in range(int(temp2_ecr.shape[1]))])
        ecr = temp3_ecr[:,:,0].T
        # save RAM once we are finished.
        del temp_ecr 
        del temp2_ecr
        
        temp_pcr = np.asarray(output_data[this_sat]['rate_proton_measured'])
        temp2_pcr = np.delete(temp_pcr,index2drop,0)
        temp3_pcr = np.array([np.interp(dday, dday_dropped, temp2_pcr[:,i]) for i in range(int(temp2_pcr.shape[1]))])
        pcr = temp3_pcr[:,:,0].T
        del temp_pcr # save RAM once we are finished.
        del temp2_pcr # save RAM once we are finished.
        
        temp_alt = output_data[this_sat]['Rad_Re']
        temp2_alt = np.delete(temp_alt,index2drop)
        satalt = np.interp(dday, dday_dropped, temp2_alt)
        del temp_alt # save RAM once we are finished.
        del temp2_alt # save RAM once we are finished.
        
        temp_bheight = output_data[this_sat]['b_coord_height']
        temp2_bheight = np.delete(temp_bheight,index2drop)
        bheight = np.interp(dday, dday_dropped, temp2_bheight)
        del temp_bheight # save RAM once we are finished.
        del temp2_bheight # save RAM once we are finished.
        
        temp_lon = output_data[this_sat]['Geographic_Longitude']
        temp2_lon = np.delete(temp_lon,index2drop)
        sat_lon = np.interp(dday, dday_dropped, temp2_lon)
        del temp_lon
        del temp2_lon
        
        del output_data # save RAM once we are finished.
        del index2drop # save RAM once we are finished.
        del dday_dropped # save RAM once we are finished.
        gc.collect()
        
        ourdates = []
        for i in range(len(dday)):
            ourdates.append(datetime(int(year[i]),1,1,0,0,0) + timedelta(days=dday[i][0]))
        
        # convert between datetime objects and matplotlib format
        ourmpldates = mpld.date2num(ourdates)
        #del ourdates # save RAM once we are finished.
        
        #Get angles from height and alt.
        angle = np.degrees(np.arcsin((bheight/satalt)))

        return ecr, pcr, dday, year, satalt, bheight, ourmpldates, angle, sat_lon
    else:
        return [0], [0], [0], [0], [0], [0], [0], [0], [0]
    
    
    # Fall back failure.
    return [0], [0], [0], [0], [0], [0], [0], [0], [0]




#%%
def turning_points(array):
    ''' https://stackoverflow.com/questions/19936033/finding-turning-points-of-an-array-in-python
    turning_points(array) -> min_indices, max_indices
    Finds the turning points within an 1D array and returns the indices of the minimum and 
    maximum turning points in two separate lists.
    '''
    idx_max, idx_min = [], []
    if (len(array) < 3): 
        return idx_min, idx_max

    NEUTRAL, RISING, FALLING = range(3)
    def get_state(a, b):
        if a < b: return RISING
        if a > b: return FALLING
        return NEUTRAL

    ps = get_state(array[0], array[1])
    begin = 1
    for i in range(2, len(array)):
        s = get_state(array[i - 1], array[i])
        if s != NEUTRAL:
            if ps != NEUTRAL and ps != s:
                if s == FALLING: 
                    idx_max.append((begin + i - 1) // 2)
                else:
                    idx_min.append((begin + i - 1) // 2)
            begin = i
            ps = s
    return idx_min, idx_max
        


def plot(this_sat, ecr, pcr, dday, year, satalt, bheight, ourmpldates, angle):
    #%%
        #!!!
        fig = plt.figure(figsize=(40, 30), dpi=160)
        #fig = plt.figure(figsize=(4, 3), dpi=80)
        gs1 = gridspec.GridSpec(11, 6) #7,6
        gs1.update(wspace=0.15, hspace=0.15)
        plt.tight_layout()
        
        titletext = 'Raw data plots for svn%s' % (this_sat)
        plt.suptitle(titletext, fontsize=20)
        fig.canvas.draw()
        
        #%%
        ax1 = plt.subplot(gs1[0,:])
        #!!! Need horizontal line for global CH2 stddev * 4
        
        for i in range(int(ecr.shape[1])):
            curlabel = 'Electron Channel %s' % (i)
            plt.plot_date(ourmpldates,ecr[:,i], label=curlabel)
        
        #plt.plot_date(ourmpldates,ch2)
        plt.ylabel('Electron rate', fontsize = 16)
        plt.setp(ax1.get_xticklabels(), visible=False)
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(4)
        ax1.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax1.yaxis.grid(False, which='minor')
        # Shrink current axis by 20%
        box = ax1.get_position()
        ax1.set_position([box.x0, box.y0, box.width * 0.9, box.height])
        # Put a legend to the right of the current axis
        ax1.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        #%%
        ax2 = plt.subplot(gs1[1,:],sharex=ax1)
        for i in range(int(pcr.shape[1])):
            curlabel = 'Proton Channel %s' % (i)
            plt.plot_date(ourmpldates,pcr[:,i], label=curlabel)
        
        plt.ylabel('Proton rate', fontsize = 16)
        plt.setp(ax2.get_xticklabels(), visible=False)
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(4)
        ax2.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax2.yaxis.grid(False, which='minor') 
    
        # Shrink current axis by 20%
        box = ax2.get_position()
        ax2.set_position([box.x0, box.y0, box.width * 0.9, box.height])
        # Put a legend to the right of the current axis
        ax2.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        # change axis location of ax2
        pos1 = ax1.get_position()
        pos2 = ax2.get_position()
        points1 = pos1.get_points()
        points2 = pos2.get_points()
        points2[1][1]=points1[0][1]
        pos2.set_points(points2)
        ax2.set_position(pos2)
        
        
        #%%
        ax3 = plt.subplot(gs1[2,:],sharex=ax1)
        plt.plot_date(ourmpldates,satalt)
        plt.ylabel('Altitude in Earth Radii', fontsize = 16)
        plt.setp(ax2.get_xticklabels(), visible=False)
        #plt.xlabel('Date', fontsize  = 16)
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(4)
        ax3.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax3.yaxis.grid(False, which='minor') 
        
        # Shrink current axis by 20%
        box = ax3.get_position()
        ax3.set_position([box.x0, box.y0, box.width * 0.9, box.height])
        # Put a legend to the right of the current axis
        ax3.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
         
        # change axis location of ax3
        pos2 = ax2.get_position()
        pos3 = ax3.get_position()
        points2 = pos2.get_points()
        points3 = pos3.get_points()
        points3[1][1]=points2[0][1]
        pos3.set_points(points3)
        ax3.set_position(pos3)
        
        #!!!
        #ax1.set_xlim(mpld.date2num([cdstart,cdend]))
        
        #%%
        
        ax9 = plt.subplot(gs1[3,:])
        plt.plot_date(ourmpldates,angle)
        plt.ylabel('Satellite angle from horizon', fontsize = 16)
        plt.xlabel('Date', fontsize  = 16)
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(4)
        ax9.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax9.yaxis.grid(False, which='minor') 
        
        # Shrink current axis by 20%
        box = ax9.get_position()
        ax9.set_position([box.x0, box.y0, box.width * 0.9, box.height])
        # Put a legend to the right of the current axis
        ax9.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
         
        # change axis location of ax9
        pos3 = ax3.get_position()
        pos9 = ax9.get_position()
        points3 = pos3.get_points()
        points9 = pos9.get_points()
        points9[1][1]=points3[0][1]
        pos9.set_points(points9)
        ax9.set_position(pos9)
        
        #%%
        ax4 = plt.subplot(gs1[4,:-3])
        for i in range(int(ecr.shape[1])):
            curlabel = 'Electron Channel %s' % (i)
            plt.scatter(satalt,ecr[:,i], label=curlabel)
        plt.ylabel('Electron rates', fontsize  = 16)
        #plt.xlabel('Altitude in Earth Radii', fontsize = 16)
        plt.setp(ax4.get_xticklabels(), visible=False)
        
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(5)
        ax4.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax4.yaxis.grid(False, which='minor') 
        
        # Shrink current axis by 20%
        box = ax4.get_position()
        ax4.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        # Put a legend to the right of the current axis
        ax4.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
    
        
        #%%
        ax5 = plt.subplot(gs1[5,:-3],sharex=ax4)
        for i in range(int(pcr.shape[1])):
            curlabel = 'Proton Channel %s' % (i)
            plt.scatter(satalt,pcr[:,i], label=curlabel)
        plt.ylabel('Proton rates', fontsize  = 16)
        plt.xlabel('Altitude in Earth Radii', fontsize = 16)
        
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(5)
        ax5.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax5.yaxis.grid(False, which='minor') 
        
        # Shrink current axis by 20%
        box = ax5.get_position()
        ax5.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        # Put a legend to the right of the current axis
        ax5.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        # change axis location of ax5
        pos4 = ax4.get_position()
        pos5 = ax5.get_position()
        points4 = pos4.get_points()
        points5 = pos5.get_points()
        points5[1][1]=points4[0][1]
        pos5.set_points(points5)
        ax5.set_position(pos5)
        
        #%%
        
        ax10 = plt.subplot(gs1[6,:-3])
        
        plt.scatter(satalt,bheight)   
        plt.ylabel('Height above plane in Re', fontsize = 16)
        plt.xlabel('Altitude in Earth Radii', fontsize  = 16)
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(5)
        ax10.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax10.yaxis.grid(False, which='minor') 
        
        # Shrink current axis by 20%
        box = ax10.get_position()
        ax10.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        # Put a legend to the right of the current axis
        ax10.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        # change axis location of ax10
        pos5 = ax5.get_position()
        pos10 = ax10.get_position()
        points5 = pos5.get_points()
        points10 = pos10.get_points()
        points10[1][1]=points5[0][1]
        pos10.set_points(points10)
        ax10.set_position(pos10)
        
        #%%
        ax6 = plt.subplot(gs1[4,3:])
        
        for i in range(int(ecr.shape[1])):
            curlabel = 'Electron Channel %s' % (i)
            plt.scatter(angle,ecr[:,i], label=curlabel)
            
        plt.ylabel('Electron rate', fontsize = 16)
        plt.xlabel('Angle from horizon', fontsize  = 16)
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(4)
        ax6.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax6.yaxis.grid(False, which='minor') 
        
        # Shrink current axis by 20%
        box = ax6.get_position()
        ax6.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        # Put a legend to the right of the current axis
        ax6.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        #%%
        
        ax7 = plt.subplot(gs1[5,3:])
        
        for i in range(int(pcr.shape[1])):
            curlabel = 'Proton Channel %s' % (i)
            plt.scatter(angle,pcr[:,i], label=curlabel)
            
        plt.ylabel('Proton rate', fontsize = 16)
        plt.xlabel('Angle from horizon', fontsize  = 16)
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(4)
        ax7.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax7.yaxis.grid(False, which='minor') 
        
        # Shrink current axis by 20%
        box = ax7.get_position()
        ax7.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        # Put a legend to the right of the current axis
        ax7.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        # change axis location of ax5
        pos6 = ax6.get_position()
        pos7 = ax7.get_position()
        points6 = pos6.get_points()
        points7 = pos7.get_points()
        points7[1][1]=points6[0][1]
        pos7.set_points(points7)
        ax7.set_position(pos7)
        
        #%%
        
        ax8 = plt.subplot(gs1[6,3:])
        
        plt.scatter(angle,satalt)   
        plt.ylabel('Altitude in Re', fontsize = 16)
        plt.xlabel('Angle from horizon', fontsize  = 16)
        # Setup grids
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(4)
        ax8.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        ax8.yaxis.grid(False, which='minor') 
        
        # Shrink current axis by 20%
        box = ax8.get_position()
        ax8.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        # Put a legend to the right of the current axis
        ax8.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        # change axis location of ax5
        pos7 = ax7.get_position()
        pos8 = ax8.get_position()
        points7 = pos7.get_points()
        points8 = pos8.get_points()
        points8[1][1]=points7[0][1]
        pos8.set_points(points8)
        ax8.set_position(pos8)
        
        #%%
        """ grad plot
        """
        
        ax30 = plt.subplot(gs1[7,:]) #not sharable with ax1 etc. as not date info
        plt.plot(ecr[:,0]/np.gradient(satalt[:,0]))
        #plt.ylabel('Amplitude?', fontsize = 16)
        #plt.xlabel('Frequency', fontsize  = 16)
        
        plt.minorticks_on()
        minorLocator = AutoMinorLocator(4)
        ax30.xaxis.set_minor_locator(minorLocator)
        plt.grid(True, which='both')
        #ax30.yaxis.grid(False, which='minor')
        
        # Shrink current axis by 20%
        box = ax30.get_position()
        ax30.set_position([box.x0, box.y0, box.width * 0.9, box.height])
        # Put a legend to the right of the current axis
        ax30.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        #%%
        #!!!
        """ Plots of Fourier Transforms
            based on:
                https://stackoverflow.com/questions/9456037/scipy-numpy-fft-frequency-analysis
        """
        N = len(ecr[:,0])
        #T = 1.0 / (4.0 * 60)  # 4 minutes in seconds
        T = 1.0 / (4.0 / 60) # 4 minutes in hours
        #T = 4 # minutes
        #T = 1.0 * 4/60 # 4 minutes in terms of hours
        
        #a = scipy.fftpack.fft(ecr[:,0])
        #b = scipy.fftpack.fft(satalt)
        #c = scipy.fftpack.fft(angle)
        
        mag_a = np.fft.rfft(ecr[:,0]/ecr[:,0].max()) #normalise values
        freq_a = np.fft.rfftfreq(N,T) # length,time diff
        
        mag_b = np.fft.rfft(satalt[:,0]/satalt[:,0].max()) #normalise values
        freq_b = np.fft.rfftfreq(N,T) # length,time diff
        
        mag_c = np.fft.rfft(angle[:,0]/angle[:,0].max()) #normalise values
        freq_c = np.fft.rfftfreq(N,T) # length,time diff
        
        #%%
        
        ax20 = plt.subplot(gs1[8,:])   # 3:   :-3
        plt.plot(freq_a, mag_a)
        plt.ylabel('Magnitude', fontsize = 16)
        plt.xlabel('Frequency (Hz)', fontsize  = 16)
        
        plt.grid(True, which='both')
        
        # Shrink current axis by 20%
        box = ax20.get_position()
        ax20.set_position([box.x0, box.y0, box.width * 0.9, box.height])
        # Put a legend to the right of the current axis
        ax20.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        #%%
        ax21 = plt.subplot(gs1[9,:])
        plt.plot(freq_b, mag_b)
        plt.ylabel('Magnitude', fontsize = 16)
        plt.xlabel('Frequency (Hz)', fontsize  = 16)
        
        plt.grid(True, which='both')
        
        # Shrink current axis by 20%
        box = ax21.get_position()
        ax21.set_position([box.x0, box.y0, box.width * 0.9, box.height])
        # Put a legend to the right of the current axis
        ax21.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        
        #%%
        ax22 = plt.subplot(gs1[10,:])
        plt.plot(freq_c, mag_c)
        plt.ylabel('Magnitude', fontsize = 16)
        plt.xlabel('Frequency (Hz)', fontsize  = 16)
        
        plt.grid(True, which='both')
        
        # Shrink current axis by 20%
        box = ax22.get_position()
        ax22.set_position([box.x0, box.y0, box.width * 0.9, box.height])
        # Put a legend to the right of the current axis
        ax22.legend(loc='center left', bbox_to_anchor=(1, 0.5), shadow=True)
        

        
        #%%
        print '###PRE-SAVE###'
        stemp = localpath + 'svn' + str(this_sat) + 'rawplot_' + str(cdstart.year) + '_' + str(cdstart.month) + '_' + str(cdstart.day) + '___' + str(cdend.year) + '_' + str(cdend.month) + '_' + str(cdend.day) + '.png'
        #plt.show()
        plt.savefig(stemp,bbox_inches="tight")
        fig.clear() #cleanup
        plt.clf() #cleanup
        plt.cla() #cleanup
        plt.close(fig) #cleanup
    
#%%
  
def smooth(y, box_pts):
    box = np.ones(box_pts)/box_pts
    y_smooth = np.convolve(y, box, mode='same')
    return y_smooth

      
def fit(this_sat, ecr, pcr, dday, year, satalt, bheight, ourmpldates, angle, sat_lon):
    """ Gaussian fit for ecr 0 
    Based upon http://cars9.uchicago.edu/software/python/lmfit/model.html"""
    # get index of minimums
    #ecr0_tpmin, ecr0_tpmax = turning_points(ecr[:,0])
    lon_tpmin, lon_tpmax = turning_points(sat_lon) # True single orbit
    
    # values between first and second sat_lon min
    tempw = [] # bheight
    tempx = [] # ecr
    tempy = [] # sat_lon
    tempz = [] # sat alt
    tempt = [] # sat dday
    tempyy = [] # year
    
    """ Get a single orbit """
    
    if len(lon_tpmin) < 2: # making sure lon_tpmin has values, else skip data point
        print 'not getting enough min lon.. ?'
        return
    
    for i in range(lon_tpmin[0],lon_tpmin[1]):
        tempw.append(bheight[i]) # Given angle is derived from bheight and sat alt.
        tempx.append(ecr[:,0][i])
        tempy.append(sat_lon[i])
        tempz.append(satalt[i])
        tempt.append(dday[i])
        tempyy.append(year[i])
    
    tempa = []
    tempb = []
    tempc = []
    tempd = []
    tempt2 = []
    tempyy2 = []
    
    tempx2 = np.copy(tempx)
    tempx2[tempx2 < 50] = 0 # remove noise from tempx
                            # It seems there are peaks at ~20. 
        
    tempx2_stpmin, tempx2_stpmax = turning_points(smooth(tempx2,20)) # Removes stuff.
    
    if not tempx2_stpmin: # making sure tempx2_stpmin has values, else skip data point
        return
    
    for i in range(0,tempx2_stpmin[0]):
        tempa.append(tempw[i]) # bheight w
        tempb.append(tempx2[i]) # ecr x
        tempc.append(tempy[i]) # lon y
        tempd.append(tempz[i]) # alt z
        tempt2.append(tempt[i]) # time t
        tempyy2.append(tempyy[i]) # year yy
        
        
    #def gaussian(x, amp, cen, wid):
    #    "1-d gaussian: gaussian(x, amp, cen, wid)"
    #    return (amp/(np.sqrt(2*np.pi)*wid)) * np.exp(-(x-cen)**2 /(2*wid**2))
    #
    #def func(x, a, x0, sigma):
    #    return a*np.exp(-(x-x0)**2/(2*sigma**2))
        
    def gaussian(x, *p):
        A, mu, sigma_squared = p
        return A*np.exp(-(x-mu)**2/(2.*sigma_squared))
        
    tempb = np.array(tempb) # As it's not a true np array...
    tempt2 = np.array(tempt2) # As it's not a true np array...
    
    """ gaussian sigma -> sigma_squared
    test sigma -> peak max min
    https://stackoverflow.com/questions/47773178/gaussian-fit-returning-negative-sigma"""    
    
    peak = tempt2[tempb > (np.exp(-0.5)*tempb.max())]
    if len(peak) < 5: # 2 is min, 5 to be safe.
        print 'not enough data in peak'
        return
    guess_sigma = 0.5*(peak.max() - peak.min())
    
    p0_vals = [max(tempb),tempt2[np.argmax(tempb)],guess_sigma**2] # ie amp = max ; cen = max position in time ; wid = optimise
    try:
        popt, pcov = curve_fit(gaussian, np.concatenate(tempt2, axis=0 ), np.asarray(tempb), p0_vals, maxfev = 6400)
    except RuntimeError:
        print("Error - curve_fit failed")
        plt.clf()
        plt.plot(tempb)
        print max(tempb)
        plt.savefig("failed.png")
        return # Report error but don't crash.
    #
#    plt.plot(np.concatenate( tempt2, axis=0 ), tempb, 'b-', label='data')
#    plt.plot(np.concatenate( tempt2, axis=0 ), gaussian(np.concatenate( tempt2, axis=0 ), *popt), 'r-',
#    label='fit: amp=%5.3f, x=%5.3f, sig_sq=%5.3f' % tuple(popt))
#    plt.legend()
#    plt.show()
#    
#    print "sigma = %s" % (np.sqrt(popt[2]))
#    
#    plt.subplot(411)
#    plt.plot(tempt2, tempc,'bo', label='sat lon')
#    plt.legend()
#    plt.subplot(412)
#    plt.plot(tempt2, tempa,'r-', label='bheight')
#    plt.legend()
#    plt.subplot(413)
#    plt.plot(tempt2, tempd,'k--', label='satalt')
#    plt.legend()
#    plt.subplot(414)
#    plt.plot(tempt2, tempb, label='ecr')
#    plt.show()
    
    gaussfile = "gaussfit" + str(this_sat) + ".txt"
    with open(gaussfile, 'a') as f:
        DAT = np.asarray([this_sat, tempyy2[np.argmax(tempb)], popt[0], popt[1], np.sqrt(popt[2])])
        #fmt='%i %i %f %f %f %f'
        np.savetxt(f, DAT[None], fmt='%i %i %f %f %f')
    
    return # end function


def main():
    truestart = datetime(2000,12,31,0,0,0) # 2001,1,7,0,0,0
    
    #start_date = datetime(2001,1,7,0,0,0);
    #end_date = datetime(2017,1,10,0,0,0);
    start_date = datetime(2009,10,4,0,0,0);
    end_date = datetime(2010,10,4,0,0,0);
    
    localpath = abspath(getsourcefile(lambda:0))[:-12]
    satlist = []
    satlist.extend([41,48])
    satlist.extend([53,54,55,56,57,58,59])
    satlist.extend([60,61,62,63,64,65,66,67,68,69])
    satlist.extend([70,71,72,73])
    #satlist = [41]
    
    maxsizeondisk = 100 # given in GB.
    
    print 'Path on disk: %s' % (localpath)
    print 'Satlist: %s' % (satlist)
    print 'Start datetime: %s end datetime: %s' % (start_date, end_date)
    print '###'
    
    #%%
    
    cdstart = truestart # Current Date we are looking at.
    while True:
        cdstart += relativedelta(days=7)
        if cdstart >= start_date:
            break
    
    #cdstart = start_date
    #cdend = end_date
    cdend = cdstart + relativedelta(days=6)
    
    #%%
    
    while True:
        
        print 'cdstart - %s' % (cdstart)
        print 'cdend - %s' % (cdend)
        
        # do stuff
        for this_sat in satlist:
            ecr, pcr, dday, year, satalt, bheight, ourmpldates, angle, sat_lon = load_data(this_sat,cdstart,cdend,localpath)
            if len(ecr) > 10:
                fit(this_sat, ecr, pcr, dday, year, satalt, bheight, ourmpldates, angle, sat_lon)
            print ' '
        # plot
        
        #cdstart += relativedelta(weeks=+52)
        cdstart += relativedelta(weeks=+4)
        cdend = cdstart + relativedelta(days=+6)
    
        if cdend.year >= end_date.year and cdend.month >= end_date.month:
            gc.collect()
            break
        
if __name__ == '__main__':
    main()
            
#truestart = datetime(2000,12,31,0,0,0) # 2001,1,7,0,0,0
#start_date = datetime(2001,1,7,0,0,0);
#end_date = datetime(2001,1,13,0,0,0);
##start_date = datetime(2002,1,7,0,0,0);
##end_date = datetime(2002,1,13,0,0,0);
#cdstart = truestart # Current Date we are looking at.
#while True:
#    cdstart += relativedelta(days=7)
#    if cdstart >= start_date:
#        break
#cdend = cdstart + relativedelta(days=6)
#localpath = abspath(getsourcefile(lambda:0))[:-12]
#
#this_sat = 41;
#
#ecr, pcr, dday, year, satalt, bheight, ourmpldates, angle, sat_lon = load_data(this_sat,cdstart,cdend,localpath)
##plot(41, ecr, pcr, dday, year, satalt, bheight, ourmpldates, angle)
##fit(ecr, pcr, dday, year, satalt, bheight, ourmpldates, angle, sat_lon)
#
#""" Gaussian fit for ecr 0 
#Based upon http://cars9.uchicago.edu/software/python/lmfit/model.html"""
## get index of minimums
##ecr0_tpmin, ecr0_tpmax = turning_points(ecr[:,0])
#lon_tpmin, lon_tpmax = turning_points(sat_lon) # True single orbit
#
#
## values between first and second sat_lon min
#tempw = [] # bheight
#tempx = [] # ecr
#tempy = [] # sat_lon
#tempz = [] # sat alt
#tempt = [] # sat time
#
#""" Get a single orbit """
#for i in range(lon_tpmin[0],lon_tpmin[1]):
#    tempw.append(bheight[i]) # Given angle is derived from bheight and sat alt.
#    tempx.append(ecr[:,0][i])
#    tempy.append(sat_lon[i])
#    tempz.append(satalt[i])
#    tempt.append(dday[i])
#
#tempa = []
#tempb = []
#tempc = []
#tempd = []
#tempt2 = []
#
#tempx2 = np.copy(tempx)
#tempx2[tempx2 < 10] = 0 # remove noise from tempx
#    
#tempx2_stpmin, tempx2_stpmax = turning_points(smooth(tempx2,20)) # Removes stuff.
#
#
#
#for i in range(0,tempx2_stpmin[0]):
#    tempa.append(tempw[i]) # bheight w
#    tempb.append(tempx2[i]) # ecr x
#    tempc.append(tempy[i]) # lon y
#    tempd.append(tempz[i]) # alt z
#    tempt2.append(tempt[i]) # time t
#    
#    
##def gaussian(x, amp, cen, wid):
##    "1-d gaussian: gaussian(x, amp, cen, wid)"
##    return (amp/(np.sqrt(2*np.pi)*wid)) * np.exp(-(x-cen)**2 /(2*wid**2))
##
##def func(x, a, x0, sigma):
##    return a*np.exp(-(x-x0)**2/(2*sigma**2))
#    
#def gaussian(x, *p):
#    A, mu, sigma_squared = p
#    return A*np.exp(-(x-mu)**2/(2.*sigma_squared))
#    
#tempb = np.array(tempb) # As it's not a true np array...
#tempt2 = np.array(tempt2) # As it's not a true np array...
#
#""" gaussian sigma -> sigma_squared
#test sigma -> peak max min
#https://stackoverflow.com/questions/47773178/gaussian-fit-returning-negative-sigma"""    
#
#peak = tempt2[tempb > (np.exp(-0.5)*tempb.max())]
#guess_sigma = 0.5*(peak.max() - peak.min())
#
#p0_vals = [max(tempb),tempt2[np.argmax(tempb)],guess_sigma**2] # ie amp = max ; cen = max position in time ; wid = optimise
#popt, pcov = curve_fit(gaussian, np.concatenate(tempt2, axis=0 ), np.asarray(tempb), p0_vals, maxfev = 3200)
##
#plt.plot(np.concatenate( tempt2, axis=0 ), tempb, 'b-', label='data')
#plt.plot(np.concatenate( tempt2, axis=0 ), gaussian(np.concatenate( tempt2, axis=0 ), *popt), 'r-',
#label='fit: amp=%5.3f, x=%5.3f, sig_sq=%5.3f' % tuple(popt))
#plt.legend()
#plt.show()
#
#print "sigma = %s" % (np.sqrt(popt[2]))
#
#plt.subplot(411)
#plt.plot(tempt2, tempc,'bo', label='sat lon')
#plt.legend()
#plt.subplot(412)
#plt.plot(tempt2, tempa,'r-', label='bheight')
#plt.legend()
#plt.subplot(413)
#plt.plot(tempt2, tempd,'k--', label='satalt')
#plt.legend()
#plt.subplot(414)
#plt.plot(tempt2, tempb, label='ecr')
#plt.show()
#
#with open("gaussfit.txt", 'a') as f:
#    DAT = np.asarray([this_sat, year[np.argmax(tempb)], dday[np.argmax(tempb)], popt[0], popt[1], np.sqrt(popt[2])])
#    np.savetxt(f, DAT[None], delimiter=' ')
#
#
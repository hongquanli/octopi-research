import os
import cv2
import time
import imageio
from control.model_utils import *
import matplotlib.pyplot as plt

settings = {}
settings['spot_detection_downsize_factor'] = 4
settings['spot_detection_threshold'] = 10

# regions to process + other settings
parameters = {}
parameters['crop_x0'] = 100
parameters['crop_x1'] = 2900
parameters['crop_y0'] = 100
parameters['crop_y1'] = 2900

def process_fov(I_fluorescence,I_BF_left,I_BF_right,model,model2,device,classification_th):

    # crop image
    I_fluorescence = I_fluorescence[ parameters['crop_y0']:parameters['crop_y1'], parameters['crop_x0']:parameters['crop_x1'], : ]
    I_BF_left = I_BF_left[ parameters['crop_y0']:parameters['crop_y1'], parameters['crop_x0']:parameters['crop_x1']]
    I_BF_right = I_BF_right[ parameters['crop_y0']:parameters['crop_y1'], parameters['crop_x0']:parameters['crop_x1']]

    # remove background
    I_fluorescence_bg_removed = remove_background(I_fluorescence,return_gpu_image=True)

    # detect spots
    spot_list = detect_spots(resize_image_cp(I_fluorescence_bg_removed,downsize_factor=settings['spot_detection_downsize_factor']),thresh=settings['spot_detection_threshold'])
    if(len(spot_list)==0):
        print('no spots!')
        return None, None
    spot_list = prune_blobs(spot_list)

    # scale coordinates for full-res image
    spot_list = spot_list*settings['spot_detection_downsize_factor']

    # generate spot arrays
    I_BF_left = I_BF_left.astype('float')/255
    I_BF_right = I_BF_right.astype('float')/255
    I_DPC = generate_dpc(I_BF_left,I_BF_right)
    I_fluorescence = I_fluorescence.astype('float')/255
    I = get_spot_images_from_fov(I_fluorescence,I_DPC,spot_list,r=15)
    I = I.transpose(0, 3, 1, 2)

    # classify
    print("running models")
    prediction_score = run_model(model,device,I)[:,1]
    indices = np.where(prediction_score > classification_th)[0]

    if TWO_CLASSIFICATION_MODELS and model2 is not None:
        prediction_score2 = run_model(model2,device,I)[:,1]
        indices2 = np.where(prediction_score2 > classification_th)[0]

        if len(indices2) < len(indices):
            indices = indices2
            print("choosing classification model 2")
        else:
            print("choosing classification model 1")

    # return positive spots
    return I[indices],prediction_score[indices]


import imageio
import cv2
import cupy as cp # conda install -c conda-forge cupy==10.2 or conda install -c conda-forge cupy cudatoolkit=11.0
import cupyx.scipy.ndimage
# from cupyx.scipy import ndimage # for 11.0
# from ndimage import laplace # for 11.0
from cupyx.scipy.ndimage import laplace # for 11.0
# from cupyx.scipy.ndimage.filters import laplace # for 10.2
from skimage.feature.blob import _prune_blobs
import numpy as np
from scipy import signal
import pandas as pd

def imread_gcsfs(fs,file_path):
    img_bytes = fs.cat(file_path)
    I = imageio.core.asarray(imageio.imread(img_bytes, "bmp"))
    return I

def resize_cp(ar,downsize_factor=4):
    # by Rinni
    s_ar = cp.zeros((int(ar.shape[0]/downsize_factor), int(ar.shape[0]/downsize_factor), 3))
    s_ar[:,:,0] = ar[:,:,0].reshape([int(ar.shape[0]/downsize_factor), int(downsize_factor), int(ar.shape[1]/downsize_factor), int(downsize_factor)]).mean(3).mean(1)
    s_ar[:,:,1] = ar[:,:,1].reshape([int(ar.shape[0]/downsize_factor), int(downsize_factor), int(ar.shape[1]/downsize_factor), int(downsize_factor)]).mean(3).mean(1)
    s_ar[:,:,2] = ar[:,:,2].reshape([int(ar.shape[0]/downsize_factor), int(downsize_factor), int(ar.shape[1]/downsize_factor), int(downsize_factor)]).mean(3).mean(1)
    return s_ar

def resize_image_cp(I,downsize_factor=4):
    I = I.astype('float')
    I_resized = cp.copy(I)
    I_resized = resize_cp(I_resized, downsize_factor)
    return(I_resized)

def remove_background(img_cpu, return_gpu_image=True):
    tophat = cv2.getStructuringElement(2, ksize=(17,17))
    tophat_gpu = cp.asarray(tophat)
    img_g_gpu = cp.asarray(img_cpu)
    img_th_gpu = img_g_gpu
    for k in range(3):
        img_th_gpu[:,:,k] = cupyx.scipy.ndimage.white_tophat(img_g_gpu[:,:,k], footprint=tophat_gpu)
    if return_gpu_image:
        return img_th_gpu
    else:
        return cp.asnumpy(img_th_gpu)

def gaussian_kernel_1d(n, std, normalized=True):
    if normalized:
        return cp.asarray(signal.gaussian(n, std))/(np.sqrt(2 * np.pi)*std)
    return cp.asarray(signal.gaussian(n, std))

def detect_spots(I, thresh = 12):
    # filters
    gauss_rs = np.array([4,6,8,10])
    gauss_sigmas = np.array([1,1.5,2,2.5])
    gauss_ts = np.divide(gauss_rs - 0.5,gauss_sigmas) # truncate value (to get desired radius)
    lapl_kernel = cp.array([[0,1,0],[1,-4,1],[0,1,0]])
    gauss_filters_1d = []
    for i in range(gauss_rs.shape[0]):
        gauss_filt_1d = gaussian_kernel_1d(gauss_rs[i]*2+1,gauss_sigmas[i],True)
        gauss_filt_1d = gauss_filt_1d.reshape(-1, 1)
        gauss_filters_1d.append(gauss_filt_1d)
    # apply all filters
    if len(I.shape) == 3:
        I = cp.average(I, axis=2, weights=cp.array([0.299,0.587,0.114]))
    filtered_imgs = []
    for i in range(len(gauss_filters_1d)): # apply LoG filters
        filt_img = cupyx.scipy.ndimage.convolve(I, gauss_filters_1d[i])
        filt_img = cupyx.scipy.ndimage.convolve(filt_img, gauss_filters_1d[i].transpose())
        filt_img = cupyx.scipy.ndimage.convolve(filt_img, lapl_kernel)
        filt_img *= -(gauss_sigmas[i]**2)
        filtered_imgs.append(filt_img)
    img_max_proj = cp.max(np.stack(filtered_imgs), axis=0)
    # return img_max_proj
    img_max_filt = cupyx.scipy.ndimage.maximum_filter(img_max_proj, size=3)
    # set pixels < thresh (12) to 0 (so they wont be in img_traceback)
    img_max_filt[img_max_filt < thresh] = 0 # check if uint8
    # origination masks
    img_traceback = cp.zeros(img_max_filt.shape)
    for i in range(len(filtered_imgs)): # trace back pixels to each filtered image
        img_traceback[img_max_filt == filtered_imgs[i]] = i+1
        img_traceback[img_max_filt == 0] = 0 # but make sure all pixels that were 0 are still 0
    ind = np.where(img_traceback != 0)
    spots = np.zeros((ind[0].shape[0],3)) # num spots x 3
    for i in range(ind[0].shape[0]):
        spots[i][0] = int(ind[1][i])
        spots[i][1] = int(ind[0][i])
        spots[i][2] = int(img_traceback[spots[i][1]][spots[i][0]])
    spots = spots.astype(int)
    return spots

# filter spots to avoid overlapping ones
def prune_blobs(spots_list):
    overlap = .5
    num_sigma = 4
    min_sigma = 1
    max_sigma = 2.5
    scale = np.linspace(0, 1, num_sigma)[:, np.newaxis]
    sigma_list = scale * (max_sigma - min_sigma) + min_sigma
    # translate final column of lm, which contains the index of the
    # sigma that produced the maximum intensity value, into the sigma
    sigmas_of_peaks = sigma_list[spots_list[:, -1]-1]
    # select one sigma column, keeping dimension
    sigmas_of_peaks = sigmas_of_peaks[:, 0:1]
    # Remove sigma index and replace with sigmas
    spots_list = np.hstack([spots_list[:,:-1], sigmas_of_peaks])
    result_pruned = _prune_blobs(spots_list, overlap)
    return result_pruned

def highlight_spots(I,spot_list,contrast_boost=1.6):
    # bgremoved_fluorescence_spotBoxed = np.copy(bgremoved_fluorescence)
    I = I.astype('float')/255 # this copies the image
    I = I*contrast_boost # enhance contrast
    for s in spot_list:
        add_bounding_box(I,int(s[0]),int(s[1]),int(s[2]))
    return I

def add_bounding_box(I,x,y,r,extension=2,color=[0.6,0.6,0]):
    ny, nx, nc = I.shape
    x_min = max(x - r - extension,0)
    y_min = max(y - r - extension,0)
    x_max = min(x + r + extension,nx-1)
    y_max = min(y + r + extension,ny-1)
    for i in range(3):
        I[y_min,x_min:x_max+1,i] = color[i]
        I[y_max,x_min:x_max+1,i] = color[i]
        I[y_min:y_max+1,x_min,i] = color[i]
        I[y_min:y_max+1,x_max,i] = color[i]

def remove_spots_in_masked_regions(spotList,mask):
    mask = mask.astype('float')/255
    mask = np.sum(mask,axis=-1) # masked out region has pixel value 0 ;# mask[mask>0] = 1 #         cv2.imshow('mask',mask) # cv2.waitKey(0)
    for s in spotList:
        x = s[0]
        y = s[1]
        if mask[int(y),int(x)] == 0:
            s[-1] = 0
    spot_list = np.array([s for s in spotList if s[-1] > 0])
    return spot_list

def extract_spot_data(I_background_removed,I_raw,spot_list,i,j,k,settings,extension=1):
    downsize_factor=settings['spot_detection_downsize_factor']
    extension = extension*downsize_factor
    ny, nx, nc = I_background_removed.shape
    I_background_removed = I_background_removed.astype('float')
    I_raw = I_raw/255
    columns = ['FOV_row','FOV_col','FOV_z','x','y','r','R','G','B','R_max','G_max','B_max','lap_total','lap_max','numPixels','numSaturatedPixels','idx']
    spot_data_pd = pd.DataFrame(columns=columns)
    idx = 0
    for s in spot_list:
        # get spot
        x = int(s[0])
        y = int(s[1])
        r = s[2]
        x_min = max(int((x - r - extension)),0)
        y_min = max(int((y - r - extension)),0)
        x_max = min(int((x + r + extension)),nx-1)
        y_max = min(int((y + r + extension)),ny-1)
        cropped = I_background_removed[y_min:(y_max+1),x_min:(x_max+1),:]
        cropped_raw = I_raw[y_min:(y_max+1),x_min:(x_max+1),:]
        # extract spot data
        B = cp.asnumpy(cp.sum(cropped[:,:,2]))
        G = cp.asnumpy(cp.sum(cropped[:,:,1]))
        R = cp.asnumpy(cp.sum(cropped[:,:,0]))
        B_max = cp.asnumpy(cp.max(cropped[:,:,2]))
        G_max = cp.asnumpy(cp.max(cropped[:,:,1]))
        R_max = cp.asnumpy(cp.max(cropped[:,:,0]))
        lap = laplace(cp.sum(cropped,2))
        lap_total = cp.asnumpy(cp.sum(cp.abs(lap)))
        lap_max = cp.asnumpy(cp.max(cp.abs(lap)))
        numPixels = cropped[:,:,0].size
        numSaturatedPixels = cp.asnumpy(cp.sum(cropped_raw == 1))
        # add spot entry
        spot_entry = pd.DataFrame.from_dict({'FOV_row':[i],'FOV_col':[j],'FOV_z':[k],'x':[x],'y':[y],'r':[r],'R':[R],'G':[G],'B':[B],'R_max':[R_max],'G_max':[G_max],'B_max':[B_max],'lap_total':[lap_total],'lap_max':[lap_max],'numPixels':[numPixels],'numSaturatedPixels':[numSaturatedPixels],'idx':[idx]})
        # spot_data_pd = spot_data_pd.append(spot_entry, ignore_index=True, sort=False)
        spot_data_pd = pd.concat([spot_data_pd,spot_entry])
        # increament idx
        idx = idx + 1
    return spot_data_pd

def process_spots(I_background_removed,I_raw,spot_list,i,j,k,settings,I_mask=None):
    # get rid of spots in masked out regions
    if I_mask!=None:
        spot_list = remove_spots_in_masked_regions(spot_list,I_mask)
    # extract spot statistics
    spot_data_pd = extract_spot_data(I_background_removed,I_raw,spot_list,i,j,k,settings)
    return spot_list, spot_data_pd

def generate_dpc(I1,I2,use_gpu=False):
    if use_gpu:
        # img_dpc = cp.divide(img_left_gpu - img_right_gpu, img_left_gpu + img_right_gpu)
        # to add
        I_dpc = 0
    else:
        I_dpc = np.divide(I1-I2,I1+I2)
        I_dpc = I_dpc + 0.5
    I_dpc[I_dpc<0] = 0
    I_dpc[I_dpc>1] = 1
    return I_dpc

def get_spot_images_from_fov(I_fluorescence,I_dpc,spot_list,r=15):
    
    if(len(I_dpc.shape)==3):
        # I_dpc_RGB = I_dpc
        I_dpc = I_dpc[:,:,1]
    else:
        # I_dpc_RGB = np.dstack((I_dpc,I_dpc,I_dpc))
        pass
    # get the full image size
    height,width,channels = I_fluorescence.shape
    # go through spot
    counter = 0
    
    # for idx, entry in spot_data.iterrows():
    #   # get coordinate
    #   x = int(entry['x'])
    #   y = int(entry['y'])
    for s in spot_list:
        x = int(s[0])
        y = int(s[1])
        # create the arrays for cropped images
        I_DPC_cropped = np.zeros((2*r+1,2*r+1), float)
        I_fluorescence_cropped = np.zeros((2*r+1,2*r+1,3), float)
        # I_overlay_cropped = np.zeros((2*r+1,2*r+1,3), np.float)
        # identify cropping region in the full FOV 
        x_start = max(0,x-r)
        x_end = min(x+r,width-1)
        y_start = max(0,y-r)
        y_end = min(y+r,height-1)
        x_idx_FOV = slice(x_start,x_end+1)
        y_idx_FOV = slice(y_start,y_end+1)
        # identify cropping region in the cropped images
        x_cropped_start = x_start - (x-r)
        x_cropped_end = (2*r+1-1) - ((x+r)-x_end)
        y_cropped_start = y_start - (y-r)
        y_cropped_end = (2*r+1-1) - ((y+r)-y_end)
        x_idx_cropped = slice(x_cropped_start,x_cropped_end+1)
        y_idx_cropped = slice(y_cropped_start,y_cropped_end+1)
        # do the cropping 
        I_DPC_cropped[y_idx_cropped,x_idx_cropped] = I_dpc[y_idx_FOV,x_idx_FOV]
        I_fluorescence_cropped[y_idx_cropped,x_idx_cropped,:] = I_fluorescence[y_idx_FOV,x_idx_FOV,:]
        
        # combine
        if counter == 0:
            I = np.dstack((I_fluorescence_cropped,I_DPC_cropped))[np.newaxis,:]
        else:
            I = np.concatenate((I,np.dstack((I_fluorescence_cropped,I_DPC_cropped))[np.newaxis,:]))
        counter = counter + 1

    if counter == 0:
        print('no spot in this FOV')
        return None
    else:
        return I

import imageio
import numpy as np
import cv2

def numpy2png(img,filename,resize_factor=5):
    img = img.transpose(1,2,0)
    img_fluorescence = img[:,:,[2,1,0]]
    img_dpc = img[:,:,3]
    img_dpc = np.dstack([img_dpc,img_dpc,img_dpc])
    img_overlay = 0.64*img_fluorescence + 0.36*img_dpc
    x = resize_factor
    img_overlay = cv2.resize(img_overlay, (int(img_overlay.shape[1]*x), int(img_overlay.shape[0]*x)), interpolation=cv2.INTER_NEAREST)
    # imageio.imwrite(filename + "_fluorescence.png", np.uint8(img_fluorescence))
    imageio.imwrite(filename + "_overlay.png", np.uint8(img_overlay))
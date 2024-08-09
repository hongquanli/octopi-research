import cv2
from numpy import std, square, mean
import numpy as np
from scipy.ndimage import label
import os

def crop_image(image,crop_width,crop_height):
    image_height = image.shape[0]
    image_width = image.shape[1]
    roi_left = int(max(image_width/2 - crop_width/2,0))
    roi_right = int(min(image_width/2 + crop_width/2,image_width))
    roi_top = int(max(image_height/2 - crop_height/2,0))
    roi_bottom = int(min(image_height/2 + crop_height/2,image_height))
    image_cropped = image[roi_top:roi_bottom,roi_left:roi_right]
    return image_cropped

def calculate_focus_measure(image,method='LAPE'):
    if len(image.shape) == 3:
        image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY) # optional
    if method == 'LAPE':
        if image.dtype == np.uint16:
            lap = cv2.Laplacian(image,cv2.CV_32F)
        else:
            lap = cv2.Laplacian(image,cv2.CV_16S)
        focus_measure = mean(square(lap))
    elif method == 'GLVA':
        focus_measure = np.std(image,axis=None)# GLVA
    else:
        focus_measure = np.std(image,axis=None)# GLVA
    return focus_measure

def unsigned_to_signed(unsigned_array,N):
    signed = 0
    for i in range(N):
        signed = signed + int(unsigned_array[i])*(256**(N-1-i))
    signed = signed - (256**N)/2
    return signed

def rotate_and_flip_image(image,rotate_image_angle,flip_image):
    ret_image = image.copy()
    if(rotate_image_angle != 0):
        '''
            # ROTATE_90_CLOCKWISE
            # ROTATE_90_COUNTERCLOCKWISE
        '''
        if(rotate_image_angle == 90):
            ret_image = cv2.rotate(ret_image,cv2.ROTATE_90_CLOCKWISE)
        elif(rotate_image_angle == -90):
            ret_image = cv2.rotate(ret_image,cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif(rotate_image_angle == 180):
            ret_image = cv2.rotate(ret_image,cv2.ROTATE_180)

    if(flip_image is not None):
        '''
            flipcode = 0: flip vertically
            flipcode > 0: flip horizontally
            flipcode < 0: flip vertically and horizontally
        '''
        if(flip_image == 'Vertical'):
            ret_image = cv2.flip(ret_image, 0)
        elif(flip_image == 'Horizontal'):
            ret_image = cv2.flip(ret_image, 1)
        elif(flip_image == 'Both'):
            ret_image = cv2.flip(ret_image, -1)

    return ret_image

def generate_dpc(im_left, im_right):
    # Normalize the images
    im_left = im_left.astype(float)/255
    im_right = im_right.astype(float)/255
    # differential phase contrast calculation
    im_dpc = 0.5 + np.divide(im_left-im_right, im_left+im_right)
    # take care of errors
    im_dpc[im_dpc < 0] = 0
    im_dpc[im_dpc > 1] = 1
    im_dpc[np.isnan(im_dpc)] = 0

    im_dpc = (im_dpc * 255).astype(np.uint8)

    return im_dpc

def colorize_mask(mask):
    # Label the detected objects
    labeled_mask, ___ = label(mask)
    # Color them
    colored_mask = np.array((labeled_mask * 83) % 255, dtype=np.uint8)
    colored_mask = cv2.applyColorMap(colored_mask, cv2.COLORMAP_HSV)
    # make sure background is black
    colored_mask[labeled_mask == 0] = 0
    return colored_mask

def colorize_mask_get_counts(mask):
    # Label the detected objects
    labeled_mask, no_cells = label(mask)
    # Color them
    colored_mask = np.array((labeled_mask * 83) % 255, dtype=np.uint8)
    colored_mask = cv2.applyColorMap(colored_mask, cv2.COLORMAP_HSV)
    # make sure background is black
    colored_mask[labeled_mask == 0] = 0
    return colored_mask, no_cells

def overlay_mask_dpc(color_mask, im_dpc):
    # Overlay the colored mask and DPC image
    # make DPC 3-channel
    im_dpc = np.stack([im_dpc]*3, axis=2)
    return (0.75*im_dpc + 0.25*color_mask).astype(np.uint8)
    
def centerCrop(image, crop_sz):
    center = image.shape
    x = int(center[1]/2 - crop_sz/2)
    y = int(center[0]/2 - crop_sz/2)
    cropped = image[y:y+crop_sz, x:x+crop_sz]
    
    return cropped

def interpolate_plane(triple1, triple2, triple3, point):
    """
    Given 3 triples triple1-3 of coordinates (x,y,z)
    and a pair of coordinates (x,y), linearly interpolates
    the z-value at (x,y).
    """
    # Unpack points
    x1, y1, z1 = triple1
    x2, y2, z2 = triple2
    x3, y3, z3 = triple3

    x,y = point
    # Calculate barycentric coordinates
    detT = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if detT == 0:
        raise ValueError("Your 3 x-y coordinates are linear")
    alpha = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / detT
    beta = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / detT
    gamma = 1 - alpha - beta

    # Interpolate z-coordinate
    z = alpha * z1 + beta * z2 + gamma * z3

    return z

def create_done_file(path):
    with open(os.path.join(path,'.done'), 'w') as file:
        pass  # This creates an empty file

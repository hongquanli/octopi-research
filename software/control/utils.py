import cv2
from numpy import std, square, mean
import numpy as np

from typing import Optional, Union
from control._def import FocusMeasureOperators
from control.typechecker import TypecheckFunction

ImageType=Union[cv2.Mat,np.ndarray]

@TypecheckFunction
def crop_image(image:ImageType,crop_width:int,crop_height:int)->ImageType:
    image_height = image.shape[0]
    image_width = image.shape[1]
    roi_left = int(max(image_width/2 - crop_width/2,0))
    roi_right = int(min(image_width/2 + crop_width/2,image_width))
    roi_top = int(max(image_height/2 - crop_height/2,0))
    roi_bottom = int(min(image_height/2 + crop_height/2,image_height))
    image_cropped = image[roi_top:roi_bottom,roi_left:roi_right]
    return image_cropped

@TypecheckFunction
def calculate_focus_measure(image:ImageType,method:FocusMeasureOperators=FocusMeasureOperators.LAPE) -> float:
    if len(image.shape) == 3:
        image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY) # optional

    if method == FocusMeasureOperators.LAPE:
        if image.dtype == np.uint16:
            lap = cv2.Laplacian(image,cv2.CV_32F)
        else:
            lap = cv2.Laplacian(image,cv2.CV_16S)

        focus_measure:float = mean(square(lap)) # type: ignore

    elif method == FocusMeasureOperators.GLVA:
        focus_measure:float = np.std(image, axis=None) #type: ignore

    else:
        assert False, f"{method} is an invalid focus measure method"

    return focus_measure

@TypecheckFunction
def rotate_and_flip_image(image:ImageType,rotate_image_angle:int,flip_image:Optional[str]) -> ImageType:
    if(rotate_image_angle != 0):
        try:
            rotation_flag={
                -90:cv2.ROTATE_90_COUNTERCLOCKWISE,
                90:cv2.ROTATE_90_CLOCKWISE,
                180:cv2.ROTATE_180
            }[rotate_image_angle]
            image = cv2.rotate(image,rotation_flag)
        except:
            assert False, "invalid rotation angle (is not 0|90|-90|180)"

    if(flip_image is not None):
        '''
            flipcode = 0: flip vertically
            flipcode > 0: flip horizontally
            flipcode < 0: flip vertically and horizontally
        '''
        if(flip_image == 'Vertical'):
            image = cv2.flip(image, 0)
        elif(flip_image == 'Horizontal'):
            image = cv2.flip(image, 1)
        elif(flip_image == 'Both'):
            image = cv2.flip(image, -1)
        else:
            assert False, "invalid image flipping mode"

    return image

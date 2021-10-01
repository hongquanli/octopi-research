import cv2
from numpy import std, square, mean

def crop_image(image,crop_width,crop_height):
    image_height = image.shape[0]
    image_width = image.shape[1]
    roi_left = int(max(image_width/2 - crop_width/2,0))
    roi_right = int(min(image_width/2 + crop_width/2,image_width))
    roi_top = int(max(image_height/2 - crop_height/2,0))
    roi_bottom = int(min(image_height/2 + crop_height/2,image_height))
    image_cropped = image[roi_top:roi_bottom,roi_left:roi_right]
    return image_cropped

def calculate_focus_measure(image):
	if len(image.shape) == 3:
		image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY) # optional
	lap = cv2.Laplacian(image,cv2.CV_16S)
	focus_measure = mean(square(lap))
	return focus_measure

def unsigned_to_signed(unsigned_array,N):
    signed = 0
    for i in range(N):
        signed = signed + int(unsigned_array[i])*(256**(N-1-i))
    signed = signed - (256**N)/2
    return signed

def rotate_and_flip_image(image,rotate_image_angle,flip_image):
    if(rotate_image_angle != 0):
        '''
            # ROTATE_90_CLOCKWISE
            # ROTATE_90_COUNTERCLOCKWISE
        '''
        if(rotate_image_angle == 90):
            image = cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE)
        elif(rotate_image_angle == -90):
            image = cv2.rotate(image,cv2.ROTATE_90_COUNTERCLOCKWISE)

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

    return image
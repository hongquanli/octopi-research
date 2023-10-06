import matplotlib.image as mpimg
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib_scalebar.scalebar import ScaleBar

targets = ["4_14_0"]
path = "/home/octopi-codex/Desktop/Data/_2023-06-18_18-31-13.883489/0"
crop_sz = 3000
scale = 0.33e-6

images = ["_BF_LED_matrix_left_half", "_BF_LED_matrix_right_half", "_DPC", "_overlay"]

for target in targets:
    for im in images:
        image = mpimg.imread(os.path.join(path, target + im + ".bmp"))
        center = image.shape
        x = int(center[1]/2 - crop_sz/2)
        y = int(center[0]/2 - crop_sz/2)
        if len(center) > 2:
            image = image[y:y+crop_sz, x:x+crop_sz, :]
        else:
            image = image[y:y+crop_sz, x:x+crop_sz]
            image = np.stack([image]*3, axis=2)
        print(image.shape)
        plt.imshow(image)
        scalebar = ScaleBar(scale)
        plt.gca().add_artist(scalebar)
        plt.axis('off')
        plt.savefig(os.path.join(path, "scalebar_" + target + im + ".png"), bbox_inches='tight', dpi = 700, pad_inches = 0)

import numpy as np
import pandas as pd
import control.models as models
import torch
from torch.utils.data import DataLoader, TensorDataset
import torch.nn as nn
from torch.optim import Adam
import copy
import time
import sys

# runs model
def run_model(model, device, images, batch_size_inference=1024):

    return generate_predictions(model,device,images,batch_size_inference)

def generate_predictions(model, device, images, batch_size_inference=1024):

    if images.dtype == np.uint8:
        images = images.astype(np.float32)/255.0 # convert to 0-1 if uint8 input

    # build dataset
    dataset = TensorDataset(torch.from_numpy(images), torch.from_numpy(np.ones(images.shape[0])))

    # dataloader
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size_inference, shuffle=False)

    # run inference 
    all_predictions = []
    t0 = time.time()
    for k, (images, labels) in enumerate(dataloader):
        images = images.float().to(device)
        predictions, features = model.get_predictions_and_features(images)
        predictions = predictions.detach().cpu().numpy()
        all_predictions.append(predictions)
        del images
        del labels
        torch.cuda.empty_cache()  # Clear GPU memory
        
    del dataset
    del dataloader
    predictions = np.vstack(all_predictions)
    print('running inference on ' + str(predictions.shape[0]) + ' images took ' + str(time.time()-t0) + ' s')

    return predictions

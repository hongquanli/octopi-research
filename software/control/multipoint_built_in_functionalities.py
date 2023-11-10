from control.processing_handler import default_upload_fn, process_fn_with_count_and_display
from control.processing_pipeline import process_fov
import imageio
import numpy as np

### NOTE: This requires a DataHandler to instantiated and accessible at
### multiPointWorker.microscope.dataHandler, as well as
### multiPointWorker.microscope.model, multiPointWorker.microscope.device,
### and multiPointWorker.classification_th

def malaria_rtp(I_fluorescence, I_left, I_right, multiPointWorker,classification_test_mode=False,sort_during_multipoint=True,disp_th_during_multipoint=0.95):
            # real time processing 
    if classification_test_mode: # testing mode
        I_fluorescence = imageio.v2.imread('images/rtp_test_data/1_1_0_Fluorescence_405_nm_Ex.bmp')
        I_fluorescence = I_fluorescence[:,:,::-1]
        I_left = imageio.v2.imread('images/rtp_test_data/1_1_0_BF_LED_matrix_left_half.bmp')
        I_right = imageio.v2.imread('images/rtp_test_data/1_1_0_BF_LED_matrix_right_half.bmp')
    processing_fn = process_fn_with_count_and_display
    processing_args = [process_fov, np.copy(I_fluorescence),np.copy(I_left), np.copy(I_right), multiPointWorker.microscope.model, multiPointWorker.microscope.device, multiPointWorker.microscope.classification_th]
    processing_kwargs = {'upload_fn':default_upload_fn, 'dataHandler':multiPointWorker.microscope.dataHandler, 'multiPointWorker':multiPointWorker,'sort':sort_during_multipoint,'disp_th':disp_th_during_multipoint}
    task_dict = {'function':processing_fn, 'args':processing_args, 'kwargs':processing_kwargs}
    multiPointWorker.processingHandler.processing_queue.put(task_dict)

## Setting up the environments

### install software dependencies
```
sudo rm /var/lib/apt/lists/lock
sudo apt-get update
sudo apt-get install python3-pip
sudo apt-get install python3-pyqtgraph
sudo apt-get install python3-pyqt5
pip3 install qtpy pyserial pandas
```
If opencv and lxml not preinstalled (e.g. if you're not using a Jetson but a regular computer), run the following
```
pip3 install --upgrade setuptools pip
pip3 install opencv-python opencv-contrib-python
pip3 install lxml
```

### install camera drivers
If you're using The Imaging Source cameras, follow instructions on https://github.com/TheImagingSource/tiscamera 

If you're using Daheng cameras, follow instructions in the `drivers and libraries/daheng camera` folder

### enable access to serial ports without sudo

```
sudo usermod -aG dialout $USER
```
 
### (optional) install pytorch and torchvision on Jetson Nano
Follow instructions on https://forums.developer.nvidia.com/t/pytorch-for-jetson-nano-version-1-5-0-now-available/72048

```
sudo apt-get install libhdf5-serial-dev hdf5-tools libhdf5-dev zlib1g-dev zip libjpeg8-dev liblapack-dev libblas-dev gfortran
sudo apt-get install python3-pip libopenblas-base libopenmpi-dev 
pip3 install -U pip testresources setuptools
pip3 install Cython
wget https://nvidia.box.com/shared/static/3ibazbiwtkl181n95n9em3wtrca7tdzp.whl -o torch-1.5.0-cp36-cp36m-linux_aarch64.whl
pip3 install torch-1.5.0-cp36-cp36m-linux_aarch64.whl
```
```
sudo apt-get install libjpeg-dev zlib1g-dev
git clone --branch torchvision v0.6.0 https://github.com/pytorch/vision torchvision   # see below for version of torchvision to download
cd torchvision
sudo python3 setup.py install
```
## Configuring the software
Create a `configuration.txt` file in the software folder to set up variables for a specific machine. The file is loaded by [`control/_def.py`](https://github.com/hongquanli/octopi-research/blob/master/software/control/_def.py) There should be only one `configuration*.txt` file in the software folder. You may edit the [`configuration_example.txt` file](https://github.com/hongquanli/octopi-research/blob/master/software/configuration_example.txt) and rename it.

The following aspects are specified in the configuration file:
- stage movement signs (what is forward vs backward) (e.g. `STAGE_MOVEMENT_SIGN_X`)
- stage motor and lead screw specs (in particular screw pitch, e.g. `SCREW_PITCH_X_MM`)
- whether encoders are used and encoder-related settings (e.g. `USE_ENCODER_X`)
- whether homing is enabled for a particular axis (e.g. `HOMING_ENABLED_X`)
- whether tracking is enabled (`ENABLE_TRACKING`)
- plate reader related definations (`class PLATE_READER`)

## Using the software
Use one of the following to start the program
```
python3 main.py
python3 main_camera_only.py
python3 main_motion_only.py
```
To start the program when no hardware is connected, use
```
python3 main_simulation.py
```

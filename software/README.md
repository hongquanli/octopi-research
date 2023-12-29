## Setting up the environments

### install software dependencies
```
sudo rm /var/lib/apt/lists/lock
sudo apt-get update
sudo apt-get install python3-pip
sudo apt-get install python3-pyqtgraph
sudo apt-get install python3-pyqt5
sudo apt-get install git
git clone https://github.com/hongquanli/octopi-research.git
pip3 install qtpy pyserial pandas imageio pyqt5-tools pyqtgraph scipy tensorrt crc==1.3.0
python3 -m pip install --upgrade --user setuptools==58.3.0
pip3 install opencv-python opencv-contrib-python
pip3 install lxml
pip3 install numpy
```

#### image stitching dependencies (optional)
For optional image stitching using ImageJ, additionally run the following:
```
sudo apt-get update
sudo apt-get install openjdk-11-jdk
sudo apt-get install maven
pip3 install pyimagej
pip3 instlal scyjava
pip3 install tifffile
pip3 install imagecodecs
```

Then, add the following line to the top of `/etc/environment` (needs to be edited with `sudo [your text editor]`):
```
JAVA_HOME=/usr/lib/jvm/default-java
```
Then, add the following lines to the top of `~/.bashrc` (or whichever file your terminal sources upon startup):
```
source /etc/environment
export JAVA_HOME = $JAVA_HOME
export PATH=$JAVA_HOME/bin:$PATH
```

### install camera drivers
If you're using Daheng cameras, follow instructions in the `drivers and libraries/daheng camera` folder

If you're using The Imaging Source cameras, follow instructions on https://github.com/TheImagingSource/tiscamera 

### enable access to serial ports without sudo

```
sudo usermod -aG dialout $USER
```
Reboot the computer for the setting to take effect.

<details>
<summary>Jetson Nano Instructions (last modified: July 2020)</summary>

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
</details>
<details>
<summary>Modify udev permissions for toupcam to work</summary>
If using a compatible Toupcam camera on Linux, copy the file `software/drivers and libraries/toupcam/linux/udev/99-toupcam.rules` to `/etc/udev/rules.d`
(via `sudo cp`) before connecting the camera.
</details>

<details>
<summary>Install CuPy (optional)</summary>

From March 2023 w/ RTX3050
```
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda

pip3 install cupy-cuda12x
pip3 install cuda-python
```
For latest instructions, refer to 
https://developer.nvidia.com/cuda-downloads
https://nvidia.github.io/cuda-python/install.html
https://docs.cupy.dev/en/stable/install.html

</details>
<details>
<summary>Installing drivers and libraries for FLIR camera support</summary>
Go to FLIR's page for downloading their Spinnaker SDK (https://www.flir.com/support/products/spinnaker-sdk/) and download and install the Spinnaker package for your version of Ubuntu (follow the instructions in the README, and when prompted by the install script, add root and the user launching the microscopy software to the "flirimaging" group). After this, download the Python Spinnaker package for the appropriate version of python from the same page, and install it in either your base environment or the environment you run microscopy software in by following the instructions in its README file.
</details>

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
python3 main_malaria.py
python3 main_hcs.py
```
To start the program when no hardware is connected, use
```
python3 main.py --simulation
```

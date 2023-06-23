#!/bin/bash

sudo apt update
sudo apt upgrade -y

# install python3.8
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt install python3.8 -y

# set python3.8 as the default python and make sure terminal still uses python3.10 for Ubuntu 22.04
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1
sudo sed -i '1s/.*\/#!\/usr\/bin\/python3.10/' /usr/bin/gnome-terminal

# install pip
sudo apt install python3.8-distutils -y
wget https://bootstrap.pypa.io/get-pip.py
sudo python3.8 get-pip.py

# install git
sudo apt-get install git

# clone the repo
cd ~/Desktop
git clone https://github.com/hongquanli/octopi-research.git

# install libraries 
pip3 install qtpy pyserial pandas imageio crc==1.3.0 lxml numpy==1.21 opencv-contrib-python-headless==4.4.0.46 pyqt5-tools

# install camera drivers
cd ~/Desktop/octopi-research/software/drivers and libraries/daheng camera/Galaxy_Linux-x86_Gige-U3_32bits-64bits_1.2.1911.9122
./Galaxy_camera.run
cd ~/Desktop/octopi-research/software/drivers and libraries/daheng camera/Galaxy_Linux_Python_1.0.1905.9081/api
python3 setup.py build
sudo python3 setup.py install

# enable access to serial ports without sudo
sudo usermod -aG dialout $USER

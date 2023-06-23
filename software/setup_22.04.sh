#!/bin/bash
sudo apt update
sudo apt upgrade -y
# install python3.8
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt install python3.8 -y
# set python3.8 as the default python and make sure terminal still uses python3.10 for Ubuntu 22.04
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1
sudo sed -i '1s/.*\/#!\/usr\/bin\/python3.10/' /usr/bin/gnome-terminal
# install pip
sudo apt install python3.8-distutils -y
wget https://bootstrap.pypa.io/get-pip.py
sudo python3.8 get-pip.py
# install git
sudo apt-get install git
# clone the repo
cd Desktop
git clone https://github.com/hongquanli/octopi-research.git

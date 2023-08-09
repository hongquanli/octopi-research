#!/bin/bash
sudo apt update
sudo apt install nvidia-driver-530
cd ~/Downloads
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda
pip install cuda-python
pip install cupy-cuda12x
pip3 install torch torchvision torchaudio

sudo usermod -aG dialout $USER
sudo apt update
sudo apt install python3-pip python3-pyqtgraph python3-pyqt5
pip3 install --upgrade setuptools pip
pip3 install qtpy pyserial pandas imageio opencv-python opencv-contrib-python lxml
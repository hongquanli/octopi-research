sudo usermod -aG dialout $USER
sudo apt update
sudo apt install python3-pip python3-pyqtgraph python3-pyqt5
python3-pip install --upgrade setuptools pip
python3-pip install qtpy pyserial pandas imageio opencv-python opencv-contrib-python lxml
#!/bin/bash
set -eo pipefail

if [[ -n "$TRACE" ]]; then
  echo "TRACE variable non-empty, turning on script tracing."
  set -x
fi

readonly SRC_ROOT="$HOME/Desktop"
mkdir -p "$SRC_ROOT"
readonly SQUID_REPO_HTTP="https://github.com/Cephla-Lab/Squid.git"
readonly SQUID_REPO_NAME="Squid"
readonly SQUID_SOFTWARE_ROOT="$SRC_ROOT/$SQUID_REPO_NAME/software"
readonly DAHENG_CAMERA_DRIVER_ROOT="$SQUID_SOFTWARE_ROOT/drivers and libraries/daheng camera/Galaxy_Linux-x86_Gige-U3_32bits-64bits_1.2.1911.9122"
readonly DAHENG_CAMERA_DRIVER_API_ROOT="$SQUID_SOFTWARE_ROOT/drivers and libraries/daheng camera/Galaxy_Linux_Python_1.0.1905.9081/api"
readonly TOUPCAM_UDEV_RULE_PATH="$SQUID_SOFTWARE_ROOT/drivers and libraries/toupcam/linux/udev/99-toupcam.rules"
# update
sudo apt update

# install packages
sudo apt install python3-pip -y
sudo apt install python3-pyqtgraph python3-pyqt5 -y
sudo apt install python3-pyqt5.qtsvg

# clone the repo
sudo apt-get install git -y
cd "$SRC_ROOT"
git clone "$SQUID_REPO_HTTP" "$SQUID_REPO_NAME"
cd "$SQUID_SOFTWARE_ROOT"
mkdir cache

# install libraries 
pip3 install qtpy pyserial pandas imageio crc==1.3.0 lxml numpy tifffile scipy napari
pip3 install opencv-python-headless opencv-contrib-python-headless
pip3 install napari[all] scikit-image dask_image ome_zarr aicsimageio basicpy pytest

# install camera drivers
cd "$DAHENG_CAMERA_DRIVER_ROOT"
./Galaxy_camera.run
cd "$DAHENG_CAMERA_DRIVER_API_ROOT"
python3 setup.py build
sudo python3 setup.py install
cd "$SQUID_SOFTWARE_ROOT"
sudo cp "$TOUPCAM_UDEV_RULE_PATH" /etc/udev/rules.d

# enable access to serial ports without sudo
sudo usermod -aG dialout $USER

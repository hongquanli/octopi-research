#!/bin/bash
sudo apt-get install libudev1
sudo apt-get install libudev-dev
chmod 777 sdk/install.sh
cd sdk

folder="/etc/tucam/"

if [ ! -d "$folder" ]; then
  mkdir "$folder"
fi

# copy the tucsen usb camera config file
cp tuusb.conf /etc/tucam
cp 50-tuusb.rules /etc/udev/rules.d

# copy the tucsen camera libraries
cp libphxapi-x86_64.so /usr/lib
cp libTUCam.so /usr/lib
cp libTUCam.so.1 /usr/lib
cp libTUCam.so.1.0 /usr/lib
cp libTUCam.so.1.0.0 /usr/lib

exit

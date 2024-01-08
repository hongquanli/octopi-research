#!/bin/bash
wget https://flir.netx.net/file/asset/54398/original/attachment/spinnaker-3.1.0.79-amd64-pkg.tar.gz
tar -xvf spinnaker-3.1.0.79-amd64-pkg.tar.gz
sudo apt-get install libavcodec58 libavformat58 \
libswscale5 libswresample3 libavutil56 libusb-1.0-0 \
libpcre2-16-0 libdouble-conversion3 libxcb-xinput0 \
libxcb-xinerama0
sudo sh spinnaker-3.1.0.79-amd64/install_spinnaker.sh
sudo sh spinnaker-3.1.0.79-amd64/configure_usbfs.sh

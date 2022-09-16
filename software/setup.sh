sudo usermod -aG dialout $USER
sudo apt update
sudo apt install -y python3-pip python3-pyqtgraph python3-pyqt5 tree curl git micro
pip3 install --upgrade setuptools pip
pip3 install qtpy pyserial pandas imageio opencv-python opencv-contrib-python lxml crc

cd ~/Downloads
git clone https://github.com/hongquanli/octopi-research
# from https://forum.squid-imaging.org/t/setting-up-arduino-teensyduino-ide-for-uploading-firmware/36
curl https://downloads.arduino.cc/arduino-1.8.19-linux64.tar.xz -o arduino-1.8.19.tar.xz
tar -xf arduino-1.8.19.tar.xz
curl https://www.pjrc.com/teensy/00-teensy.rules -o 00-teensy.rules
sudo cp 00-teensy.rules /etc/udev/rules.d/
curl https://www.pjrc.com/teensy/td_157/TeensyduinoInstall.linux64 -o teensyduino-install.linux64
chmod +x teensyduino-install.linux64
./teensyduino-install.linux64 --dir=arduino-1.8.19
cd arduino-1.8.19
chmod +x install.sh
sudo ./install.sh
echo "comment #include 'def_octopi.h' and uncomment #include 'def_octopi_80120.h' switch to correct board (teensy 4.1) then install the packages PacketSerial and FastLED (both in Tools)"
cd octopi-research/firmware/octopi_firmware_v2/main_controller_teensy41
arudino main_controller_teensy41.ino 
cd octopi-research/software

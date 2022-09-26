sudo usermod -aG dialout $USER
sudo apt update
sudo apt install -y python3-pip python3-pyqtgraph python3-pyqt5 make gcc build-essential libgtk-3-dev tree curl git micro openjdk-11-jdk-headless default-libmysqlclient-dev libnotify-dev libsdl2-dev
pip3 install --upgrade setuptools pip
pip3 install numpy matplotlib qtpy pyserial pandas imageio opencv-python opencv-contrib-python lxml crc

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH=$PATH:/home/ubuntu/.local/bin

wget https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-20.04/wxPython-4.1.0-cp38-cp38-linux_x86_64.whl
pip3 install wxPython-4.1.0-cp38-cp38-linux_x86_64.whl

cd ~/Downloads
git clone https://github.com/CellProfiler/CellProfiler.git
cd CellProfiler
pip3 install .

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
cd ~/Downloads/octopi-research/firmware/octopi_firmware_v2/main_controller_teensy41
arduino main_controller_teensy41.ino
cd ~/Downloads/octopi-research/software
cp configurations/configuration_HCS_v2.txt configuration.txt
cd ~/Downloads/octopi-research/software/drivers\ and\ libraries/daheng\ camera/Galaxy_Linux-x86_Gige-U3_32bits-64bits_1.2.1911.9122
echo -e "\ny\nEn\n" | sudo ./Galaxy_camera.run
cd ~/Downloads/octopi-research/software
python3 main.py

# installing prerequisite software packages
sudo usermod -aG dialout $USER # allow communication with arduino boards without superuser access
sudo apt update
sudo apt install -y tree curl git micro htop # basic tools that should be installed
sudo apt install -y python3-pip python3-pyqtgraph python3-pyqt5 # squid software dependencies
sudo apt install -y libreoffice virtualenv make gcc build-essential libgtk-3-dev openjdk-11-jdk-headless default-libmysqlclient-dev libnotify-dev libsdl2-dev # dependencies for cellprofiler
sudo snap install --classic code # install visual studio code

# set environmental variables required for cellprofiler installation
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH=$PATH:/home/ubuntu/.local/bin

# install everything relative to home
cd ~

# setuo microscope python env (which is global env, since Qt is used for gui, which does not work inside virtualenv)
pip3 install --upgrade setuptools pip
pip3 install pyqt5 pyqtgraph scipy numpy==1.23 matplotlib qtpy pyserial pandas imageio opencv-python opencv-contrib-python lxml crc scikit-image tqdm # python dependencies for squid software

# install orange
virtualenv orange_venv
source orange_venv/bin/activate
pip3 install --upgrade setuptools pip
pip3 install orange3
deactivate

# install cellprofiler
virtualenv cellprofiler_venv
source cellprofiler_venv/bin/activate
pip3 install numpy==1.23 matplotlib qtpy pyserial pandas imageio opencv-python opencv-contrib-python lxml crc # python dependencies for squid software, installed into cellprofiler virtualenv
# download prebuilt wxpython wheel to avoid local compilation which takes 30 minutes
wget https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-20.04/wxPython-4.1.0-cp38-cp38-linux_x86_64.whl
pip3 install wxPython-4.1.0-cp38-cp38-linux_x86_64.whl
pip3 install cellprofiler==4.2.4 # numpy needs to be done installing before cellprofiler is installed
deactivate

# install cellprofiler analyst
virtualenv cellprofileranalyst_venv
source cellprofileranalyst_venv/bin/activate
pip3 install numpy==1.23 pandas seaborn scikit-learn verlib python-javabridge python-bioformats
pip3 install wxPython-4.1.0-cp38-cp38-linux_x86_64.whl
wget https://github.com/CellProfiler/CellProfiler-Analyst/archive/refs/tags/3.0.4.tar.gz -O cpa304.tar.gz
tar -xf cpa304.tar.gz
pip3 install ./CellProfiler-Analyst-3.0.4
# for some reason these icons are not copied during installation (which crashes the program on startup)
cp CellProfiler-Analyst-3.0.4/cpa/icons/* cellprofileranalyst_venv/lib/python3.8/site-packages/cpa/icons/
deactivate

# install microscope software (and firmware)
cd ~/Downloads
git clone https://github.com/hongquanli/octopi-research # download squid software and firmware repo
# from https://forum.squid-imaging.org/t/setting-up-arduino-teensyduino-ide-for-uploading-firmware/36 :
# download arduino IDE
curl https://downloads.arduino.cc/arduino-1.8.19-linux64.tar.xz -o arduino-1.8.19.tar.xz
tar -xf arduino-1.8.19.tar.xz
# install arduino udev rules for arduino board communication
curl https://www.pjrc.com/teensy/00-teensy.rules -o 00-teensy.rules 
sudo cp 00-teensy.rules /etc/udev/rules.d/
# install teensyduino board package (teensy4.1 is used inside the microscopes)
curl https://www.pjrc.com/teensy/td_157/TeensyduinoInstall.linux64 -o teensyduino-install.linux64
chmod +x teensyduino-install.linux64
./teensyduino-install.linux64 --dir=arduino-1.8.19
cd arduino-1.8.19
# install arduino IDE (incl. teensyduin)
chmod +x install.sh
sudo ./install.sh

# install/upgrade microscope firmware
echo "manual instructions: in the now open window, manually comment #include 'def_octopi.h' and uncomment #include 'def_octopi_80120.h', then switch to correct board (teensy 4.1) then install the packages PacketSerial and FastLED (both in Tools), then flash firmware"
cd ~/Downloads/octopi-research/firmware/octopi_firmware_v2/main_controller_teensy41
arduino main_controller_teensy41.ino
# copy default microscope configuration file - requires adjustment of well positions and autofocus channel
cd ~/Downloads/octopi-research/software
cp configurations/configuration_HCS_v2.txt configuration.txt
# install camera driver
cd ~/Downloads/octopi-research/software/drivers\ and\ libraries/daheng\ camera/Galaxy_Linux-x86_Gige-U3_32bits-64bits_1.2.1911.9122
echo -e "\ny\nEn\n" | sudo ./Galaxy_camera.run

# set up bash commands to run installed software
echo '
run_microscope() {
  cd ~/Downloads/octopi-research/software
  python3 main.py
}
run_hcs() {
  cd ~/Downloads/octopi-research/software
  python3 main_hcs.py
}
run_cellprofiler() {
  source ~/cellprofiler_venv/bin/activate
  python3 -m cellprofiler
  deactivate
}
run_cellprofileranalyst() {
  source ~/cellprofileranalyst_venv/bin/activate
  python3 ~/CellProfiler-Analyst-3.0.4/CellProfiler-Analyst.py
  deactivate
}
run_orange() {
  source ~/orange_venv/bin/activate
  python3 -m Orange.canvas
  deactivate
}
' >> ~/.bashrc
source ~/.bashrc

# add desktop icons to start the installed software (incl. microscope)
echo '[Desktop Entry]
Type=Application
Terminal=false
Name=cellprofiler
Icon=utilities-terminal
Exec=/home/pharmbio/Documents/cellprofiler.sh
Categories=Application;
' > ~/Desktop/cellprofiler.desktop
echo '[Desktop Entry]
Type=Application
Terminal=false
Name=cellprofiler analyst
Icon=utilities-terminal
Exec=/home/pharmbio/Documents/cellprofileranalyst.sh
Categories=Application;
' > ~/Desktop/cellprofileranalyst.desktop
echo '[Desktop Entry]
Type=Application
Terminal=true
Name=microscope
Icon=utilities-terminal
Exec=/home/pharmbio/Documents/hcs.sh
Categories=Application;
' > ~/Desktop/hcs.desktop
echo '[Desktop Entry]
Type=Application
Terminal=false
Name=orange
Icon=utilities-terminal
Exec=/home/pharmbio/Documents/orange.sh
Categories=Application;
' > ~/Desktop/orange.desktop
echo '#!/bin/bash
source /home/pharmbio/cellprofiler_venv/bin/activate
python3 -m cellprofiler
deactivate
' > ~/Documents/cellprofiler.sh
echo '#!/bin/bash
source /home/pharmbio/cellprofileranalyst_venv/bin/activate
python3 ~/CellProfiler-Analyst-3.0.4/CellProfiler-Analyst.py
deactivate
' > ~/Documents/cellprofileranalyst.sh
echo '#!/bin/bash
cd /home/pharmbio/Downloads/octopi-research/software
python3 main_hcs.py
sleep 10
' > ~/Documents/hcs.sh
echo '#!/bin/bash
source /home/pharmbio/orange_venv/bin/activate
python3 -m Orange.canvas
deactivate
' > ~/Documents/orange.sh

chmod 755 ~/Desktop/orange.desktop ~/Documents/orange.sh 
chmod 755 ~/Desktop/hcs.desktop ~/Documents/hcs.sh
chmod 755 ~/Desktop/cellprofiler.desktop ~/Documents/cellprofiler.sh 
chmod 755 ~/Desktop/cellprofileranalyst.desktop ~/Documents/cellprofileranalyst.sh 

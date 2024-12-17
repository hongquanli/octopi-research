## Setting up the environments
Run the following script in terminal to clone the repo and set up the environment
```
wget https://raw.githubusercontent.com/Cephla-Lab/Squid/master/software/setup_22.04.sh
chmod +x setup_22.04.sh
./setup_22.04.sh
```

Then run this script to set up cuda
```
wget https://raw.githubusercontent.com/Cephla-Lab/Squid/master/software/setup_cuda_22.04.sh
chmod +x setup_cuda_22.04.sh
./setup_cuda_22.04.sh
```

Reboot the computer to finish the installation.

## Optional or Hardware-specific dependencies

<details>
<summary>image stitching dependencies (optional)</summary>
For optional image stitching using ImageJ, additionally run the following:

```
sudo apt-get update
sudo apt-get install openjdk-11-jdk
sudo apt-get install maven
pip3 install pyimagej
pip3 instlal scyjava
pip3 install tifffile
pip3 install imagecodecs
```

Then, add the following line to the top of `/etc/environment` (needs to be edited with `sudo [your text editor]`):
```
JAVA_HOME=/usr/lib/jvm/default-java
```
Then, add the following lines to the top of `~/.bashrc` (or whichever file your terminal sources upon startup):
```
source /etc/environment
export JAVA_HOME = $JAVA_HOME
export PATH=$JAVA_HOME/bin:$PATH
```
</details>

<details>
<summary>Installing drivers and libraries for FLIR camera support</summary>
Go to FLIR's page for downloading their Spinnaker SDK (https://www.flir.com/support/products/spinnaker-sdk/) and register.

Open the `software/drivers and libraries/flir` folder in terminal and run the following
```
sh ./install_spinnaker.sh
sh ./install_PySpin.sh
```
</details>

<details>
<summary>Add udev rules for ToupTek cameras</summary>

```
sudo cp drivers\ and\ libraries/toupcam/linux/udev/99-toupcam.rules /etc/udev/rules.d
```
</details>

<details>
<summary>Installing drivers and libraries for Hamamatsu camera support</summary>

Open the `software/drivers and libraries/hamamatsu` folder in terminal and run the following
```
sh ./install_hamamatsu.sh
```
</details>

<details>
<summary>Installing drivers and libraries for iDS camera support</summary>
- Software:

Go to iDS's page for downloading their software (https://en.ids-imaging.com/download-details/1009877.html?os=linux&version=&bus=64&floatcalc=). Register and log in.

Open the `software/drivers and libraries/ids` folder in terminal and run the following
```
sh ./install_ids.sh
```

You will be asked to enter sudo password.

- Firmware (optional):

If you would like to update the firmware of the camera (optional), download the Vision firmware update (GUF file) on the same page.

Open the `software/drivers and libraries/ids/ids-peak_2.11.0.0-178_amd64/bin` folder in terminal and run the following
```
./ids_peak_cockpit
```

This will start the iDS peak Cockpit software. Then: 
1. Open the camera manager by clicking on the camera manager icon in the main menu.
2. Select the camera in the camera manager.
3. Click on the firmware update icon in the menu to open the dialog for selecting the update file for the Vision firmware (*.guf).
4. Select the update file.
5. Click on "Open".

The update is started and the camera is updated. Note: If you select an incorrect update file by mistake, you will see the message "The update file is incompatible".
After the update is complete, you can close the iDS peak Cockpit software. (Reference: https://en.ids-imaging.com/tl_files/downloads/usb3-vision/firmware/ReadMe.html)

</details>

<details>
<summary>Installing drivers and libraries for Tucsen camera support</summary>

Open the `software/drivers and libraries/tucsen` folder in terminal and run the following to log in as a root user
```
sudo -s
```

The following steps should be run as root user
```
sh ./install_tucsen.sh
```

After installation, run the following to log out
```
exit
```

</details>

## Configuring the software
Copy the .ini file associated with the microscope configuration to the software folder. Make modifications as needed (e.g. `camera_type`, `support_laser_autofocus`,`focus_camera_exposure_time_ms`)

## Using the software
```
python3 main_hcs.py
```
To start the program when no hardware is connected, use
```
python3 main_hcs.py --simulation
```

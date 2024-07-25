## Setting up the environments
Run the following script in terminal to clone the repo and set up the environment
```
wget https://raw.githubusercontent.com/hongquanli/octopi-research/master/software/setup_22.04.sh
chmod +x setup_22.04.sh
./setup_22.04.sh
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

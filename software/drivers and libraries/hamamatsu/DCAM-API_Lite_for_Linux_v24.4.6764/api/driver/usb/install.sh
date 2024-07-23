#!/bin/bash

######################################
# SETTING                            #
######################################
MAINDIR=$(cd $(dirname $0) && pwd)

FLG_MAINCALL=0

for arg in "$@"
do
	if [ $arg == "--maincall" ]; then
		FLG_MAINCALL=1
	fi
done


######################################
# DIRECTORY PATH                     #
######################################
TARGET_DCAM_MAIN_DIR="/usr/local/hamamatsu_dcam"
TARGET_DCAM_DRV_DIR="$TARGET_DCAM_MAIN_DIR/script"
TARGET_RULES_DIR="/etc/udev/rules.d"


######################################
# PRECHECK                           #
######################################
if [ ! -d $TARGET_DCAM_DRV_DIR -a $FLG_MAINCALL -eq 1 ]; then
	sudo mkdir $TARGET_DCAM_DRV_DIR
fi

######################################
# INSTALL                            #
######################################

if [ -d $TARGET_DCAM_DRV_DIR ]; then
	sudo cp -f $MAINDIR/uninstall_*.sh $TARGET_DCAM_DRV_DIR
fi
sudo cp -f $MAINDIR/udev/rules.d/55-hamamatsu_dcamusb.rules $TARGET_RULES_DIR

ID=$(whoami)
sudo gpasswd -a $ID plugdev 

echo "USB Driver installed."

exit 0

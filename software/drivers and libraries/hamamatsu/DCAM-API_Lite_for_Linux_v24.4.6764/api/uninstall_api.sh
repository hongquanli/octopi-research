#!/bin/bash

######################################
# SETTING                            #
######################################
MAINDIR=$(cd $(dirname $0) && pwd)
UNINSTALL_DIR="/usr/local/hamamatsu_dcam"

FLG_FORCE=0
FLG_MAINCALL=0

for arg in "$@"
do
	if [ $arg == "-f" -o $arg == "--force" ]; then
		FLG_FORCE=1
	fi
done


######################################
# uninstall directory check          #
######################################
if [ ! -d $UNINSTALL_DIR ]; then
	echo "Warnig : \"$UNINSTALL_DIR\" is not installed."	
	exit 0
fi

if [ $FLG_FORCE == 0 ]; then
	echo "Do you want to remove \"$UNINSTALL_DIR/api and Driver\"? (Y/n)"
	read ans
	if [ "x$ans" == "xn" ]; then
		exit 0
	fi
fi


######################################
# sub directory uninstall            #
######################################
RUNTIME_UNINSTALLER=$UNINSTALL_DIR/api/uninstall_runtime.sh 
FBD_DRIVER_UNINSTALLER=$UNINSTALL_DIR/script/uninstall_fbd.sh 
USB_DRIVER_UNINSTALLER=$UNINSTALL_DIR/script/uninstall_usb.sh 

if [ -e $RUNTIME_UNINSTALLER ]; then
	$RUNTIME_UNINSTALLER -f
fi

if [ -e $FBD_DRIVER_UNINSTALLER ]; then
	$FBD_DRIVER_UNINSTALLER -f
fi

if [ -e $USB_DRIVER_UNINSTALLER ]; then
	$USB_DRIVER_UNINSTALLER -f
fi


######################################
# directry check		     #
######################################
if [ -d $UNINSTALL_DIR ]; then
	DIR_COUNT=$(ls -l $UNINSTALL_DIR | grep ^d | wc -l )

	if [ $DIR_COUNT -eq 0 ]; then
		sudo rm -rf $UNINSTALL_DIR
	fi

	sudo rm -f $UNINSTALL_DIR/uninstall_api.sh
fi

echo ""
echo "########################################"
echo "Uninstall DCAM-API completely."
echo "########################################"
echo ""

exit 0

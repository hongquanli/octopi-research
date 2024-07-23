#!/bin/bash

#############################################################################################
# Help
#############################################################################################
ShowHelp()
{
	echo ""
	echo " <<< Install DCAM-API Driver and Runtime >>>"
	echo " command line : relative path from root folder of DCAM-API installer." 
	echo " $	api/install.sh [OPTION] TARGET"
	echo ""
	echo " [OPTION]: followint option is available."
	echo "	-h, --help	show help and exit"
	echo ""
	echo " Target: choose following keywords." 
	echo "	fbd		install firebird(x86_64 only)"
	echo "	usb3		install usb3"
	echo ""
}


#############################################################################################
# INSTALL SETTING
#############################################################################################

readonly NONE=0
readonly INSTALL=1
readonly COMPLETE=2

TARGET_API=$INSTALL
TARGET_DRIVER=$INSTALL

TARGET_DRV_FBD=$NONE
TARGET_DRV_USB=$NONE

TARGET_FBD="not_install"
TARGET_USB3="not_install"
API_INSTALL_ARGUMENT=""


MAINDIR=$(cd $(dirname $0) && pwd)
PROCTYPE=$(uname -m)
if [ $PROCTYPE == "i486" -o $PROCTYPE == "i586" -o $PROCTYPE == "i686" -o $PROCTYPE == "k6" -o $PROCTYPE == "athlon" ]; then
	PROCTYPE="i386"
fi

DCAM_VERSION=$(cd $MAINDIR/runtime/$PROCTYPE/core && ls libdcamdig.so.* | cut -d "." -f 3-5)


FLAG_TARGET=0

for arg in "$@"
do
	if [ $arg == "-h" -o $arg == "--help" ]; then
		ShowHelp
		exit 0
	elif [ $arg == "usb3" ]; then
		TARGET_USB3="install"
		API_INSTALL_ARGUMENT="$API_INSTALL_ARGUMENT usb3"
		let FLAG_TARGET=${FLAF_TARGET}+1
	elif [ $arg  == "fbd" -a $PROCTYPE == "x86_64" ]; then
		TARGET_FBD="install"
		API_INSTALL_ARGUMENT="$API_INSTALL_ARGUMENT fbd"
		let FLAG_TARGET=${FLAF_TARGET}+1
	else
		echo "Invalid option: $arg"
		echo "Try 'install.sh --help' for more information."
		exit 1
	fi
done

if [ $FLAG_TARGET == 0 ]; then
	echo "Please input target."
	ShowHelp
	exit 1
fi

#############################################################################################

######################################
# INSTALLED CHECK                   #
######################################
Installed_check()
{
	ERROR_CODE=$1

	echo ""

	echo "< Install modules >"
	echo "####################################################"
	if [ $TARGET_API == $INSTALL ]; then
		echo "  API         : incomplete"
	elif [ $TARGET_API == $COMPLETE ]; then
		echo "  API         : complete"
	fi

	if [ $TARGET_DRV_FBD == $INSTALL ]; then
		echo "  FBD  DRIVER : incomplete"
	elif [ $TARGET_DRV_FBD == $COMPLETE ]; then
		echo "  FBD  DRIVER : complete"
	fi

	if [ $TARGET_DRV_USB == $INSTALL ]; then
		echo "  USB  DRIVER : incomplete"
	elif [ $TARGET_DRV_USB == $COMPLETE ]; then
		echo "  USB  DRIVER : complete"
	fi	
	echo "####################################################"
	echo ""
	return $ERROR_CODE
}

#############################################################################################
# INSTALL START
#############################################################################################



######################################
# DIRECTORY PATH                     #
######################################
ORIGINAL_DCAM_MAIN_DIR="$MAINDIR"
ORIGINAL_DCAM_API_DIR="$MAINDIR/runtime"
ORIGINAL_DCAM_DRV_DIR="$MAINDIR/driver"

INSTALL_DCAM_MAIN_DIR="/usr/local/hamamatsu_dcam"

KRNL=`uname -r`
BUILD_DIR="/lib/modules/$KRNL/build"

echo
echo "< Install Start >"
echo 
fbd_flag=0

######################################
# INSTALL                            #
######################################
if [ ! -d $INSTALL_DCAM_MAIN_DIR ]; then
	sudo mkdir $INSTALL_DCAM_MAIN_DIR
fi
sudo cp -f $ORIGINAL_DCAM_MAIN_DIR/uninstall_* $INSTALL_DCAM_MAIN_DIR

$ORIGINAL_DCAM_API_DIR/install.sh $API_INSTALL_ARGUMENT 
if [ $? == 0 ]; then
	TARGET_API=$COMPLETE
fi

dist=`cat /etc/issue`
if [[ $dist = Ubuntu* ]]; then
	dist=Debian
fi


if [ "$TARGET_FBD" == "install" ]; then

	iommu=$(sudo dmesg | grep IOMMU | grep -v IOMMUv2)
	if [ -n "$iommu" ]; then
		echo ""
		echo "####################################################"
		echo "!!Attention!!"
		echo "----------------------------------------------------"
		echo "IOMMU is enabled on your system."
		echo "If you can not capture correctly,"
		echo " you should disable IOMMU setting in BIOS. "
		echo "----------------------------------------------------"
		echo "####################################################"
	fi

		
	echo ""
	echo "####################################################"
#	echo "Need following packages to install FireBird Driver."
	echo "Following packages will be installed."
	echo "----------------------------------------------------"
	if [[ $dist = Debian* ]]; then
		echo "	* linux-headers-generic"
		echo "	* linux-headers-$(uname -r)"
		echo "	* build-essential"
		echo "####################################################"
		sudo apt install -y linux-headers-generic linux-headers-$(uname -r) build-essential
	else
		echo "	* kernel-devel"
		echo "	* kernel-headers"
		echo "	* gcc"
		echo "####################################################"
		sudo yum install -y kernel-devel kernel-headers gcc
	fi
#	echo "----------------------------------------------------"
#	echo "Have you already installed those? (y/N)"
#	read ans
	
	echo ""

#	if [ "x$ans" == "xy" ]; then

		SECURE_BOOT=(`test -d /sys/firmware/efi && echo efi || echo bios`)
	if [ "x$SECURE_BOOT" == "xefi" ]; then
		echo ""
		echo "#####################################################"
		echo "Your System has Secure Boot enabled."
		echo "The FireBird driver installation will fail."
		echo "See \"doc\\add_sign.txt\" to add a Digital Signature."
		echo "#####################################################"
		echo ""
	fi

	sudo mkdir $INSTALL_DCAM_MAIN_DIR/tools
	cd $MAINDIR
	cd ../tools/x86_64
	sudo cp aslupdate $INSTALL_DCAM_MAIN_DIR/tools

	TARGET_DRV_FBD=$INSTALL
	$ORIGINAL_DCAM_DRV_DIR/firebird/install.sh --maincall
	if [ $? == 0 ]; then
		TARGET_DRV_FBD=$COMPLETE
		fbd_flag=1
	fi
#	else
#		echo ""
#		echo "After install those packages, run $ORIGINAL_DCAM_DRV_DIR/firebird/install.sh"
#		echo ""
#		TARGET_DRV_FBD=$INSTALL
#	fi
fi

if [ "$TARGET_USB2" == "install" -o "$TARGET_USB3" == "install" ]; then
	TARGET_DRV_USB=$INSTALL
	$ORIGINAL_DCAM_DRV_DIR/usb/install.sh  --maincall
	if [ $? == 0 ]; then
		TARGET_DRV_USB=$COMPLETE
	fi

	if [[ $dist = Debian* ]]; then

		dpkg -l libusb-dev > libusbdever;
		if grep -q '0.1.12-32' ./libusbdever; then
			echo "libusb-dev Version 0.1.12-32 found" 
		else
			echo "Purging and installing latest libusb-dev. Should be 0.1.12-32 or higher."
			sudo apt --assume-yes purge libusb-dev
			sudo apt --assume-yes autoremove
			sudo apt --assume-yes install libusb-dev
		fi
		rm libusbdever;

	else
		sudo yum install -y libusb-devel
	fi
#	echo ""
#	echo "#######################################################"
#	echo "DCAM-API depends on LIBUSB-0.X(not LIBUSB-1.X)."
#	echo "You should install it before using HAMAMATSU cameras."
#	echo "#######################################################"

fi


if [ "x$fbd_flag" == "x1" ]; then
	echo "RESTART COMPUTER."
	echo ""
fi

sudo chmod 777 $INSTALL_DCAM_MAIN_DIR/*.sh
sudo chmod 777 $INSTALL_DCAM_MAIN_DIR/*/*.sh					

Installed_check 0
ret=$?
if [ "x$ret" != "x0" ]; then
	echo $ret
fi

exit 0

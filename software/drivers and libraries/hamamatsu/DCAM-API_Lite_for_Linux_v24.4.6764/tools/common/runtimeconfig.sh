#!/bin/bash

# ################################################################################
# Get Current Setting and Show
# ################################################################################
Show_setting()
{
	dirpath=$1
	conf=${dirpath}dcamdig.conf
	flag=0
	
	echo "-------------------------------------"

	if [ -e $conf ]; then
	
		while read line
		do
#		echo $line
			if [[ "$line" =~ ^disable ]]; then
				flag=1
				enable=${line: -1}
				if [ $enable == "1" ]; then
					echo "DCAM:	Disable"
				else
					echo "DCAM:	Enable"
				fi
				break
			fi
		done < $conf
	
	fi

	if [ $flag == 0 ]; then
		echo "DCAMDIG:	Not Installed"
	fi

	flag=0
	conf=${dirpath}fgphnx.conf
	

	if [ -e $conf ]; then
		while read line
		do
#			echo $line
			if [[ "$line" =~ ^disable ]]; then
				flag=1
				enable=${line: -1}
				if [ $enable == "1" ]; then
					echo "PHNX:	Disable"
				else
					echo "PHNX:	Enable"
				fi
				break
			fi
		done < $conf
	fi

	if [ $flag == 0 ]; then
		echo "PHNX:	Not Installed"
	fi

	flag=0
	conf=${dirpath}fgusb3.conf
	
	if [ -e $conf ]; then

		while read line
		do
#		echo $line
			if [[ "$line" =~ ^disable ]]; then
				flag=1
				enable=${line: -1}
				if [ $enable == "1" ]; then
					echo "USB:	Disable"
				else
					echo "USB:	Enable"
				fi
			fi
		done < $conf
	fi

	if [ $flag == 0 ]; then
		echo "USB:	Not Installed"
	fi

	echo "-------------------------------------"
}


# ################################################################################
# Show Usage
# ################################################################################
if [ "$1" != "dcam" ] && [ "$1" != "phnx" ] && [ "$1" != "usb" ] && [ "$1" != "show" ]; then
	echo "<< Set DCAM/PHNX/USB Module Enabled >>"
	echo ""
	echo "$ module_switch.sh TARGET SETTING"
	echo ""
	echo "TARGET: choose following keywords."
	echo "dcam	DCAM Dig"
	echo "phnx	PHOENIX Module"
	echo "usb	USB Module"
	echo "show	Show current setting"
	echo ""
	echo "SETTING: choose following keywords."
	echo "on	Enable to the module."
	echo "off	Disable to the module."
	exit
fi

# ################################################################################
# Get libdcamapi.so path to temporarty file
# ################################################################################
cd `dirname $0`
./get_filepath.sh > dir.txt
CONFPATH=`cat dir.txt`
CONFPATH=${CONFPATH}modules/
# Remove temporary file
rm dir.txt

# ################################################################################
# Local Setting
# ################################################################################

#conf=`cat dir.txt`
#echo $conf
readonly OFF=0
readonly ON=1
readonly KP=2

DCAMMOD=$KP
PHNXMOD=$KP
USBMOD=$KP

OUTPUT="./current"

# ################################################################################
# Show Current Settings
# ################################################################################
if [ "$1" == "show" ]; then
	echo "Current Setting"
	Show_setting $CONFPATH
	exit
fi



# ################################################################################
# Check the arguments
# ################################################################################

if [ "$2" == "" ]; then
	echo "Specify ON or OFF."
	exit
fi

# ################################################################################
# Set Conffile path
# ################################################################################
if [ $1 == "dcam" ]; then
	CONFPATH=${CONFPATH}dcamdig.conf
	if [ "$2" == "on" ] || [ "$2" == "ON" ] ||[ "$2" == "On" ]; then
		DCAMMOD=$ON
	else
		DCAMMOD=$OFF
	fi

elif [ $1 == "phnx" ]; then
	CONFPATH=${CONFPATH}fgphnx.conf
	if [ "$2" == "on" ] || [ "$2" == "ON" ] ||[ "$2" == "On" ]; then
		PHNXMOD=$ON
	else
		PHNXMOD=$OFF
	fi

else
	CONFPATH=${CONFPATH}fgusb3.conf
	if [ "$2" == "on" ] || [ "$2" == "ON" ] ||  [ "$2" == "On" ]; then
		USBMOD=$ON
	else
		USBMOD=$OFF
	fi
fi

# ################################################################################
# Check DCAM or the Module is installed
# ################################################################################

if [ ! -e $CONFPATH ]; then
	echo "$CONFPATH is not exist."
	echo "Need to install DCAM."
	exit
fi

#echo $CONFPATH

# ################################################################################
# DCAMMOD Setting
# ################################################################################
if [ $DCAMMOD == $ON ]; then
	sudo sed -i -e "s/disable\t1/disable\t0/g" $CONFPATH
elif [ $DCAMMOD == $OFF ]; then
	sudo sed -i -e "s/disable\t0/disable\t1/g" $CONFPATH
fi

# ################################################################################
# PHNXMOD Setting
# ################################################################################
if [ $PHNXMOD == $ON ]; then
	sudo sed -i -e "s/disable\t1/disable\t0/g" $CONFPATH
elif [ $PHNXMOD == $OFF ]; then
	sudo sed -i -e "s/disable\t0/disable\t1/g" $CONFPATH
fi

# ################################################################################
# USBMOD Setting
# ################################################################################
if [ $USBMOD == $ON ]; then
	sudo sed -i -e "s/disable\t1/disable\t0/g" $CONFPATH
elif [ $USBMOD == $OFF ]; then
	sudo sed -i -e "s/disable\t0/disable\t1/g" $CONFPATH
fi


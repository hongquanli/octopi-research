#!/bin/bash

######################################
# SETTING                            #
######################################
MAINDIR=$(cd $(dirname $0) && pwd)
UNINSTALL_DIR="/usr/local/hamamatsu_dcam/script"

FLG_FORCE=0
FLG_MAINCALL=0

for arg in "$@"
do
	if [ $arg == "-f" -o $arg == "--force" ]; then
		FLG_FORCE=1
	elif [ $arg == "--maincall" ]; then
		FLG_MAINCALL=1
	fi
done


######################################
# module uninstall                   #
######################################
MAINDIR=$(cd $(dirname $0) && pwd)
INSTALL_ASL_DIR="/usr/local/activesilicon"

dist=`cat /etc/issue`

if [[ $dist = Ubuntu* ]]; then
	dist=Debian
fi

if [[ $dist = Debian* ]]; then
	sudo dpkg --purge as-fbd-linux
	sudo dpkg --purge as-fbd-cl-linux
	sudo dpkg --purge as-fbd-linux-ham
else
	sudo rpm -e as-fbd-linux
	sudo rpm -e as-fbd-cl-linux
	sudo rpm -e as-fbd-linux-ham
fi

sudo rm -f /etc/modprobe.d/blacklist-solos-pci.conf
sudo rm -f /etc/udev/rules.d/80-activesilicon.rules
sudo rm -f /etc/ld.so.conf.d/aslphxapi.conf
sudo /sbin/ldconfig
sudo rm -rf $INSTALL_ASL_DIR


######################################
# directory uninstall                #
######################################
UNINSTALL_MAIN="/usr/local/hamamatsu_dcam/"

if [ -d $UNINSTALL_DIR ]; then
	sudo rm -f $UNINSTALL_DIR/$(basename $0)

	UNINSTALL_ARRAY=($(find $UNINSTALL_DIR -follow -maxdepth 1 -name "uninstall_*.sh"))
	if [ "x$UNINSTALL_ARRAY" == "x" ]; then
		sudo rm -rf $UNINSTALL_DIR
	fi

	DIR_COUNT=$(ls -l $UNINSTALL_MAIN | grep ^d | wc -l)
	if [ $DIR_COUNT -eq 0 ]; then
		sudo rm -rf $UNINSTALL_MAIN
	fi
fi

exit 0

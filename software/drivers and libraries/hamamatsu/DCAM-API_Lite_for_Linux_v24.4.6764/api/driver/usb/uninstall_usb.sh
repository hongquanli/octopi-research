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
sudo rm -f /etc/udev/rules.d/55-hamamatsu_dcamusb.rules


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

#!/bin/bash

######################################
# SETTING                            #
######################################
MAINDIR=$(cd $(dirname $0) && pwd)
KERNEL_VERSION=$(uname -r)
PROCTYPE=$(uname -m)
if [ $PROCTYPE == "i486" -o $PROCTYPE == "i586" -o $PROCTYPE == "i686" -o $PROCTYPE == "k6" -o $PROCTYPE == "athlon" ]; then
	echo "$PROCTYPE is not supported."
	PROCTYPE="i386"
	exit 1
fi

#DRV_VERSION="HAM-Installer-Linux-2020-12-03"
#DRV_VERSION="HAM-Installer-Linux-v02_05_00"
#DRV_VERSION="HAM-Installer-Linux-v03_00_04"
DRV_VERSION="HAM-Installer-Linux-v03_02_01_runtime"
DRV_DIR="as-fbd-liux-ham"
FLG_MAINCALL=0
#DRV_UPDATE="HAM-Installer-Linux-v02_05_00-Update-2021-05-27"

for arg in "$@"
do
	if [ $arg == "--maincall" ]; then
		FLG_MAINCALL=1
	fi
done


######################################
# DIRECTORY PATH                     #
######################################
INSTALLER_DRV_PHNX_DIR="$MAINDIR"
INSTALLER_DRV_PHNX_LDSO_DIR="$INSTALLER_DRV_PHNX_DIR/etc/ld.so.conf.d"

TARGET_DCAM_MAIN_DIR="/usr/local/hamamatsu_dcam"
TARGET_DCAM_DRV_DIR="$TARGET_DCAM_MAIN_DIR/script"
TARGET_ASL_DIR="/usr/local/activesilicon"
TARGET_ASL_LIB_DIR="$TARGET_ASL_DIR/lib64"
TARGET_ASL_BIN_DIR="$TARGET_ASL_DIR/bin64"
TARGET_LDSO_DIR="/etc/ld.so.conf.d"
TARGET_RULES_DIR="/etc/udev/rules.d"
TARGET_BLACKLIST_DIR="/etc/modprobe.d"


######################################
# PRECHECK                           #
######################################

if [ ! -d $TARGET_DCAM_DRV_DIR -a $FLG_MAINCALL -eq 1 ]; then
	sudo mkdir $TARGET_DCAM_DRV_DIR 
fi


######################################
# INSTALL                            #
######################################

dist=`cat /etc/issue`

#tar -zxvf $MAINDIR/$DRV_VERSION.tar.gz -C $MAINDIR
tar -zxvf $MAINDIR/$DRV_VERSION.tgz -C $MAINDIR

#mv -f ./$DRV_VERSION $MAINDIR

if [[ $dist = Ubuntu* ]]; then
	dist=Debian
fi

if [[ $dist = Debian* ]]; then
	echo "Use .deb package"
	DRVPATH="$MAINDIR/x86_64/*.deb"
	sudo dpkg --install $DRVPATH
else
	echo "Use .rpm package"
	DRVPATH="$MAINDIR/x86_64/*.rpm"
	sudo rpm -ivh $DRVPATH
fi
rm $MAINDIR/as-fbd-linux-ham*

rm -rf $MAINDIR/$DRV_VERSION

# update
#tar -zxvf $MAINDIR/$DRV_UPDATE.tar.gz -C $MAINDIR

#sudo cp -a $MAINDIR/libphx* $TARGET_ASL_LIB_DIR

#rm $MAINDIR/libphx*

if [ -d $TARGET_DCAM_DRV_DIR ]; then
	sudo cp -f $MAINDIR/uninstall_*.sh $TARGET_DCAM_DRV_DIR
fi
sudo cp -f $INSTALLER_DRV_PHNX_LDSO_DIR/*.conf $TARGET_LDSO_DIR

sudo /sbin/ldconfig

echo "Firebird Driver installed."

if [ $# -eq 0 ]; then
	echo "NOW RESTART COMPUTER."
fi

exit 0

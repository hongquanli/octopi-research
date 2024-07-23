#!/bin/bash

dcampath=(`/sbin/ldconfig -p | grep "libdcamapi.so"`)
#echo $dcampath
dcamlink=${dcampath[3]}

dir=(`readlink -f $dcamlink`)

dir="${dir%/*}/etc/"
echo $dir


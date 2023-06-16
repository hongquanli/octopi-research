#!/bin/bash

xhost +local:docker
sudo docker run -it --rm --runtime nvidia --env="DISPLAY" --net=host -v /dev:/dev --device=/dev/ttyACM0  -v ~/Documents:/Docs --privileged prakashlab_docker:drivers_perms

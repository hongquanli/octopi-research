#!/bin/bash
wget https://flir.netx.net/file/asset/54401/original/attachment/spinnaker_python-3.1.0.79-cp310-cp310-linux_x86_64.tar.gz
mkdir PySpin
tar -xvf spinnaker_python-3.1.0.79-cp310-cp310-linux_x86_64.tar.gz -C PySpin
python3 -m pip install --user PySpin/spinnaker_python-3.1.0.79-cp310-cp310-linux_x86_64.whl

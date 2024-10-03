#!/bin/bash
wget https://en.ids-imaging.com/files/downloads/ids-peak/software/linux-desktop/ids-peak_2.11.0.0-178_amd64.tgz
tar -xvzf ids-peak_2.11.0.0-178_amd64.tgz
sudo sh ids-peak_2.11.0.0-178_amd64/local/scripts/ids_install_udev_rule.sh
python3 -m pip install ids_peak_ipl
python3 -m pip install ids_peak
python3 -m pip install ids_peak_afl

# Define the content to add to .bashrc
content="
# IDS camera library paths
export LD_LIBRARY_PATH=\"$HOME/Desktop/octopi-research/software/drivers and libraries/ids/ids-peak_2.11.0.0-178_amd64/lib:\$LD_LIBRARY_PATH\"
export GENICAM_GENTL32_PATH=\"\$GENICAM_GENTL32_PATH:$HOME/Desktop/octopi-research/software/drivers and libraries/ids/ids-peak_2.11.0.0-178_amd64/lib/ids/cti\"
export GENICAM_GENTL64_PATH=\"\$GENICAM_GENTL64_PATH:$HOME/Desktop/octopi-research/software/drivers and libraries/ids/ids-peak_2.11.0.0-178_amd64/lib/ids/cti\"
"

# Append the content to .bashrc if it's not already there
if ! grep -qF "IDS camera library paths" ~/.bashrc; then
    echo "$content" >> ~/.bashrc
    echo "iDS peak library paths added to .bashrc"
else
    echo "iDS peak library paths already exist in .bashrc"
fi

# Source .bashrc to apply changes immediately
source ~/.bashrc

echo "Finished installation for iDS camera."

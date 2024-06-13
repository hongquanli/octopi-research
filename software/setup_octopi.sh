#!/bin/bash
# Setup script for octopi-software environment
# -------------------------------------------------------
# Usage
# -------------------------------------------------------
# brew install git (MacOS)
# sudo apt-get install git (Linux)
# 
# git clone git@github.com:sohamazing/octopi-software.git
# cd octopi-research/software
# chmod +x setup_octopi.sh
# ./setup_octopi.sh
# ./setup_octopi.sh --INSTALL_CUDA=True  (optional)
#
# conda activate octopi
# python main.py --simulation
# -------------------------------------------------------

# Detect Operating System
OS="$(uname -s)"
case "${OS}" in
    Linux*)     os=Linux;;
    Darwin*)    os=MacOS;;
    *)          os="UNKNOWN:${OS}"
esac

# Function to compare version numbers
version() {
    echo "$@" | awk -F. '{ printf("%d%03d%03d", $1,$2,$3); }'
}

# Determines and installs the best NVIDIA driver, with checks for specific versions
install_best_nvidia_driver() {
    if [ "${os}" == "Linux" ]; then
        echo "Checking current NVIDIA driver version..."
        local current_driver_version=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | cut -d '.' -f1 || echo "0")
        if [[ "$current_driver_version" -eq 550 || "$current_driver_version" -eq 535 || "$current_driver_version" -eq 545 ]]; then
            echo "Compatible NVIDIA driver version $current_driver_version is already installed."
            return
        fi
        
        echo "No compatible NVIDIA driver version found. Determining the best driver for installation..."
        # This example assumes ubuntu-drivers command is available and the system is Ubuntu
        local recommended_driver=$(ubuntu-drivers devices | grep 'recommended' | grep 'nvidia-driver' | awk '{print $3}')
        if [ -n "$recommended_driver" ]; then
            echo "Purging existing NVIDIA drivers..."
            sudo apt-get purge -y nvidia-*
            echo "Installing recommended NVIDIA driver: $recommended_driver"
            sudo apt-get install -y "$recommended_driver"
        else
            echo "No recommended NVIDIA driver found by `ubuntu-drivers devices`. Considering manual installation."
            # Manual installation of a driver if needed
            # sudo apt-get install -y nvidia-driver-550     ### uncomment to install version 550 manually
        fi
    else
        echo "NVIDIA driver installation is not applicable on ${os}. Skipping..."
    fi
}

# Installs CUDA Toolkit if not already installed after ensuring the NVIDIA driver is correctly installed
install_cuda_toolkit() {
    if [ "${os}" == "Linux" ]; then
        if dpkg -l | grep -q cuda-12; then
            echo "CUDA 12.x is already installed."
            return
        else
            echo "Installing CUDA 12.x..."
            if [ -f cuda-keyring_*.deb ]; then
                echo "Removing existing CUDA keyring package..."
                rm cuda-keyring_*.deb
            fi
            if dpkg -l | grep -q cuda-keyring; then
                echo "Removing previously installed CUDA keyring..."
                sudo dpkg --purge cuda-keyring
            fi
            wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
            sudo dpkg -i cuda-keyring_1.1-1_all.deb
            rm cuda-keyring_1.1-1_all.deb
            sudo apt-get install -y cuda-12
            echo "CUDA 12.x installation completed."
        fi
    else
        echo "CUDA Toolkit installation is not applicable on ${os}. Skipping..."
    fi
}

# Combines the steps to install CUDA and NVIDIA drivers
install_cuda_nvidia_linux() {
    if [ "${os}" == "Linux" ]; then
        # Check for Ubuntu 22.04 or adapt for other distributions
        if grep -q Ubuntu /etc/os-release; then
            if grep -q "22.04" /etc/os-release; then
                sudo apt-get update
                install_best_nvidia_driver
                install_cuda_toolkit
            else
                echo "This script is designed for Ubuntu 22.04. You are running a different version."
            fi
        else
            echo "This script is designed for Ubuntu 22.04. Skipping CUDA and NVIDIA driver installation."
        fi
    else
        echo "CUDA and NVIDIA driver installation is not applicable on ${os}. Skipping..."
    fi
}


# Creates and activates a Conda environment if it doesn't already exist
create_conda_env() {
    local env_name="octopi"
    local python_version="3.10"

    if conda info --envs | grep -qw "$env_name"; then
        echo "Conda environment '$env_name' already exists. Activating it..."
    else
        echo "Creating conda environment '$env_name' with Python $python_version..."
        conda create -y -n "$env_name" python="$python_version"
    fi
    eval "$(conda shell.bash hook)"
    conda activate "$env_name"
    echo "Conda environment '$env_name' activated."
}

# Installs required Python packages excluding PyTorch
install_python_packages() {
    echo "Installing Python packages..."
    pip install -U pip setuptools wheel numpy pandas scikit-learn \
                   PyQt5 pyqtgraph qtpy pyserial lxml==4.9.4 crc==1.3.0 \
                   opencv-python-headless opencv-contrib-python-headless \
                   dask_image imageio aicsimageio tifffile \
                   napari[all] napari-ome-zarr basicpy
}

# Installs PyTorch with CUDA support for Linux using Conda, updates JAX to a specific version based on the OS
install_conditional_packages() {
    echo "Installing conditional packages..."
    if [ "${os}" == "Linux" ]; then
        pip install cuda-python cupy-cuda12x
        conda install -y pytorch torchvision torchaudio cudatoolkit=12.1 -c pytorch -c nvidia
        pip install 'jax[cuda12_pip]==0.4.23' --find-links https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
    elif [ "${os}" == "MacOS" ]; then
        pip install torch torchvision torchaudio 
        pip install jax[cpu]==0.4.23
    fi
}

# Installs the Galaxy Camera software
install_galaxy_camera() {
    echo "Installing Galaxy Camera software..."
    cd drivers\ and\ libraries/daheng\ camera/Galaxy_Linux-x86_Gige-U3_32bits-64bits_1.2.1911.9122/
    ./Galaxy_camera.run
    cd ../Galaxy_Linux_Python_1.0.1905.9081/api
    python3 setup.py build
    python3 setup.py install
}

# Main script execution
if [ ! -d "cache" ]; then
    echo "Creating cache directory..."
    mkdir cache
else
    echo "Cache directory already exists."
fi
create_conda_env
if [ "$INSTALL_CUDA" == "True" ]; then
    install_cuda_nvidia_linux  # Check and install CUDA/NVIDIA drivers if necessary
fi
install_python_packages
install_conditional_packages  # Install PyTorch, JAX, and related CUDA packages
install_galaxy_camera
echo "Installation completed successfully."
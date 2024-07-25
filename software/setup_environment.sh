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
# chmod +x setup_environment.sh
# ./setup_environment.sh
# ./setup_environment.sh --INSTALL_CUDA=True --CUDA_VERSION=12-5 (optional)
# 
# conda activate octopi
# python main.py --simulation
# -------------------------------------------------------

set -e

# Set default values
install_cuda="False"
cuda_version="12-5"

# Parse command-line arguments
for i in "$@"; do
    case $i in
        --INSTALL_CUDA=True)
        install_cuda="True"
        shift
        ;;
        --INSTALL_CUDA=False)
        install_cuda="False"
        shift
        ;;
        --CUDA_VERSION=*)
        cuda_version="${i#*=}"
        shift
        ;;
        *)
        # unknown option
        ;;
    esac
done

# Detect Operating System
os="$(uname -s)"
case "${os}" in
    Linux*)     os=Linux;;
    Darwin*)    os=MacOS;;
    *)          os="UNKNOWN:${os}"
esac

# Removes all existing NVIDIA drivers and CUDA installations if needed
remove_existing_drivers_and_cuda() {
    echo "Removing existing NVIDIA drivers and CUDA installations..."
    sudo apt-get purge -y 'nvidia-*'
    sudo apt-get purge -y cuda*
    sudo apt-get autoremove -y
    sudo apt-get clean
    sudo rm -rf /usr/local/cuda*
    sudo rm -rf /usr/local/cuda-*
    sudo rm -rf /usr/local/nvidia*
}

# Installs the NVIDIA driver
install_nvidia_drivers() {
    if [ "${os}" == "Linux" ]; then
        echo "Checking current NVIDIA driver version..."
        if command -v nvidia-smi &> /dev/null; then
            local current_driver_version=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | cut -d '.' -f1 || echo "0")
            # Check if the current driver version is 535 or higher
            if [ "$current_driver_version" -ge 535 ]; then
                echo "Compatible NVIDIA driver version $current_driver_version is already installed."
                return
            fi
        fi

        echo "No compatible NVIDIA driver version found. Installing the latest stable NVIDIA driver..."
        remove_existing_drivers_and_cuda
        sudo apt-get update

        # Install the NVIDIA driver
        sudo apt-get install -y cuda-drivers || { echo "Failed to install NVIDIA driver"; exit 1; }
    else
        echo "NVIDIA driver installation is not applicable on ${os}. Skipping..."
    fi
}

# Installs the CUDA toolkit
install_cuda_toolkit() {
    echo "Installing CUDA toolkit version $cuda_version..."
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
    sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600

    wget https://developer.download.nvidia.com/compute/cuda/12.5.0/local_installers/cuda-repo-ubuntu2204-12-5-local_12.5.0-555.42.02-1_amd64.deb
    sudo dpkg -i cuda-repo-ubuntu2204-12-5-local_12.5.0-555.42.02-1_amd64.deb
    sudo cp /var/cuda-repo-ubuntu2204-12-5-local/cuda-*-keyring.gpg /usr/share/keyrings/

    sudo apt-get update
    sudo apt-get -y install cuda-toolkit-12-5 || { echo "Failed to install CUDA toolkit"; exit 1; }

    # Ensure CUDA directory exists before setting environment variables
    if [ -d "/usr/local/cuda-12.5" ]; then
        echo "Setting environment variables for CUDA"
        export PATH=/usr/local/cuda-12.5/bin${PATH:+:${PATH}}
        export LD_LIBRARY_PATH=/usr/local/cuda-12.5/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
    else
        echo "CUDA directory /usr/local/cuda-12.5 does not exist"
        exit 1
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
                   napari[all] napari-ome-zarr basicpy || { echo "Failed to install Python packages"; exit 1; }
}

# Installs PyTorch with CUDA support for Linux using pip, updates JAX to a specific version based on the OS
install_conditional_packages() {
    echo "Installing conditional packages..."
    if [ "${os}" == "Linux" ]; then
        pip install cuda-python cupy-cuda12x || { echo "Failed to install cuda-python or cupy-cuda12x"; exit 1; }
        pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu125 || { echo "Failed to install PyTorch"; exit 1; }
        pip install 'jax[cuda12_pip]==0.4.23' --find-links https://storage.googleapis.com/jax-releases/jax_cuda_releases.html || { echo "Failed to install JAX"; exit 1; }
    elif [ "${os}" == "MacOS" ]; then
        pip install torch torchvision torchaudio || { echo "Failed to install PyTorch"; exit 1; }
        pip install 'jax[cpu]==0.4.23' || { echo "Failed to install JAX"; exit 1; }
    fi
}

# Installs the Galaxy Camera software
install_galaxy_camera() {
    echo "Installing Galaxy Camera software..."
    cd "drivers and libraries/daheng camera/Galaxy_Linux-x86_Gige-U3_32bits-64bits_1.2.1911.9122/"
    ./Galaxy_camera.run || { echo "Failed to install Galaxy Camera software"; exit 1; }
    cd ../Galaxy_Linux_Python_1.0.1905.9081/api
    python3 setup.py build || { echo "Failed to build Galaxy Camera Python API"; exit 1; }
    python3 setup.py install || { echo "Failed to install Galaxy Camera Python API"; exit 1; }
}

# Main script execution
if [ ! -d "cache" ]; then
    echo "Creating cache directory..."
    mkdir cache
else
    echo "Cache directory already exists."
fi
create_conda_env
if [ "$install_cuda" == "True" ]; then
    install_nvidia_drivers  # Check and install the latest stable NVIDIA driver
    install_cuda_toolkit    # Install the specified CUDA toolkit
fi
install_python_packages
install_conditional_packages  # Install PyTorch, JAX, and related CUDA packages
install_galaxy_camera
echo "Installation completed successfully."

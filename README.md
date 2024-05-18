# Squid Control

The Squid Control software is a Python package that provides a simple interface to control the Squid microscope. The software is designed to be used with the Squid microscope (made by Cephla Inc.).

## Installation and Usage

See the [installation guide](./docs/installation.md) for instructions on how to install and use the software.

### Usage

To run the software, use the following command:
```
python -m squid_control --config HCS_v2
```

If you want to use a different configuration file, you can specify the path to the configuration file:
```
python -m squid_control --config /home/user/configuration_HCS_v2.ini
```

To start simulation mode, use the following command:
```
python -m squid_control --config HCS_v2 --simulation
```

To load a custom multipoint function:
```
python -m squid_control --config HCS_v2 --simulation --multipoint-function=./my_multipoint_custom_script_entry.py:multipoint_custom_script_entry
```

## About

<img style="width:60px;" src="./docs/assets/cephla_logo.svg"> Cephla Inc. 




## Note

The current branch is a frok from https://github.com/hongquanli/octopi-research/ at the following commit:
```
commit dbb49fc314d82d8099d5e509c0e1ad9a919245c9 (HEAD -> master, origin/master, origin/HEAD)
Author: Hongquan Li <hqlisu@gmail.com>
Date:   Thu Apr 4 18:07:51 2024 -0700

    add laser af characterization mode for saving images from laser af camera
```

How to make pypi work:
 - Register on pypi.org
 - Create a new token in the account settings
 - In the repository setting, create a new secret called `PYPI_API_TOKEN` and paste the token in the value field
 - Then, if you want to manually publish a new pypi package, go to actions, select the `Publish to PyPi` workflow, and click on `Run workflow`.


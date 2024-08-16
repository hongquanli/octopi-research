# Squid (formerly octopi-research)

![alt text](https://i.imgur.com/Gjwh02y.png)

## Introduction
Squid (Simplifying Quantitive Imaging Development and Deployment) provides a full suite of hardware and software components for rapidly configuring high-performance microscopes tailored to users' applications with reduced cost, effort and turnaround time. Besides increasing accessibility of research microscopes and available microscope hours to labs, it is also designed to simplify development and dissemination of new or otherwise advanced microscopy techniques.

Applications include
- slide scanner for digital pathology
- time lapse imaging with 2D or 3D tiling
- spatial omics that involves multicolor and multi-round imaging
- tracking microscopy
- computational microscopy, including label free microscopy using phase/polarization/reflectance + deep learning
- super resolution microscopy
- light sheet microscopy

## Assets
- main software repo: [GitHub](https://github.com/hongquanli/octopi-research) (this repo)
- tracking software repo: [GitHub](https://github.com/prakashlab/squid-tracking)
- CAD models/photos of assembled squids: [Google Drive](https://drive.google.com/drive/folders/1JdVp34HtERGpBCBlFX6jFDwMUdeBLCEx?usp=sharing)
- BOM for the microscope, including CAD files for CNC machining: [link](https://docs.google.com/spreadsheets/d/1WA64HySj9I7XROtTXuaRvjlbhHXRGspvoxb_20CWDR8/edit?usp=drivesdk)
- BOM for the multicolor laser engine: [link](https://docs.google.com/spreadsheets/d/1hEM6PsxZPTp1LY3cpxUJOS3Q1YLQN-xniF33ZddFj9U/edit#gid=1175873468)
- BOM for the control panel: [link](https://docs.google.com/spreadsheets/d/1z2HjibIG9PHffiDsbuzQXmvf2gSFMduHrXkPwDbcXRY/edit?usp=sharing)

## Early Results, Related Work and Possible Applications
Refer to our website: www.squid-imaging.org

## References
[1] Hongquan Li, Deepak Krishnamurthy, Ethan Li, Pranav Vyas, Nibha Akireddy, Chew Chai, Manu Prakash, "**Squid: Simplifying Quantitative Imaging Platform Development and Deployment**." BiorXiv [ link | [website](https://squid-imaging.org)]

For scale-free vertical tracking microscopy, check out our work at:

[2] Deepak Krishnamurthy, Hongquan Li, François Benoit du Rey, Pierre Cambournac, Adam G. Larson, Ethan Li, and Manu Prakash. "**Scale-free vertical tracking microscopy.**" Nature Methods 17, no. 10 (2020): 1040-1051. [ [link](https://www.nature.com/articles/s41592-020-0924-7) | [website](https://gravitymachine.org) ]

## Acknowledgement
The Squid software was developed with structuring inspiration from [Tempesta-RedSTED](https://github.com/jonatanalvelid/Tempesta-RedSTED). The laser engine is inspired by [https://github.com/ries-lab/LaserEngine](https://github.com/ries-lab/LaserEngine). 

## Software Instructions
The microscope is controled by an Arduino Due and a computer running Ubuntu. The computer can be one of the Nvidia Jetson platforms (e.g. Jetson Nano, Jetson Xavier NX) or a regular laptop/workstation. Instructions for using the firmware and software can be found in the respective folders.

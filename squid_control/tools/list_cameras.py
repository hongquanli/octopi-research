# version:1.0.1808.9101
import control.gxipy as gx

def main():
    
    # create a device manager
    device_manager = gx.DeviceManager()
    dev_num, dev_info_list = device_manager.update_device_list()
    if dev_num is 0:
        print("Number of enumerated devices is 0")
        return
    for i in range(dev_num):
        print(dev_info_list[i])

if __name__ == "__main__":
    main()

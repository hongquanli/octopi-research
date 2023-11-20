import os
import stat
def create_desktop_shortcut_simulation(directory_path, script_name):
    squid_suffix = script_name.replace("main_","")
    icon_path = os.path.join(directory_path, "icon/cephla_logo.svg")
    if squid_suffix != "main" and squid_suffix != "":
        shortcut_content = f'''\
[Desktop Entry]
Name=Squid_{squid_suffix}_simulation
Icon={icon_path}
Exec=gnome-terminal --working-directory="{directory_path}" -e "/usr/bin/env python3 {directory_path}/{script_name}.py --simulation"
Type=Application
Terminal=true
'''
    else:
         shortcut_content = f'''\
[Desktop Entry]
Name=Squid_simulation
Icon={icon_path}
Exec=gnome-terminal --working-directory="{directory_path}" -e "/usr/bin/env python3 {directory_path}/{script_name}.py --simulation"
Type=Application
Terminal=true
'''

    if squid_suffix != "main" and squid_suffix != "":
        desktop_path_base = f'~/Desktop/Squid_{squid_suffix}_simulation.desktop'
    else:
        desktop_path_base = f'~/Desktop/Squid_simulation.desktop'
    desktop_path = os.path.expanduser(desktop_path_base)
    with open(desktop_path, 'w') as shortcut_file:
        shortcut_file.write(shortcut_content)
    os.chmod(desktop_path, stat.S_IRWXU)
    return desktop_path



def create_desktop_shortcut(directory_path, script_name):
    squid_suffix = script_name.replace("main_","")
    icon_path = os.path.join(directory_path, "icon/cephla_logo.svg")
    if squid_suffix != "main" and squid_suffix != "":
        shortcut_content = f'''\
[Desktop Entry]
Name=Squid_{squid_suffix}
Icon={icon_path}
Exec=gnome-terminal --working-directory="{directory_path}" -e "/usr/bin/env python3 {directory_path}/{script_name}.py"
Type=Application
Terminal=true
'''
    else:
         shortcut_content = f'''\
[Desktop Entry]
Name=Squid
Icon={icon_path}
Exec=gnome-terminal --working-directory="{directory_path}" -e "/usr/bin/env python3 {directory_path}/{script_name}.py"
Type=Application
Terminal=true
'''

    if squid_suffix != "main" and squid_suffix != "":
        desktop_path_base = f'~/Desktop/Squid_{squid_suffix}.desktop'
    else:
        desktop_path_base = f'~/Desktop/Squid.desktop'
    desktop_path = os.path.expanduser(desktop_path_base)
    with open(desktop_path, 'w') as shortcut_file:
        shortcut_file.write(shortcut_content)
    os.chmod(desktop_path, stat.S_IRWXU)
    return desktop_path

def main():
    # Prompt for directory path and script name
    directory_path = input('Enter the directory path to octopi-research/software (default: current directory): ') or os.getcwd()
    script_name = input('Enter the main script name under octopi-research/software (without .py extension): ')

    simulation = input('Is this for launching in simulation mode? [NO/yes]: ') or False
    if str(simulation).lower() == 'yes':
        simulation = True
    else:
        simulation = False

    # Create desktop shortcut
    if not simulation:
        desktop_path = create_desktop_shortcut(directory_path, script_name)
    else:
        desktop_path = create_desktop_shortcut_simulation(directory_path, script_name)
    print(f'Desktop shortcut created at: {desktop_path}')

if __name__ == '__main__':
    main()


import os
import stat
def create_desktop_shortcut(directory_path, script_name):
    shortcut_content = f'''\
[Desktop Entry]
Name=Squid
Exec=gnome-terminal --working-directory="{directory_path}" -e "/usr/bin/env python3 {directory_path}/{script_name}.py"
Type=Application
Terminal=true
'''

    desktop_path = os.path.expanduser('~/Desktop/Squid.desktop')
    with open(desktop_path, 'w') as shortcut_file:
        shortcut_file.write(shortcut_content)
    os.chmod(desktop_path, stat.S_IRWXU)
    return desktop_path

def main():
    # Prompt for directory path and script name
    directory_path = input('Enter the directory path (default: current directory): ') or os.getcwd()
    script_name = input('Enter the script name (without .py extension): ')

    # Create desktop shortcut
    desktop_path = create_desktop_shortcut(directory_path, script_name)
    print(f'Desktop shortcut created at: {desktop_path}')

if __name__ == '__main__':
    main()


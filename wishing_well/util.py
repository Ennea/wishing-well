import logging
import os
import socket
import subprocess
import sys
import tkinter
import webbrowser
import winreg
import psutil
from pathlib import Path
from tkinter import ttk
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


def get_data_path():
    if sys.platform == 'win32':
        path = Path(os.environ['APPDATA']) / 'wishing-well'
    else:
        show_error('Wishing Well only supports Windows.')

    # create dir if it does not yet exist
    if not path.exists():
        path.mkdir(parents=True)

    # path exists, but is a file
    if not path.is_dir():
        show_error(f'{path} already exists, but is a file.')

    return path

def get_cache_path():
    try:
        handle = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Genshin Impact',
                                    access=winreg.KEY_WOW64_64KEY | winreg.KEY_READ)
        path = winreg.QueryValueEx(handle, 'InstallPath')[0]
        handle.Close()

        # create a copy of the file so we can also access it while genshin is running.
        # python cannot do this without raising an error, and neither can the default
        # windows copy command, so we instead delegate this task to powershell's Copy-Item
        try:
            path = Path(path) / 'Genshin Impact game/GenshinImpact_Data/webCaches/Cache/Cache_Data/data_2'
            copy_path = get_data_path() / 'data_2'
            subprocess.check_output(f'powershell.exe -Command "Copy-Item \'{path}\' \'{copy_path}\'"', shell=True)
        except (FileNotFoundError, subprocess.CalledProcessError):

            # if that fails, try getting the install path by looking for a running instance of Genshin.
            try:
                for p in psutil.process_iter():
                    if p.name() == "GenshinImpact.exe":
                        path = p.exe().replace("GenshinImpact.exe","GenshinImpact_Data/webCaches/Cache/Cache_Data/data_2")
                        copy_path = get_data_path() / 'data_2'
                        subprocess.check_output(f'powershell.exe -Command "Copy-Item \'{path}\' \'{copy_path}\'"', shell=True)
            except:
                return None

        return copy_path
    except (OSError, FileNotFoundError):
        return None

def set_up_logging():
    log_level = logging.DEBUG if len(sys.argv) > 1 and sys.argv[1] == '--debug' else logging.INFO
    log_format = '%(asctime)s %(levelname)s: %(message)s'
    logging.basicConfig(filename=(get_data_path() / 'wishing-well.log'), format=log_format, level=log_level)

    # add a stream handler for log output to stdout
    root_logger = logging.getLogger()
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    formatter = logging.Formatter(log_format)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    logging.info('Starting Wishing Well')

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(( 'localhost', port ))
            return False
        except OSError:
            return True

def get_usable_port():
    port = 39000
    while is_port_in_use(port):
        # check if wishing well is already running on this port
        try:
            with urlopen(f'http://localhost:{port}/wishing-well', timeout=0.1) as _:
                pass
            webbrowser.open(f'http://localhost:{port}')
            logging.info('Wishing Well is already running on port %d. Quitting', port)
            sys.exit(1)
        except (URLError, HTTPError):
            port += 1
            if port == 39010:
                show_error('No suitable port found.')

    return port

def show_error(message):
    logging.error(message)

    root = tkinter.Tk()
    root.title('Wishing Well')
    root.minsize(300, 0)
    root.resizable(False, False)
    root.iconphoto(False, tkinter.PhotoImage(file=Path(sys.path[0]) / 'icon.png'))

    frame = ttk.Frame(root, padding=10)
    frame.pack()
    ttk.Label(frame, text=message).pack()
    ttk.Frame(frame, height=5).pack()
    ttk.Button(frame, text='Okay', command=root.destroy).pack()

    # center the window
    window_width = root.winfo_reqwidth()
    window_height = root.winfo_reqheight()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry('+{}+{}'.format(int(screen_width / 2 - window_width / 2), int(screen_height / 2 - window_height / 2)))

    root.mainloop()
    logging.info('Quitting')
    sys.exit(1)

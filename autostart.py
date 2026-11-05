"""Per-user app lifecycle watcher. No administrator privileges needed."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import sys
import time

HANDLES=[]


def singleton(name):
    api=C.WinDLL('kernel32',use_last_error=True)
    api.CreateMutexW.argtypes=[C.c_void_p,W.BOOL,W.LPCWSTR]
    api.CreateMutexW.restype=W.HANDLE
    handle=api.CreateMutexW(None,False,'Local\\'+name)
    if not handle:raise C.WinError(C.get_last_error())
    exists=C.get_last_error()==183
    HANDLES.append(handle)
    return not exists


def app_open():
    u=C.WinDLL('user32',use_last_error=True)
    k=C.WinDLL('kernel32',use_last_error=True)
    callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    u.EnumWindows.argtypes=[callback,W.LPARAM]
    u.IsWindowVisible.argtypes=[W.HWND]
    u.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    u.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
    k.CloseHandle.argtypes=[W.HANDLE]
    found=[]
    @callback
    def visit(hwnd,_):
        if not u.IsWindowVisible(hwnd):return True
        title=C.create_unicode_buffer(512)
        u.GetWindowTextW(hwnd,title,512)
        if title.value not in ('ChatGPT','Codex'):return True
        pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(pid))
        process=k.OpenProcess(0x1000,False,pid.value)
        if not process:return True
        try:
            path=C.create_unicode_buffer(32768);size=W.DWORD(32768)
            if k.QueryFullProcessImageNameW(process,0,path,C.byref(size)) and Path(path.value).name.lower() in ('chatgpt.exe','codex.exe'):
                found.append(pid.value)
        finally:k.CloseHandle(process)
        return True
    u.EnumWindows(visit,0)
    return bool(found)


def pythonw():return str(Path(sys.executable).with_name('pythonw.exe'))


def watch():
    if not singleton('arizdot.watcher'):return
    was_open=False
    while True:
        opened=app_open()
        if opened and not was_open:
            subprocess.Popen([pythonw(),str(Path(__file__).with_name('arizdot.py'))],creationflags=subprocess.CREATE_NO_WINDOW)
        # Closing arizdot manually does not respawn it during the same app session.
        was_open=opened
        time.sleep(1)


def startup_file():
    return Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup/arizdot.vbs'


def install():
    path=startup_file()
    path.parent.mkdir(parents=True,exist_ok=True)
    command='"'+pythonw()+'" "'+str(Path(__file__).resolve())+'" --watch'
    script='Set shell = CreateObject("WScript.Shell")\r\nshell.Run "'+command.replace('"','""')+'", 0, False\r\n'
    path.write_bytes(script.encode('utf-16'))
    subprocess.Popen([pythonw(),str(Path(__file__).resolve()),'--watch'],creationflags=subprocess.CREATE_NO_WINDOW)
    print('arizdot autostart installed for this user')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install',action='store_true')
    parser.add_argument('--remove',action='store_true')
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.install:install()
    elif args.remove:
        startup_file().unlink(missing_ok=True)
        print('Autostart disabled for future logins; current watcher exits at sign-out')
    elif args.watch:watch()
    elif args.check:print(dict(app_open=app_open(),startup_installed=startup_file().exists()))

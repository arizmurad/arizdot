"""Check, or explicitly start, the optional official Kaggle account login."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import re


def redact_callback(line):
    return re.sub(r'([?&]code=)[^&\s]+',r'\1[redacted]',line)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--login',action='store_true');args=parser.parse_args()
    from kaggle_remote import credentials_present
    installed=importlib.util.find_spec('kaggle') is not None
    if not args.login:
        print(json.dumps(dict(client_installed=installed,credentials_present=credentials_present(),connected=False,check='local registration only; no account request sent')));return 0
    if not installed:
        subprocess.run([sys.executable,'-m','pip','install','-r',str(Path(__file__).with_name('requirements-kaggle.txt'))],check=True)
    print('Opening the official Kaggle sign-in. Complete its permission screen yourself.\nThe official CLI requests resources.admin:* account scope. arizdot uses only read/status/log calls.\nNo calculation will be launched, stopped or resubmitted. Keep credentials private.',flush=True)
    executable=Path(sys.executable).with_name('kaggle.exe')
    process=subprocess.Popen([str(executable),'auth','login'],stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
    for line in process.stderr:sys.stderr.write(redact_callback(line))
    return process.wait()


if __name__=='__main__':raise SystemExit(main())

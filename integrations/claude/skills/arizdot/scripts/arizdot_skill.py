import subprocess
import sys
import os
from bridge import app_root


if __name__=='__main__':
    args=sys.argv[1:] or ['start']
    if args[0]=='start' and '--cwd' not in args:args+=['--cwd',os.getcwd()]
    raise SystemExit(subprocess.run([sys.executable,str(app_root()/'control.py'),*args]).returncode)

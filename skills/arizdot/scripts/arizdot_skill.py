"""Bridge from the installed skill link to the desktop application."""
from pathlib import Path
import json
import subprocess
import sys


def app_root():
    for parent in Path(__file__).resolve().parents:
        if (parent/'control.py').is_file() and (parent/'arizdot.py').is_file():return parent
    marker=Path(__file__).resolve().parents[1]/'.arizdot-link.json'
    try:root=Path(json.loads(marker.read_text(encoding='utf-8'))['app_root'])
    except (OSError,ValueError,KeyError):raise SystemExit('arizdot registration is missing; run the Codex installer again')
    if not (root/'control.py').is_file() or not (root/'arizdot.py').is_file():raise SystemExit('ariztools was moved; reinstall the Codex integration')
    return root


def main():
    root=app_root()
    python=root/'.venv/Scripts/python.exe'
    if not python.is_file():python=Path(sys.executable)
    args=sys.argv[1:] or ['start']
    result=subprocess.run([str(python),str(root/'control.py'),*args])
    raise SystemExit(result.returncode)


if __name__=='__main__':main()

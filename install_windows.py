"""One-time Windows setup for the Codex, Claude, or combined arizdot package."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Check the launcher without installing anything')
    parser.add_argument('--target',choices=('codex','claude','both'),default=None)
    args=parser.parse_args()
    if os.name!='nt':
        print('This arizdot preview requires Windows 10/11.');return 1
    if sys.version_info<(3,11):
        print('Install Python 3.11 or newer, then run Install-arizdot.cmd again.');return 1
    if args.check:
        print('Launcher OK: Windows, Python '+sys.version.split()[0]);return 0
    profile=ROOT/'PACKAGE.json'
    target=args.target or (json.loads(profile.read_text(encoding='utf-8')).get('target','both') if profile.exists() else 'both')
    if target not in ('codex','claude','both'):print('Invalid package target.');return 1
    python=ROOT/'.venv/Scripts/python.exe'
    try:
        if not python.exists():
            print('Creating a local Python environment...',flush=True)
            subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')],cwd=ROOT,check=True)
        print('Installing arizdot dependencies (internet required)...',flush=True)
        requirements='requirements.txt' if target=='codex' else 'requirements-claude.txt'
        subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/requirements)],cwd=ROOT,check=True)
        if target in ('codex','both'):
            print('Registering arizdot for Codex...',flush=True)
            subprocess.run([str(python),str(ROOT/'install_codex.py')],cwd=ROOT,check=True)
        if target in ('claude','both'):
            print('Registering arizdot for Claude Code and Desktop...',flush=True)
            subprocess.run([str(python),str(ROOT/'install_claude.py'),'--code','--desktop'],cwd=ROOT,check=True)
        result=subprocess.run([str(python),str(ROOT/'doctor.py')],cwd=ROOT,check=True,capture_output=True,text=True)
        health=json.loads(result.stdout)
        required=['native_indicator_supported','pillow','tkinter']
        if target in ('codex','both'):required+=['codex_skill_installed']
        if target in ('claude','both'):required+=['mcp','claude_skill_installed','claude_desktop_config_valid']
        if not all(health.get(key) for key in required):
            print(result.stdout);print('Installation needs attention. See the diagnostics above.');return 1
    except (OSError,subprocess.CalledProcessError,ValueError) as error:
        print('Setup stopped: '+str(error))
        print('Keep this folder and check your Python installation and internet connection.');return 1
    print('\nInstalled. Restart your assistant or open a new local session.')
    if target in ('codex','both'):print('Codex: select arizdot from the skill picker, or type $arizdot.')
    if target in ('claude','both'):
        print('Claude Code: /arizdot')
        print('Desktop Chat: / -> Connectors -> Add from arizdot -> arizdot')
    print('Keep this extracted ariztools folder in place. Autostart was not enabled.')
    return 0


if __name__=='__main__':raise SystemExit(main())

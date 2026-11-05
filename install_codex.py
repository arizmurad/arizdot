"""Register only arizdot-owned local Codex skill files; no admin rights needed."""
import argparse
import json
import os
from pathlib import Path
import shutil
from activation import write_json
from install_claude import digest,load_object

APP=Path(__file__).resolve().parent
FILES=('SKILL.md','agents/openai.yaml','scripts/arizdot_skill.py')


def skill_path(home=None,legacy=False):
    explicit=home is not None
    home=Path(home or Path.home())
    old=(home/'.codex' if explicit else Path(os.environ.get('CODEX_HOME',home/'.codex')))/'skills/arizdot'
    if legacy:return old
    # Keep an existing source junction working without showing two commands.
    if old.is_dir() and old.resolve()==(APP/'skills/arizdot').resolve():return old
    return home/'.agents/skills/arizdot'


def install(home=None,legacy=False):
    target=skill_path(home,legacy)
    source=APP/'skills/arizdot'
    if target.is_dir() and target.resolve()==source.resolve():return str(target)
    marker=target/'.arizdot-link.json'
    if target.exists() and not marker.exists():raise ValueError('An unmanaged arizdot Codex skill exists; it was not overwritten')
    if marker.exists() and Path(load_object(marker).get('app_root','')).resolve()!=APP:raise ValueError('A Codex registration from another ariztools folder exists; remove that registration before relocating')
    for name in FILES:
        path=target/name;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/name,path)
    write_json(marker,dict(app_root=str(APP),files={name:digest(target/name) for name in FILES}))
    return str(target)


def uninstall(home=None,legacy=False):
    target=skill_path(home,legacy);marker=target/'.arizdot-link.json'
    value=load_object(marker)
    if not value or Path(value.get('app_root','')).resolve()!=APP:raise ValueError('No owned copied Codex registration found; source junctions are left intact')
    for name,sha in value.get('files',{}).items():
        if name not in FILES:raise ValueError('Unexpected owned file entry')
        path=target/name
        if path.exists() and digest(path)==sha:path.unlink()
    marker.unlink()
    for folder in (target/'agents',target/'scripts',target):
        try:folder.rmdir()
        except OSError:pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy',action='store_true',help='Use CODEX_HOME/skills for an older desktop installation')
    parser.add_argument('--remove',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if args.dry_run:print(json.dumps(dict(codex=str(skill_path(legacy=args.legacy)))));return
    try:
        result=uninstall(legacy=args.legacy) if args.remove else install(legacy=args.legacy)
        print(json.dumps(dict(codex=result,removed=args.remove)));return 0
    except (OSError,ValueError) as error:
        print(json.dumps(dict(error=str(error))));return 1


if __name__=='__main__':raise SystemExit(main())

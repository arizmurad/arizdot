"""Install only arizdot-owned Claude integration entries; preserve other tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from activation import write_json

APP=Path(__file__).resolve().parent


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_object(path):
    if not path.exists():return {}
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value,dict):raise ValueError('Configuration must be a JSON object')
    return value


def interpreter():
    candidate=APP/'.venv/Scripts/python.exe'
    return candidate if candidate.exists() else Path(sys.executable).resolve()


def install_code(home=None,python=None):
    home=Path(home or Path.home());python=Path(python or interpreter()).resolve()
    target=home/'.claude/skills/arizdot'
    source=APP/'integrations/claude/skills/arizdot'
    marker=target/'.arizdot-link.json'
    if target.exists() and not marker.exists():raise ValueError('An unmanaged arizdot Claude skill already exists; it was not overwritten')
    if marker.exists() and Path(load_object(marker).get('app_root','')).resolve()!=APP:raise ValueError('An arizdot skill from another folder already exists')
    target.mkdir(parents=True,exist_ok=True)
    owned={}
    text=(source/'SKILL.md').read_text(encoding='utf-8')
    # Exec-form hooks avoid shell quoting; generated body quotes the same path.
    text=text.replace('command: python','command: '+json.dumps(str(python)))
    def literal(value):return "'"+str(value).replace("'","''")+"'"
    for action in ('start','status','report','job-register'):
        template='python "${CLAUDE_SKILL_DIR}/scripts/arizdot_skill.py" '+action+' --provider claude --session "${CLAUDE_SESSION_ID}"'
        command='& '+literal(python)+' '+literal(target/'scripts/arizdot_skill.py')+' '+action+" --provider claude --session '${CLAUDE_SESSION_ID}'"
        text=text.replace(template,command)
    # Hook fields have different substitutions from skill markdown. Resolve the
    # observer path here instead of depending on an unsupported hook variable.
    text=text.replace('args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]','args: ['+json.dumps(str(target/'scripts/hook.py'))+']')
    (target/'SKILL.md').write_text(text,encoding='utf-8')
    owned['SKILL.md']=digest(target/'SKILL.md')
    for filename in ('bridge.py','hook.py','arizdot_skill.py'):
        (target/'scripts').mkdir(exist_ok=True)
        shutil.copy2(source/'scripts'/filename,target/'scripts'/filename)
        owned['scripts/'+filename]=digest(target/'scripts'/filename)
    write_json(marker,dict(app_root=str(APP),files=owned))
    return str(target)


def desktop_config_path(appdata=None,localappdata=None):
    """Find migrated MSIX data before legacy Roaming data; never move preferences."""
    if appdata is not None:
        return Path(appdata)/'Claude/claude_desktop_config.json'
    local=Path(localappdata or os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))
    migrated=local/'Claude-Data/claude_pzs8sxrjxfjjc/claude_desktop_config.json'
    if migrated.is_file():return migrated
    packaged=local/'Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/claude_desktop_config.json'
    if packaged.is_file():return packaged
    return Path(os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))/'Claude/claude_desktop_config.json'


def install_desktop(appdata=None,python=None):
    python=Path(python or interpreter()).resolve()
    path=desktop_config_path(appdata)
    config=load_object(path)
    servers=config.setdefault('mcpServers',{})
    if not isinstance(servers,dict):raise ValueError('mcpServers must be an object')
    entry=dict(command=str(python),args=[str(APP/'mcp_server.py')])
    previous=servers.get('arizdot')
    if previous is not None and previous!=entry:raise ValueError('A different arizdot MCP entry exists; it was not overwritten')
    if path.exists() and previous!=entry:
        backup=APP/'config/backups'/('claude-desktop-'+str(time.time_ns())+'.json')
        backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,backup)
    servers['arizdot']=entry
    write_json(path,config)
    return str(path)


def uninstall_code(home=None):
    target=Path(home or Path.home())/'.claude/skills/arizdot'
    marker=target/'.arizdot-link.json'
    value=load_object(marker)
    if not value or Path(value.get('app_root','')).resolve()!=APP:raise ValueError('No owned Claude skill installation found')
    allowed={'SKILL.md','scripts/bridge.py','scripts/hook.py','scripts/arizdot_skill.py'}
    for name,sha in value.get('files',{}).items():
        if name not in allowed:raise ValueError('Unexpected owned file entry')
        path=target/name
        if path.exists() and digest(path)==sha:path.unlink()
    marker.unlink()
    for folder in (target/'scripts',target):
        try:folder.rmdir()
        except OSError:pass


def uninstall_desktop(appdata=None,python=None):
    path=desktop_config_path(appdata)
    value=load_object(path);servers=value.get('mcpServers',{})
    expected=dict(command=str(Path(python or interpreter()).resolve()),args=[str(APP/'mcp_server.py')])
    if servers.get('arizdot')!=expected:raise ValueError('MCP entry changed; it was not removed')
    del servers['arizdot'];write_json(path,value)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code',action='store_true');p.add_argument('--desktop',action='store_true')
    p.add_argument('--remove',action='store_true');p.add_argument('--dry-run',action='store_true')
    args=p.parse_args()
    if not args.code and not args.desktop:p.error('Choose --code and/or --desktop')
    if args.dry_run:
        print(json.dumps(dict(code=str(Path.home()/'.claude/skills/arizdot') if args.code else None,desktop=str(desktop_config_path()) if args.desktop else None,python=str(interpreter()))));return
    result={}
    if args.code:result['code']=(uninstall_code() if args.remove else install_code())
    if args.desktop:result['desktop']=(uninstall_desktop() if args.remove else install_desktop())
    print(json.dumps(result))


if __name__=='__main__':main()

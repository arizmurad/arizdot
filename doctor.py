"""Read-only local installation diagnostics; never launches either assistant."""
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
from install_claude import desktop_config_path
from install_codex import skill_path


def diagnostics():
    root=Path(__file__).resolve().parent
    appdata=Path(os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))
    config=desktop_config_path()
    try:
        desktop=json.loads(config.read_text(encoding='utf-8-sig')).get('mcpServers',{}).get('arizdot')
        desktop_config_valid=bool(desktop and Path(desktop['command']).is_file() and Path(desktop['args'][0]).is_file())
    except (OSError,ValueError,KeyError,TypeError):desktop_config_valid=False
    return dict(platform=platform.system(),native_indicator_supported=os.name=='nt',python=sys.version.split()[0],
        pillow=bool(importlib.util.find_spec('PIL')),tkinter=bool(importlib.util.find_spec('tkinter')),mcp=bool(importlib.util.find_spec('mcp')),
        claude_cli=shutil.which('claude'),claude_skill_installed=(Path.home()/'.claude/skills/arizdot/SKILL.md').is_file(),
        codex_skill_installed=(skill_path()/'SKILL.md').is_file(),codex_skill_path=str(skill_path()),
        claude_desktop_config_valid=desktop_config_valid,claude_desktop_config_path=str(config),
        autostart_enabled=(appdata/'Microsoft/Windows/Start Menu/Programs/Startup/arizdot.vbs').exists(),
        project_root=str(root))


if __name__=='__main__':print(json.dumps(diagnostics(),ensure_ascii=True,indent=2))

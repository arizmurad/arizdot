import json
import tempfile
import unittest
import os
import subprocess
import sys
from pathlib import Path
from install_claude import install_code,uninstall_code,install_desktop,uninstall_desktop,desktop_config_path


class InstallTests(unittest.TestCase):
    def test_migrated_msix_config_precedes_old_packaged_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            packaged=root/'Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/claude_desktop_config.json'
            migrated=root/'Claude-Data/claude_pzs8sxrjxfjjc/claude_desktop_config.json'
            packaged.parent.mkdir(parents=True);packaged.write_text('{}')
            self.assertEqual(desktop_config_path(localappdata=root),packaged)
            migrated.parent.mkdir(parents=True);migrated.write_text('{"preferences":{"theme":"dark"}}')
            self.assertEqual(desktop_config_path(localappdata=root),migrated)
            self.assertEqual(desktop_config_path(appdata=root/'explicit',localappdata=root),root/'explicit/Claude/claude_desktop_config.json')

    def test_existing_desktop_tools_and_preferences_survive_install_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'Claude/claude_desktop_config.json';path.parent.mkdir()
            initial={'preferences':{'theme':'dark'},'mcpServers':{'other':{'command':'other-tool'}}}
            path.write_text(json.dumps(initial))
            install_desktop(root)
            value=json.loads(path.read_text())
            self.assertEqual(value['preferences'],initial['preferences'])
            self.assertEqual(value['mcpServers']['other'],initial['mcpServers']['other'])
            install_desktop(root)
            uninstall_desktop(root)
            self.assertEqual(json.loads(path.read_text()),initial)

    def test_broken_config_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'Claude/claude_desktop_config.json';path.parent.mkdir()
            path.write_text('invalid-json')
            with self.assertRaises(ValueError):install_desktop(root)
            self.assertEqual(path.read_text(),'invalid-json')

    def test_unmanaged_skill_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'.claude/skills/arizdot';target.mkdir(parents=True)
            (target/'SKILL.md').write_text('my-own-skill')
            with self.assertRaises(ValueError):install_code(tmp)
            self.assertEqual((target/'SKILL.md').read_text(),'my-own-skill')

    def test_relocation_pointer_and_interpreter_are_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(install_code(tmp))
            self.assertTrue((target/'.arizdot-link.json').exists())
            text=(target/'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('${CLAUDE_SESSION_ID}',text)
            self.assertIn('command: "',text)
            self.assertNotIn('args: ["${CLAUDE_SKILL_DIR}',text)
            # Preserve a user-edited installed file during uninstall.
            (target/'scripts/bridge.py').write_text('# custom edit')
            uninstall_code(tmp)
            self.assertTrue((target/'scripts/bridge.py').exists())

    @unittest.skipUnless(os.name=='nt','PowerShell quoting is a Windows check')
    def test_generated_status_command_survives_spaces_and_shell_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)/"Skill O'Neil $value & test"
            target=Path(install_code(home,python=sys.executable))
            text=(target/'SKILL.md').read_text(encoding='utf-8')
            command=next(line.strip('`') for line in text.splitlines() if line.startswith('`& ') and ' status ' in line)
            sid='00000000-0000-4000-8000-000000000955'
            command=command.replace('${CLAUDE_SESSION_ID}',sid)
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['thread_id'],'claude:'+sid)


if __name__=='__main__':unittest.main()

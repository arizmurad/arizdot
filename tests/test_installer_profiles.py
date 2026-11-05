import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import install_windows
from package_source import build
import zipfile


@unittest.skipUnless(os.name=='nt','Windows bootstrap')
class InstallerProfileTests(unittest.TestCase):
    def test_each_profile_registers_only_its_selected_assistants(self):
        for profile in ('codex','claude','both'):
            with self.subTest(profile=profile),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);python=root/'.venv/Scripts/python.exe';python.parent.mkdir(parents=True);python.touch()
                (root/'PACKAGE.json').write_text(json.dumps(dict(target=profile)))
                health=dict(native_indicator_supported=True,pillow=True,tkinter=True,codex_skill_installed=True,mcp=True,claude_skill_installed=True,claude_desktop_config_valid=True)
                with patch.object(install_windows,'ROOT',root),patch.object(install_windows.sys,'argv',['install']),patch.object(install_windows.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()):
                    run.return_value.stdout=json.dumps(health)
                    self.assertEqual(install_windows.main(),0)
                    commands=[call.args[0] for call in run.call_args_list]
                    codex=any(str(root/'install_codex.py') in command for command in commands)
                    claude=any(str(root/'install_claude.py') in command for command in commands)
                    self.assertEqual(codex,profile in ('codex','both'))
                    self.assertEqual(claude,profile in ('claude','both'))


class ReleaseProfileTests(unittest.TestCase):
    def test_archive_profile_and_ownership_rules_survive_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            for profile in ('codex','claude','both'):
                output=Path(tmp)/(profile+'.zip');build(output,target=profile)
                with zipfile.ZipFile(output) as archive:
                    data=json.loads(archive.read('ariztools/PACKAGE.json'))
                    self.assertEqual(data['target'],profile)
                    self.assertIn('ariztools/.github/CODEOWNERS',archive.namelist())
                    self.assertIn('ariztools/Install-Codex.cmd',archive.namelist())
                    self.assertIn('ariztools/Install-Claude.cmd',archive.namelist())
                    self.assertIn('ariztools/assets/providers/openai.png',archive.namelist())
                    self.assertIn('ariztools/assets/providers/claude.webp',archive.namelist())


if __name__=='__main__':unittest.main()

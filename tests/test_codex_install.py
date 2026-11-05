import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from install_codex import install,uninstall,skill_path


class CodexInstallTests(unittest.TestCase):
    def test_installed_pointer_uses_the_application_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(install(Path(tmp)/"O'Neil & Codex"))
            spec=importlib.util.spec_from_file_location('installed_arizdot',target/'scripts/arizdot_skill.py')
            helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
            root=helper.app_root()
            self.assertTrue((root/'control.py').is_file())
            fixture=Path(tmp)/'application';python=fixture/'.venv/Scripts/python.exe'
            python.parent.mkdir(parents=True);python.touch()
            with patch.object(helper,'app_root',return_value=fixture),patch.object(helper.sys,'argv',['helper','status']),patch.object(helper.subprocess,'run') as run:
                run.return_value.returncode=0
                with self.assertRaises(SystemExit) as result:helper.main()
                self.assertEqual(result.exception.code,0)
                self.assertEqual(Path(run.call_args.args[0][0]),python)
            self.assertEqual(json.loads((target/'.arizdot-link.json').read_text())['app_root'],str(root))

    def test_unmanaged_registration_and_edited_files_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=skill_path(tmp);target.mkdir(parents=True)
            (target/'SKILL.md').write_text('custom')
            with self.assertRaises(ValueError):install(tmp)
            (target/'SKILL.md').unlink();target.rmdir()
            target=Path(install(tmp));(target/'SKILL.md').write_text('edited')
            uninstall(tmp)
            self.assertEqual((target/'SKILL.md').read_text(),'edited')
            self.assertFalse((target/'scripts/arizdot_skill.py').exists())

    def test_explicit_home_is_isolated_from_real_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'CODEX_HOME':'C:/unrelated-private-profile'}):
            self.assertEqual(skill_path(tmp,True),Path(tmp)/'.codex/skills/arizdot')
            self.assertEqual(skill_path(tmp),Path(tmp)/'.agents/skills/arizdot')


if __name__=='__main__':unittest.main()

import tempfile
import unittest
import zipfile
from pathlib import Path
from package_source import build


class PackageTests(unittest.TestCase):
    def test_a_config_named_parent_does_not_hide_source_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'config/project'
            for name in ('arizdot.py','tests/test_example.py','skills/arizdot/SKILL.md','config/private.json'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('example')
            result=build(root/'dist/test.zip',root)
            with zipfile.ZipFile(result['archive']) as archive:
                names=archive.namelist()
                self.assertIn('ariztools/tests/test_example.py',names)
                self.assertIn('ariztools/skills/arizdot/SKILL.md',names)
                self.assertNotIn('ariztools/config/private.json',names)

    def test_private_configuration_logs_and_machine_paths_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('arizdot.py','config/sources.json','.venv/token.json','live-preview.png','tests/__pycache__/cached.pyc','integrations/.arizdot-link.json'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('private' if '/' in name or name.endswith('.png') else '# source')
            result=build(root/'dist/test.zip',root)
            with zipfile.ZipFile(result['archive']) as archive:
                names=archive.namelist()
                self.assertIn('ariztools/arizdot.py',names)
                self.assertEqual(len(names),3)
                self.assertIn('ariztools/SOURCE-MANIFEST.json',names)


if __name__=='__main__':unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from alignment import snap
from languages import detect_language,translate,DisplayState
from pulse import State


class AlignmentTests(unittest.TestCase):
    def test_snap_both_axes_and_ignore_distant_position(self):
        self.assertEqual(snap(955,482,1920,1080,112),(960,484,True,True))
        self.assertEqual(snap(700,100,1920,1080,112),(700,100,False,False))

    def test_collapsed_dot_center(self):
        self.assertEqual(snap(961,520,1920,1080,32),(960,524,True,True))


class LanguageTests(unittest.TestCase):
    def test_english_from_codex_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            p=home/'Codex/web/Codex/codex-browser-app/Preferences'
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps(dict(intl=dict(selected_languages='en-US,en'))))
            self.assertEqual(detect_language(home,home),'en')
            p.write_text(json.dumps(dict(intl=dict(selected_languages='az-AZ,en'))))
            self.assertEqual(detect_language(home,home),'az')

    def test_explicit_app_language_overrides_browser_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            p=home/'.codex/.codex-global-state.json'
            p.parent.mkdir()
            p.write_text(json.dumps({'electron-persisted-atom-state':{'locale':'az'}}))
            self.assertEqual(detect_language(home,home),'az')

    def test_english_dynamic_background_status(self):
        self.assertEqual(translate('Dalğa cutoff-u · 120 Ry · SCF 2','en'),'Wave cutoff · 120 Ry · SCF 2')
        self.assertEqual(translate('Sonra: Sıxlıq cutoff-u (yoxlama keçərsə)','en'),'Next: Density cutoff (if validation passes)')
        self.assertEqual(translate('2/7 mərhələ · validasiya planı','en'),'2/7 stages · validation plan')

    def test_preserve_chat_title_and_commentary(self):
        s=State(title='Mənim işim',detail='Sənədi yoxlayıram')
        d=DisplayState(s,'en')
        self.assertEqual(d.title,s.title)
        self.assertEqual(d.current,s.current)
        self.assertEqual(translate('Söhbətə qayıt','az'),'Söhbətə qayıt')


if __name__=='__main__':unittest.main()

"""Resolve either a source skill or its installed pointer registration."""
import json
from pathlib import Path


def app_root():
    for parent in Path(__file__).resolve().parents:
        if (parent/'control.py').is_file() and (parent/'arizdot.py').is_file():return parent
    link=Path(__file__).resolve().parents[1]/'.arizdot-link.json'
    value=json.loads(link.read_text(encoding='utf-8'))
    root=Path(value['app_root'])
    if not (root/'control.py').is_file() or not (root/'arizdot.py').is_file():raise FileNotFoundError('ariztools was moved; reinstall the Claude integration')
    return root

"""Build a reviewable source archive from an allowlist; never include config."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent


def source_files(root=ROOT):
    root=Path(root)
    files=set()
    for pattern in ('*.py','*.md','requirements*.txt','*.vbs','Install-*.cmd','Connect-*.cmd','LICENSE','VERSION','.gitignore','.gitattributes'):
        files.update(p for p in root.glob(pattern) if p.is_file())
    for folder in ('skills','integrations','tests','docs','.github','publication','assets'):
        base=root/folder
        if not base.exists():continue
        for p in base.rglob('*'):
            asset=folder=='docs' and p.parent==base/'assets' and p.suffix in ('.svg','.png','.gif')
            asset=asset or (folder=='assets' and p.parent==base/'providers' and p.suffix in ('.png','.webp'))
            if p.is_file() and (p.suffix in ('.py','.md','.yaml','.yml','.json') or p.name=='CODEOWNERS' or asset) and not any(x in p.relative_to(root).parts for x in ('__pycache__','config','.venv')) and p.name!='.arizdot-link.json':files.add(p)
    return sorted(files)


def build(output=None,root=ROOT,target='both'):
    root=Path(root)
    if target not in ('codex','claude','both'):raise ValueError('Unknown package target')
    output=Path(output or root/'dist/arizdot-claude-preview.zip')
    output.parent.mkdir(parents=True,exist_ok=True)
    entries=source_files(root)
    manifest={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in entries}
    profile=json.dumps(dict(target=target,version=(root/'VERSION').read_text().strip() if (root/'VERSION').exists() else 'development'),indent=2).encode()
    manifest['PACKAGE.json']=hashlib.sha256(profile).hexdigest()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in entries:archive.write(p,'ariztools/'+p.relative_to(root).as_posix())
        archive.writestr('ariztools/PACKAGE.json',profile)
        archive.writestr('ariztools/SOURCE-MANIFEST.json',json.dumps(manifest,sort_keys=True,indent=2))
    return dict(archive=str(output),files=len(entries),sha256=hashlib.sha256(output.read_bytes()).hexdigest())


def build_release(root=ROOT):
    root=Path(root);version=(root/'VERSION').read_text().strip()
    return {target:build(root/'dist'/f'arizdot-{version}-{target}-windows.zip',root,target) for target in ('codex','claude','both')}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--release',action='store_true');args=parser.parse_args()
    print(json.dumps(build_release() if args.release else build()))

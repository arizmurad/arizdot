"""Create two clean local repositories for review; never contacts GitHub."""
import argparse
import json
from pathlib import Path
import shutil
from package_source import ROOT,source_files,build_release


def prepare(output=None,root=ROOT):
    root=Path(root);output=Path(output or root/'dist/github-ready').resolve()
    if output.exists() and any(output.iterdir()):raise ValueError('Choose an empty output folder; existing review files were not overwritten')
    output.mkdir(parents=True,exist_ok=True)
    application=output/'arizdot';catalog=output/'ariztools'
    for path in source_files(root):
        target=application/path.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    template=root/'publication/catalog'
    for path in template.rglob('*'):
        if path.is_file():
            target=catalog/path.relative_to(template);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    for relative in ('LICENSE','.github/CODEOWNERS'):
        target=catalog/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/relative,target)
    releases=build_release(root)
    checksums=''.join(value['sha256']+'  '+Path(value['archive']).name+'\n' for value in releases.values())
    checksum_path=root/'dist/SHA256SUMS.txt';checksum_path.write_text(checksums,encoding='utf-8')
    report=dict(status='Prepared locally; no GitHub changes',repositories=dict(ariztools=str(catalog),arizdot=str(application)),
        packages=releases,checksums=str(checksum_path),source_files=len(source_files(root)))
    (output/'PREPARATION-REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output');args=parser.parse_args()
    print(json.dumps(prepare(args.output),indent=2))

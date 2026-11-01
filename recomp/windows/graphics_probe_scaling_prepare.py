"""Prepare an isolated pinned ANGLE scaling variant; never edits accepted base.

Local immutable Git objects can seed the exact official pins. No base working
tree or DLL bundle is copied as source, and no system installation is performed.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'work/angle-native'
ROOT=HERE.parent/'work/angle-scaling'


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def main():
    prepare=module('angle_base_prepare','graphics_probe_prepare_angle.py')
    ROOT.mkdir(parents=True,exist_ok=True)
    for relative,(url,commit) in sorted(prepare.SOURCES.items(),key=lambda item:len(Path(item[0]).parts)):
        target=ROOT/relative;source=BASE/relative
        if (target/'.git').exists() or not (source/'.git').exists():continue
        target.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['git','clone','--shared','--no-checkout',str(source),str(target)],check=True)
        subprocess.run(['git','remote','set-url','origin',url],cwd=target,check=True)
        subprocess.run(['git','-c','core.autocrlf=false','checkout','--detach',commit],cwd=target,check=True)
    evidence=json.loads((BASE/'prepare-provenance.json').read_text())
    for relative,record in evidence['downloads'].items():
        source=BASE/relative
        if not source.is_file():continue
        if hashlib.sha256(source.read_bytes()).hexdigest()!=record['sha256']:raise RuntimeError('Base recipe hash mismatch:'+relative)
        target=ROOT/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    prepare.ROOT=ROOT;sys.argv=[sys.argv[0],'--sources-only'];prepare.main()
    patch=module('angle_base_patch','graphics_probe_patch_angle.py');patch.ROOT=ROOT;patch.SOURCE=ROOT/'src';patch.main()
    (ROOT/'variant-provenance.json').write_text(json.dumps({'base_source_pin':prepare.SOURCES['src'][1],'base_recipe_pin':prepare.RECIPE,
      'base_accepted_bundle':str((BASE/'bundle/provenance.json').resolve()),'base_bundle_sha256':hashlib.sha256((BASE/'bundle/provenance.json').read_bytes()).hexdigest(),
      'purpose':'Isolated Vulkan present-scaling prototype; no capability or fixed-size support claimed until real tests pass',
      'source_seeding':'Exact pinned Git commits, optionally using immutable local object alternates; working tree modifications excluded'},indent=2)+'\n')


if __name__=='__main__':main()

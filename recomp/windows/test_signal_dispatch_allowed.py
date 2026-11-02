"""Atomic allowed dispatch; reuse accepted NDK sender bytes without any relift."""
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('signal_host.h','signal_host.cpp','signal_dispatch_allowed_test.cpp','test_signal_dispatch_allowed.py','signal_dispatch_allowed.md')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('out','toolchain'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--support-commit',default='9cdf370');p.add_argument('--sender',type=Path,default=HERE.parent/'work/signal-sender5');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 def wp(q):return subprocess.check_output(['wslpath','-m',str(Path(q).resolve())],text=True).strip()
 old=a.sender.resolve();oldproof=old/'acceptance.json';assert sha(oldproof)=='86d2f5d1b9292d1e089b94de3fd32071f6d78ebfa6104aad9c497b2e2286d410';accepted=json.loads(oldproof.read_text())
 git=['git.exe','-C',wp(HERE.parent.parent)];commit=subprocess.check_output([*git,'rev-parse',a.support_commit],text=True).strip();archive=subprocess.check_output([*git,'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp'
 for n,h in accepted['overlays'].items():assert sha(source/'windows'/n)==h,n
 overlay={}
 for n in OWN:overlay[n]=sha(HERE/n);shutil.copy2(HERE/n,source/'windows'/n)
 pins={str(q):sha(q)for q in source.rglob('*')if q.is_file()};tools={str(q):sha(q)for q in a.toolchain.rglob('*')if q.is_file()};old_inputs={str(oldproof):sha(oldproof)}
 result={'passed':False,'support_commit':commit,'overlays':overlay,'source_pins':pins,'tool_pins':tools,'archive_sha256':sha(out/'support.tar'),'limits':'Atomic virtual signal selection plus reused actual NDK handler only; no game or GC execution; no guest relift/instrumentation.'};(out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n')
 def run(cmd,name,timeout=300):
  with(out/name).open('w')as log:r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(f'{name}: exit{r.returncode}\n{(out/name).read_text(errors="replace")[-6000:]}')
 library=old/'sender.so';assert sha(library)==accepted['fixture_sha256'];old_inputs[str(library)]=sha(library)
 platforms={};external={str(q.resolve()):sha(q.resolve())for q in [Path('/usr/bin/clang++-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe')]}
 for windows in (False,True):
  label='windows'if windows else'linux';build=out/label;build.mkdir();hp=wp if windows else str;cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18'
  previous=old/label;manifest=json.loads((previous/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  for q in [previous/'manifest.json',previous/'traces.h',*map(Path,manifest['objects'])]:old_inputs[str(q)]=sha(q)
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(a.toolchain/'include')];loader=build/'loader.o';run([cc,'-O2','-c',hp(source/'fastaes/elfload.c'),'-o',hp(loader)],label+'-loader.log');objects={}
  for rel in ('whole/runtime.cpp','whole/signal_frame.cpp','windows/libc.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/semaphore_host.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',hp(source/rel),'-o',hp(obj)],label+'-'+Path(rel).stem+'-build.log');objects[Path(rel).stem]=obj
  binary=build/('allowed.exe'if windows else'allowed');run([cxx,*flags,'-Wall','-Wextra','-Werror','-I'+hp(previous),f'-DSENDER_LIBRARY="{hp(library)}"',hp(source/'windows/signal_dispatch_allowed_test.cpp'),*map(hp,[objects[n]for n in ('runtime','signal_frame','libc','signal_host','signal_delivery')]),hp(loader),*map(hp,manifest['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',hp(binary)],label+'-test-build.log');run([binary],label+'-focused.log',60);text=(out/(label+'-focused.log')).read_text();assert 'SIGNAL-DISPATCH-ALLOWED-SUCCESS 'in text
  prior=HERE.parent/'work'/('signal-host-'+label);prior_manifest=json.loads((prior/'guest/manifest.json').read_text());assert not prior_manifest['unsupported_traces']and not prior_manifest['unresolved_direct_targets']
  for q in [prior/'policy.so',prior/'reference.bin',prior/'guest/manifest.json',prior/'guest/traces.h',*map(Path,prior_manifest['objects'])]:old_inputs[str(q)]=sha(q)
  exe=build/('default-regression.exe'if windows else'default-regression');run([cxx,*flags,'-I'+hp(prior/'guest'),f'-DSIGNAL_HOST_LIBRARY="{hp(prior/"policy.so")}"',f'-DSIGNAL_HOST_REFERENCE="{hp(prior/"reference.bin")}"',hp(source/'windows/signal_host_test.cpp'),*map(hp,[objects[n]for n in ('runtime','signal_host','semaphore_host')]),hp(loader),*map(hp,prior_manifest['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',hp(exe)],label+'-default-build.log');run([exe],label+'-default.log',60)
  platforms[label]={'focused_stdout':text,'executable_sha256':sha(binary),'default_stdout':(out/(label+'-default.log')).read_text(),'default_executable_sha256':sha(exe),'reused_NDK_heads':len(manifest['traces']),'reused_NDK_objects':len(manifest['objects'])};print(label,'passed',flush=True)
 for n,h in overlay.items():assert sha(HERE/n)==h and sha(source/'windows'/n)==h,n
 for n,h in {**pins,**tools,**external,**old_inputs}.items():assert sha(n)==h,n
 result.update(passed=True,platforms=platforms,external_tools=external,reused_inputs=old_inputs,NDK_fixture_sha256=sha(library));result['evidence']={str(q.relative_to(out)):sha(q)for q in out.rglob('*')if q.is_file()and'host'not in q.relative_to(out).parts and q.name!='acceptance.json'};(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ALLOWED-ALL-SUCCESS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()

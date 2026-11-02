"""Focused real SignalHost phase transition; no guest/game/ISA execution."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,tarfile
HERE=Path(__file__).resolve().parent
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--support',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False)
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 commit='ff6c86bf8b826426702f73c87d361affb82c2a4e';archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',commit,'recomp/whole','recomp/windows/signal_host.h','recomp/windows/signal_host.cpp']);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp';owned={}
 for n in('game_collector_mask.h','game_collector_mask_test.cpp','test_game_collector_mask.py'):
  owned[n]=sha(HERE/n);shutil.copy2(HERE/n,source/'windows'/n)
 pins={str(p):sha(p)for p in source.rglob('*')if p.is_file()};includes=a.support.resolve()/'remill-include';headers={str(p):sha(p)for p in includes.rglob('*')if p.is_file()}
 result=dict(passed=False,scope='real SignalHost native policy transitions and production phase predicate only; no guest/game/GC/ISA execution',support_commit=commit,owned_sources=owned,source_pins=pins,header_pins=headers,archive_sha256=sha(out/'support.tar'));(out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n')
 commands=[];platforms={};tools={}
 def run(command,name):
  commands.append(list(map(str,command)))
  with(out/name).open('w')as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
  if r.returncode:raise RuntimeError(f'{name}: exit{r.returncode}\n{(out/name).read_text()[-5000:]}')
 for windows in(False,True):
  label='windows'if windows else'linux';build=out/label;build.mkdir();path=wp if windows else str;cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'/usr/bin/clang++-18';tools[str(Path(cxx).resolve())]=sha(Path(cxx).resolve())
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(includes)]
  objects=[]
  for rel in('whole/runtime.cpp','windows/signal_host.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(obj)],label+'-'+Path(rel).stem+'.log');objects.append(obj)
  binary=build/('mask.exe'if windows else'mask');run([cxx,*flags,'-Wall','-Wextra','-Werror',path(source/'windows/game_collector_mask_test.cpp'),*map(path,objects),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(binary)],label+'-link.log')
  run([str(binary)],label+'-runtime.log');text=(out/(label+'-runtime.log')).read_text();assert'GAME-COLLECTOR-MASK-PASS 'in text;platforms[label]=dict(stdout=text,executable_sha256=sha(binary));print(label,'passed',flush=True)
 for name,h in owned.items():assert sha(HERE/name)==h and sha(source/'windows'/name)==h,name
 for p,h in{**pins,**headers,**tools}.items():assert sha(p)==h,p
 result.update(passed=True,platforms=platforms,external_tools=tools,commands=commands,evidence={str(p.relative_to(out)):sha(p)for p in out.rglob('*')if p.is_file()and'host'not in p.relative_to(out).parts and p.name!='acceptance.json'})
 (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('MASK-FOCUSED-PASS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()

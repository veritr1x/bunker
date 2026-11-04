"""Focused internal SignalHost admitted/subset dispatch; no NDK lift or game."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,tarfile,re
from concurrent.futures import ThreadPoolExecutor
HERE=Path(__file__).resolve().parent
BASE='bfa4e8e650408d740e861b10e4c2bebaf26d0aa0'
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('signal_host.h','signal_host.cpp','signal_admitted_subset_test.cpp','test_signal_admitted_subset.py')
PROOF=W/'signal-admitted-subset-preparation1/source-proof.json'
PROOF_SHA='c748f2f660587ab63f1837c15911fa3e9565abc713c2b56b11673e486ec2c436'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False)
 assert sha(PROOF)==PROOF_SHA;proof=json.loads(PROOF.read_text());assert proof['passed']is True and proof['base_commit']==BASE
 archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',BASE,'recomp/windows','recomp/whole']);(out/'support.tar').write_bytes(archive)
 source=out/'source';source.mkdir()
 with tarfile.open(fileobj=io.BytesIO(archive))as tf:assert tf.pax_headers['comment']==BASE;tf.extractall(source,filter='data')
 source=source/'recomp'
 for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
 for name,row in proof['files'].items():
  f=source/name;assert sha(f)==row['new_sha256'];b=f.read_bytes()
  for item in reversed(row['insertions']):
   at=item['new_offset'];added=bytes.fromhex(item['bytes_hex']);assert b[at:at+len(added)]==added;b=b[:at]+b[at+len(added):]
  assert hashlib.sha256(b).hexdigest()==row['old_sha256']
 owned={'windows/'+name:sha(source/'windows'/name)for name in OWN};sources={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()}
 tool=W/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4'
 inputs={str(PROOF):PROOF_SHA}
 for p in (Path('/mnt/c/mingw64/bin/g++.exe'),Path(shutil.which('clang++-18')).resolve()):inputs[str(p)]=sha(p)
 for f in(tool/'include').rglob('*'):
  if f.is_file():inputs[str(f)]=sha(f)
 commands=[]
 def platform(windows):
  name='windows'if windows else'linux';build=out/name;build.mkdir();convert=wp if windows else str;cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18'
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',convert(tool/'include')]
  def run(command,label):
   command=list(map(str,command));commands.append(command);print('STAGE '+name+' '+label,flush=True)
   with(build/(label+'.log')).open('w')as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=120)
   text=(build/(label+'.log')).read_text(errors='replace')
   if r.returncode:raise RuntimeError(name+' '+label+' exit'+str(r.returncode)+'\n'+text[-6000:])
   return text
  objects=[]
  for rel in ('windows/signal_admitted_subset_test.cpp','windows/signal_host.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');strict=['-Wall','-Wextra','-Werror']if Path(rel).stem=='signal_admitted_subset_test'else[]
   run([cxx,*flags,*strict,'-c',convert(source/rel),'-o',convert(obj)],'compile-'+Path(rel).stem);objects.append(obj)
  exe=build/('test.exe'if windows else'test');run([cxx,*map(convert,objects),'-pthread','-latomic',*(['-static']if windows else[]),'-o',convert(exe)],'link')
  text=run([exe],'test');m=re.search(r'SIGNAL-ADMITTED-SUBSET-PASS checks=(\d+)',text);assert m,text
  return name,dict(exit_code=0,checks=int(m[1]),stdout=text,binary_sha256=sha(exe),log_sha256=sha(build/'test.log'))
 with ThreadPoolExecutor(max_workers=2)as pool:platforms=dict(pool.map(platform,(False,True)))
 assert platforms['linux']['checks']==platforms['windows']['checks']
 for name,h in sources.items():assert sha(source/name)==h,name
 for name,h in owned.items():assert sha(HERE.parent/name)==h,name
 for path,h in inputs.items():assert sha(path)==h,path
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 receipt=dict(passed=True,commit=BASE,owned_sources=owned,source_sha256=sources,source_proof={'path':str(PROOF),'sha256':PROOF_SHA},inputs=inputs,platforms=platforms,actual_queue_mask_siginfo_and_real_boundary_callbacks=True,atomic_all_eligible_unknown_rejection_before_subset_selection=True,admitted_unselected_24_retained=True,invalid_selected_subset_returns22_before_mutation=True,foreign_retired_default_and_missing_boundary_controls=True,restored_mask_callback_edits_throw_cleanup_and_NeedsPoll_verified=True,existing_allowed_and_admitted_API_regressions=True,all_old_core_function_bodies_and_layout_byte_exact=True,no_NDK_lift_or_original_game_execution=True,limits='Internal model API only; selected actual C++ boundary callbacks execute. No translated signal-frame, NanoSleep integration, collector roots, native OS signal delivery or game claim.')
 receipt['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and f.name!='acceptance.json'}
 (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('SIGNAL-SUBSET-QUALIFIED '+sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()

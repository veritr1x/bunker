"""Real Windows prepared-worker composition with retained original GC protocol code."""
import argparse,concurrent.futures,hashlib,json,re,shutil,subprocess,threading,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('windows/game_unity_worker_collector.h','windows/game_unity_worker_collector_test.cpp','windows/test_game_unity_worker_collector.py')
COMPILE=('windows/game_unity_worker_collector_test.cpp','windows/pthread_host.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/signal_futex.cpp','windows/signal_sleep.cpp','windows/semaphore_host.cpp','windows/worker_signal_lifecycle.cpp','whole/runtime.cpp','whole/signal_frame.cpp','whole/cooperative_poll.cpp')
EXTRACT='ace8c5cd9da8460c110d6a8da6dd91e4a31a36cfc4ed598cd256ab9bcd222f3a'
OBJECT='c353c4bb96e6fba4081c522215771a563eb1f1680c23251b902f7ab5ecc4b8e0'
DEFAULT='f9d6714285dda794da3d023589957dd38c38d334c24f3fa201e08edbca39a6fa'
AUDIT='c088c3c959a137f8589b5485f27dfe70d2a19cd62d5ef37279927dfcd6f83b4d'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--header-sha',required=True);p.add_argument('--fixture-sha',required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False)
 commands=[];pins={};lock=threading.Lock();repo=HERE.parent;source=out/'source'
 def pin(path,expected=None):
  path=Path(path).resolve();value=sha(path);assert expected is None or value==expected,str(path);pins[str(path)]=value;return value
 def run(label,cmd):
  cmd=list(map(str,cmd))
  with lock:commands.append(dict(label=label,argv=cmd));save(out/'commands.json',commands)
  print('STAGE '+label,flush=True)
  with(out/(label+'.log')).open('x')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
  text=(out/(label+'.log')).read_text(errors='replace')
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+text[-6000:])
  return dict(exit_code=r.returncode,stdout=text)
 try:
  pin(HERE/'game_unity_worker_collector.h',a.header_sha);pin(HERE/'game_unity_worker_collector_test.cpp',a.fixture_sha)
  extraction=W/'original-gc-protocol-extract1/extraction.json';pin(extraction,EXTRACT);assert read(extraction)['passed']is True
  original=W/'original-gc-protocol-extract1/windows.o';pin(original,OBJECT)
  default=W/'futex-dispatcher-qualification1/acceptance.json';pin(default,DEFAULT);provider=read(default);assert provider['passed']is True
  for name,h in provider['core_sources'].items():pin(repo/name,h)
  audit=W/'soft-input1-worker-collector-boundary1/acceptance.json';pin(audit,AUDIT);assert read(audit)['passed']is True
  hashes={}
  def freeze(path):
   path=Path(path).resolve();name=path.relative_to(repo).as_posix()
   if name in hashes:return
   hashes[name]=pin(path);dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
   for include in re.findall(r'^\s*#include\s+"([^"]+)"',path.read_text(),re.M):
    child=path.parent/include
    if child.is_file():freeze(child)
  for name in (*COMPILE,*OWN,'windows/game_collector_delivery.h'):freeze(repo/name)
  save(out/'source-hashes.json',hashes)
  # The bootstrap is not linked into this component. Pin its reviewed route
  # snapshot separately for the subsequent whole-host integration qualification.
  boot=repo/'windows/game_bootstrap.cpp';boothash=pin(boot);shutil.copyfile(boot,out/'observed-bootstrap.cpp')
  shutil.copyfile(original,out/'original-protocol.o')
  tool=W/'remill-src/include';cxx='/mnt/c/mingw64/bin/g++.exe';pin(cxx)
  for path in(tool/'remill').rglob('*.h'):pin(path)
  opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool)]
  run('strict-fixture-syntax',[cxx,*opts,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(source/'windows/game_unity_worker_collector_test.cpp')])
  objects=[];jobs=[]
  for name in COMPILE:
   obj=out/(Path(name).stem+'.o');objects.append(obj);jobs.append((Path(name).stem,[cxx,*opts,'-c',wp(source/name),'-o',wp(obj)]))
  with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
   futures=[pool.submit(run,label,cmd)for label,cmd in jobs]
   for f in futures:f.result()
  exe=out/'original-worker-gc.exe'
  run('link',[cxx,*map(wp,objects),wp(out/'original-protocol.o'),'-static','-pthread','-latomic','-ladvapi32','-lbcrypt','-o',wp(exe)])
  result=run('genuine-protocol',[exe]);text=result['stdout']
  match=re.search(r'UNITY-WORKER-ORIGINAL-GC-SUCCESS cycles=2 posts=4 stops=2 restarts=(\d+) checks=(\d+)',text)
  assert match and int(match[1])>=2,text
  assert text.count('physical ordinary roots')==4 and text.count('genuine stop returned')==2,text
  result.update(cycles=2,actual_posts=4,stop_deliveries=2,nested_restarts=int(match[1]),checks=int(match[2]),physical_root_frames=4,binary_sha256=sha(exe))
  for name,h in hashes.items():assert sha(repo/name)==h,name
  for path,h in pins.items():assert sha(path)==h,path
  for name in OWN:assert b'\r'not in(source/name).read_bytes(),name
  receipt=dict(passed=True,scope='Actual Windows Pthreads prepared-worker lifecycle and existing hook composition; genuine retained original stop/resume coordinators and handlers perform two cycles with ordinary-record normal31GPR/32Q roots and original4posts.',
   owned_sources={name:hashes[name]for name in OWN},compositor_sources={'windows/game_collector_delivery.h':hashes['windows/game_collector_delivery.h']},core_sources={name:hashes[name]for name in provider['core_sources']},source_hashes=hashes,bootstrap_source=dict(path=str(boot),sha256=boothash,compiled_here=False),
   results={'windows':result},cycles=2,actual_posts=4,stop_deliveries=2,nested_restarts=result['nested_restarts'],checks=result['checks'],physical_root_frames=4,
   original_extraction=dict(path=str(extraction),sha256=EXTRACT,windows_object_sha256=OBJECT),default_futex_receipt=dict(path=str(default),sha256=DEFAULT,reused_without_replay=True),original_boundary_audit=dict(path=str(audit),sha256=AUDIT),inputs=pins,
   limits=['TEST initial registry/global state and helper-shaped interrupted caller; real Pthreads ownership but original Unity wrapper, original GC registration/scanner, heap reclamation and game are not executed.',
           'Only disabled alternate stack, actual entered Unity-wrapper witness and exact copied UINT32_MAX-ms timed-private-futex phase are admitted. No arbitrary provider/compiler-poll or callback-identity claim.',
           'Late known bits remain pending until a later sender-certified original epoch; same-epoch duplicate zero-post delivery is not qualified.'])
  receipt['evidence']={f.relative_to(out).as_posix():sha(f)for f in out.rglob('*')if f.is_file()and f.name!='acceptance.json'};save(out/'acceptance.json',receipt);print('UNITY-WORKER-COLLECTOR-QUALIFIED '+sha(out/'acceptance.json'),flush=True)
 except BaseException as error:save(out/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()

"""Real Windows socket readiness wait with retained original GC protocol code."""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,re,shutil,subprocess,threading,traceback
HERE=Path(__file__).resolve().parent;REPO=HERE.parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=['windows/game_socket_wait_context.h','windows/game_socket_wait.h','windows/game_socket_wait_test.cpp','windows/test_game_socket_wait.py','windows/game_collector_delivery.h','windows/game_unity_main_collector.h','windows/game_unity_worker_collector.h']
COMPILE=['windows/game_socket_wait_test.cpp','windows/pthread_host.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/signal_sleep.cpp','windows/semaphore_host.cpp','windows/worker_signal_lifecycle.cpp','windows/socket_transport.cpp','windows/filesystem.cpp','windows/growdown_memory.cpp','whole/format.cpp','whole/runtime.cpp','whole/signal_frame.cpp','whole/cooperative_poll.cpp']
PROVIDER_NAMES={'windows/socket_transport.cpp','windows/socket_transport.h','windows/guest_descriptors.h','windows/filesystem.h','windows/filesystem.cpp'}
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(p),sha256=sha(p),bytes=Path(p).stat().st_size)
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def read(p):return json.loads(Path(p).read_bytes())
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--provider-manifest',type=Path,required=True);p.add_argument('--provider-manifest-sha256',required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';commands=[];lock=threading.Lock();hashes={}
 def run(label,argv):
  argv=list(map(str,argv))
  with lock:commands.append(dict(stage=label,argv=argv));save(out/'commands.json',commands)
  print('STAGE '+label,flush=True)
  with(out/(label+'.log')).open('x')as log:r=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+(out/(label+'.log')).read_text(errors='replace')[-5000:])
  return dict(exit_code=r.returncode,stdout=desc(out/(label+'.log')))
 def freeze(path):
  path=path.resolve();name=path.relative_to(REPO).as_posix()
  if name in hashes:return
  hashes[name]=sha(path);dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
  for include in re.findall(r'^\s*#include\s+"([^"]+)"',path.read_text(),re.M):
   child=path.parent/include
   if child.is_file():freeze(child)
 try:
  assert re.fullmatch('[0-9a-f]{64}',a.provider_manifest_sha256)and sha(a.provider_manifest)==a.provider_manifest_sha256
  provider=read(a.provider_manifest);assert set(provider)==PROVIDER_NAMES
  for n,h in provider.items():assert re.fullmatch('[0-9a-f]{64}',h)and sha(REPO/n)==h,n
  for n in COMPILE+OWN+['fastaes/elfload.c']:freeze(REPO/n)
  save(out/'source-hashes.json',hashes)
  parent=W/'socket-transport-qualification1';manifest=parent/'guest/manifest.json';assert sha(manifest)=='bae7017273eb5632784b385379a40c518d11254fafdc8780b34cf96b5fdc9aea';guest=read(manifest);assert not guest['unsupported_traces']and not guest['unresolved_direct_targets']and len(guest['objects'])==2
  elf=parent/'socket.so';assert sha(elf)=='d4ca8d93cf04dbfaa7d1000a4fd2b27bc78eae393bdf2a6fae96f4ee738eb743'
  shutil.copytree(parent/'guest',out/'guest');shutil.copyfile(elf,out/'socket.so')
  extraction=W/'original-gc-protocol-extract1/extraction.json';original=W/'original-gc-protocol-extract1/windows.o';assert sha(extraction)=='ace8c5cd9da8460c110d6a8da6dd91e4a31a36cfc4ed598cd256ab9bcd222f3a'and read(extraction)['passed']is True;assert sha(original)=='c353c4bb96e6fba4081c522215771a563eb1f1680c23251b902f7ab5ecc4b8e0';shutil.copyfile(original,out/'original-protocol.o')
  cxx='/mnt/c/mingw64/bin/g++.exe';cc='/mnt/c/mingw64/bin/gcc.exe';tool=W/'remill-src/include';opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool),'-I'+wp(out/'guest'),'-DSOCKET_LIBRARY="'+wp(out/'socket.so')+'"']
  tools={'cxx':desc(Path(cxx)),'cc':desc(Path(cc))}
  run('strict-fixture-syntax',[cxx,*opts,'-Wall','-Wextra','-Werror','-fmax-errors=5','-fsyntax-only',wp(source/'windows/game_socket_wait_test.cpp')])
  loader=out/'elfload.o';run('compile-loader',[cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)])
  jobs=[];objects=[]
  for name in COMPILE:
   obj=out/(Path(name).stem+'.o');objects.append(obj);jobs.append((Path(name).stem,[cxx,*opts,'-c',wp(source/name),'-o',wp(obj)]))
  with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
   futures=[pool.submit(run,label,argv)for label,argv in jobs]
   for f in futures:f.result()
  guest_objects=[]
  for path in guest['objects']:
   src=Path(path);dest=out/'guest'/src.name;assert sha(src)==sha(dest);guest_objects.append(dest)
  exe=out/'socket-gc.exe';run('link',[cxx,*map(wp,objects),wp(loader),wp(out/'original-protocol.o'),*map(wp,guest_objects),'-static','-pthread','-latomic','-ladvapi32','-lbcrypt','-o',wp(exe)])
  results={}
  for role in range(3):
   result=run('genuine-socket-GC-'+str(role),[exe,str(role)]);text=Path(result['stdout']['path']).read_text();match=re.search(r'SOCKET-WAIT-ORIGINAL-GC-PASS role='+str(role)+r' cycles=2 posts=4 stops=2 restarts=(\d+) checks=(\d+) copied=2 returned=2 before=(\d+) after=(\d+) actual_NDK_calls=2 forms=2 negative_controls=(\d+)',text);assert match and int(match[1])>=4 and int(match[5])>=11 and text.count('physical roots token=')==4
   result.update(cycles=2,actual_posts=4,stop_deliveries=2,nested_restarts=int(match[1]),checks=int(match[2]),physical_root_frames=4,actual_NDK_calls=2,forms=2,negative_controls=int(match[5]));results[str(role)]=result
  for n,h in hashes.items():assert sha(source/n)==h,n
  for n in OWN:assert sha(REPO/n)==hashes[n],n
  receipt=dict(passed=True,scope='Actual NDK poll on genuine Windows Pthreads ordinary/Unity-witness worker and attached external main lifetimes, real loopback readiness and unchanged retained original GC coordinators/handlers. TEST initial registry and component NDK site policy are explicit.',owned_sources={n:hashes[n]for n in OWN},provider_sources=provider,provider_manifest=desc(a.provider_manifest),source_hashes=hashes,tools=tools,original_extraction=desc(extraction),original_protocol_object=desc(out/'original-protocol.o'),NDK_caller_manifest=desc(manifest),NDK_caller_ELF=desc(out/'socket.so'),binary=desc(exe),results=results,cycles=6,actual_posts=12,physical_root_frames=12,actual_NDK_calls=6,limits=['Initial GC registry/role/caller setup is TEST data; original Unity registration/trampoline/heap scanner/reclamation and game are not executed.','Component site policy admits only actual NDK poll return PCs; production default original Unity site policy is independently retained and original-game caller role remains unproven.','Existing finalizer-condition/nanosleep/futex regressions are separate required checks after final production freeze.'])
  save(out/'acceptance.json',receipt);print('SOCKET-WAIT-COLLECTOR-QUALIFIED '+sha(out/'acceptance.json'),flush=True)
 except BaseException as error:save(out/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc(),source_hashes=hashes));raise
if __name__=='__main__':main()

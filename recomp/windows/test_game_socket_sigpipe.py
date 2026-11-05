"""Isolated real NDK socket/send tests of the production Windows SIGPIPE policy."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
OWN=('game_socket_sigpipe_test.cpp','test_game_socket_sigpipe.py')
PROVIDER={'windows/socket_transport.cpp','windows/socket_transport.h','windows/guest_descriptors.h','windows/filesystem.h','windows/filesystem.cpp'}

def sha(path):
 with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def desc(path):return dict(path=str(Path(path).absolute()),sha256=sha(path),bytes=Path(path).stat().st_size)
def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):
 with Path(path).open('x')as stream:stream.write(json.dumps(value,indent=2)+'\n')
def hp(path):
 text=str(path);return Path('/mnt/'+text[0].lower()+'/'+text[3:].replace('\\','/'))if re.match(r'^[A-Za-z]:[/\\]',text)else Path(path)
def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).absolute())],text=True).strip()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('out','provider-manifest','physical-receipt'):parser.add_argument('--'+name,type=Path,required=True)
 for name in ('provider-manifest-sha256','physical-receipt-sha256','policy-sha256'):parser.add_argument('--'+name,required=True)
 args=parser.parse_args();out=args.out.absolute();out.mkdir(exist_ok=False);commands=[];held={}
 def pin(path,digest=None):
  path=Path(path).absolute();actual=sha(path)
  if digest is not None:assert actual==digest,str(path)
  held[str(path)]=actual;return desc(path)
 def run(label,argv,expected=None):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv,component_timeout_seconds=30))
  (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  log=out/(label+'.log')
  with log.open('xb')as stream:result=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,timeout=30)
  text=log.read_text(errors='replace')
  if expected is not None:assert result.returncode==expected,(label,result.returncode,text[-3000:])
  return result.returncode,text,desc(log)
 try:
  provider_pin=pin(args.provider_manifest,args.provider_manifest_sha256);provider=read(args.provider_manifest);assert set(provider)==PROVIDER
  physical_pin=pin(args.physical_receipt,args.physical_receipt_sha256);physical=read(args.physical_receipt);assert physical['passed']is True and physical['provider_sources']==provider
  base=args.physical_receipt.parent;source=out/'source';shutil.copytree(base/'source',source)
  for name,digest in physical['source_hashes'].items():pin(base/'source'/name,digest);assert sha(source/name)==digest
  for name,digest in provider.items():assert physical['source_hashes'][name]==digest;pin(HERE.parent/name,digest)
  for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name);pin(HERE/name)
  policy=pin(HERE/'game_socket_sigpipe.h',args.policy_sha256);shutil.copyfile(HERE/'game_socket_sigpipe.h',source/'windows/game_socket_sigpipe.h');assert sha(source/'windows/game_socket_sigpipe.h')==args.policy_sha256
  guest=out/'guest';shutil.copytree(base/'guest',guest);guest_manifest=pin(base/'guest/manifest.json',physical['NDK_caller_manifest']['sha256']);manifest=read(base/'guest/manifest.json');assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']and len(manifest['objects'])==2
  guest_elf=pin(base/'socket.so',physical['NDK_caller_ELF']['sha256']);shutil.copyfile(base/'socket.so',out/'socket.so')
  old_commands=read(base/'commands.json');link=next(row['argv']for row in old_commands if row['stage']=='link');assert len([p for p in link if p.endswith('.o')])==18
  library=out/'library';library.mkdir();objects=[];object_sources={};reused=[]
  for token in link:
   if not token.endswith('.o'):continue
   path=hp(token)
   if path.name in ('game_socket_wait_test.o','original-protocol.o'):continue
   row=pin(path);target=library/path.name;assert not target.exists();shutil.copyfile(path,target);assert sha(target)==row['sha256'];objects.append(target);reused.append(dict(original=row,frozen_copy=desc(target)))
   stage=next((item for item in old_commands if '-c'in item['argv']and '-o'in item['argv']and hp(item['argv'][item['argv'].index('-o')+1])==path),None)
   if stage:
    cpp=hp(stage['argv'][stage['argv'].index('-c')+1]);assert cpp.is_file();pin(cpp);object_sources[path.name]=dict(source=desc(cpp),compile_argv=stage['argv'])
   else:assert path.name.startswith('shard-'),path
  assert len(objects)==16 and len(object_sources)==14
  cxx=hp(physical['tools']['cxx']['path']);compiler=pin(cxx,physical['tools']['cxx']['sha256']);includes=Path('/mnt/c/GitRepos/bunker/recomp/work/remill-src/include')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(includes),'-I'+wp(guest),'-DSOCKET_LIBRARY="'+wp(out/'socket.so')+'"','-Wall','-Wextra','-Werror']
  test_object=out/'game_socket_sigpipe_test.o';run('compile-policy-fixture',[cxx,*flags,'-c',wp(source/'windows/game_socket_sigpipe_test.cpp'),'-o',wp(test_object)],0)
  executable=out/'socket-sigpipe.exe';run('link-policy-fixture',[cxx,wp(test_object),*map(wp,objects),'-Wl,--wrap=_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE','-static','-pthread','-latomic','-ladvapi32','-lbcrypt','-o',wp(executable)],0)
  results={}
  modes=('ignore','default','nosignal','custom','blocked')
  for mode in modes:
   for form in (0,1):
    label=mode+'-'+str(form);code,text,log=run(label,[executable,mode,form]);assert 'BEFORE-GUEST-SEND mode='+mode in text and f'NDK-CALL api=socket form={form}'in text and f'NDK-CALL api=send form={form}'in text
    mask=re.search(r'POLICY-MASK mode='+mode+r' actual=(0x[0-9a-f]+|0) blocked13=([01])',text);assert mask and int(mask[2])==(mode in ('ignore','blocked'))
    returned='AFTER-GUEST-SEND'in text
    if mode in ('ignore','nosignal'):
     assert code==0 and returned and 'result=-1 errno=32'in text
     match=re.search(r'SIGPIPE-PASS mode='+mode+r' form='+str(form)+r' checks=(\d+) hooks=(\d+) NDK_calls=3 nativeEnvironment=1 State1200=1 Memory64=1',text);assert match,text[-3000:]
     count=int(match[2]);assert count==(1 if mode=='ignore'else 0)
     if mode=='ignore':assert 'POLICY-RETURN ignored=1 nativeEnvironment=1'in text
     else:assert 'POLICY-NOTIFY'not in text
     result=dict(exit_code=code,stdout=log,postcall_returned=True,guest_send_return=-1,guest_errno=32,hooks=count,checks=int(match[1]),actual_NDK_entries=3,native_environment_preserved=True)
    else:
     assert not returned and 'SIGPIPE-PASS'not in text and 'POLICY-NOTIFY'in text
     if mode=='default':assert code==141 and 'terminating with adapter status 141'in text
     else:
      diagnosis='blocked default SIGPIPE is outside the qualified pending-delivery profile'if mode=='blocked'else'custom guest SIGPIPE handler is outside the qualified native delivery profile'
      assert code not in (0,141)and diagnosis in text
      assert 'POLICY-REJECT mode='+mode+' actionUnchanged=1 maskUnchanged=1 pending=0'in text
     result=dict(exit_code=code,stdout=log,postcall_returned=False,hooks=1,actual_NDK_entries_started=2,adapter_status_not_POSIX_wait_status=True)
    result['observed_signal_mask']=int(mask[1],0);result['SIGPIPE_blocked']=bool(int(mask[2]));results[label]=result
  for path,digest in held.items():assert sha(path)==digest,path
  completed=sum(value.get('actual_NDK_entries',value['actual_NDK_entries_started']-1)if 'actual_NDK_entries_started'in value else value['actual_NDK_entries']for value in results.values());started=sum(value.get('actual_NDK_entries_started',value.get('actual_NDK_entries',0))for value in results.values());assert completed==18 and started==24
  result=dict(passed=True,production_sources={'windows/game_socket_sigpipe.h':args.policy_sha256},dependency_production_sources=provider,provider_manifest=provider_pin,physical_dependency_receipt=physical_pin,owned_sources={'windows/'+name:sha(source/'windows'/name)for name in OWN},policy_source=policy,source_binding={name:desc(source/name)for name in ('windows/game_socket_sigpipe.h',*sorted(provider))},NDK_caller_ELF=guest_elf,NDK_caller_manifest=guest_manifest,reused_objects=reused,reused_object_sources=object_sources,compiler=compiler,executable=desc(executable),results=results,modes=len(modes),forms=2,children=len(results),actual_NDK_entries_completed=completed,actual_NDK_entries_started=started,blocked_default_rejected_without_queue=True,ignored_blocked_signal_returns_EPIPE=True,held_inputs=held,commands=commands,limits=['The native main-thread/token/disposition and stack are TEST setup; the original game and Android inherited process dispositions are not executed or inferred.','Actual Runtime.Run, same held NDK direct/volatile-pointer socket/send caller, installed provider and real unconnected Winsock TCP socket produce EPIPE.','Unblocked default exit141 is this Windows adapter policy, not a POSIX wait-status encoding. Blocked default pending-delivery and custom SIGPIPE delivery remain explicitly unsupported/fail-closed without queuing or disposition/mask edits.','SIG_IGN is measured with actual SIGPIPE blocked; default and MSG_NOSIGNAL modes explicitly request SIGPIPE unblocked through the real mask API while retaining Android provider-owned reserved bits.','Native environment is measured at complete installed callback boundaries and inside the ignored production Notify call; no arbitrary invalid-State call is substituted.','No full host, original game, external endpoint, settings or backend operation.'])
  save(out/'acceptance.json',result);print('SOCKET-SIGPIPE-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  save(out/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc(),held_inputs=held,commands=commands));raise
if __name__=='__main__':main()

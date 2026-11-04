"""Qualified original unwind table cases on ARM and translated raw/polled hosts.

This controller uses the actual appended Windows COFF and unchanged retained
helper projections. It excludes the two inherited LDURSH error paths.
"""
import argparse,hashlib,json,re,shutil,struct,subprocess,sys,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
PARENT=W/'windows-first-frame-phdr1'
CANDIDATE_SHA='39e796e2df30442baac1b209b355c8240433f4488f2b44371685ece9d59122e6'
OBJECT_SHA='18c7f53eb9b9ffdeeaca78d4b183749cbbbc41e131ec5f54564795587c016ea9'
OWN=['unwind_cases_fixture.h','unwind_cases_native.S','unwind_cases_ref.c','unwind_cases_test.cpp','prepare_unwind_cases.py','test_unity_unwind_entries.py']
FIXTURE_HOLD={'unwind_cases_fixture.h':'a1d06334c81b27e8abd510b17419e3c4d19adcfd333134f5017ab0d0cccd2407','unwind_cases_native.S':'64868ddaf35e1dd401a5709ff8a140ec00d4c705ec10ae2d4646fe9ce4c9472c','unwind_cases_ref.c':'193c235e1d89d5daa7890dbacc4e3ff896bfa90f323938e8500f561bb6767c5e','unwind_cases_test.cpp':'c7424345e84b617dc552681669ec007c35870a260a08180f35629d006dfd3356','prepare_unwind_cases.py':'5e3b3e58de0476f93ba71309836f2a44cd2585788df9d141d6ef54bd0d6cb220'}
def sha(path):
 with Path(path).open('rb')as file:return hashlib.file_digest(file,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True);a=p.parse_args()
 O=a.out.resolve();assert not O.exists();O.mkdir();S=O/'source';S.mkdir();SUP=O/'support';SUP.mkdir();T=a.toolchain.resolve();CP=a.candidate.resolve();commands=[];inputs={};sourcepins={}
 def pin(path):path=Path(path).resolve();inputs[str(path)]=sha(path)
 def run(cmd,label,timeout=240):
  cmd=list(map(str,cmd));commands.append(dict(label=label,argv=cmd));save(O/'commands.json',commands)
  if not label.startswith('case-'):print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('x')as file:result=subprocess.run(cmd,stdout=file,stderr=subprocess.STDOUT,timeout=timeout)
  text=(O/(label+'.log')).read_text(errors='replace')
  if result.returncode:raise RuntimeError(label+' exit'+str(result.returncode)+'\n'+text[-2400:])
  return text
 try:
  assert sha(CP)==CANDIDATE_SHA;C=read(CP);assert C['passed']is True and C['definitions']==27 and C['candidate_object']['sha256']==OBJECT_SHA and len(C['added_unsupported_heads'])==22
  assert(C['State_size'],C['State_align'],C['State_type_closure_sha256'])==(1200,16,'26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137')
  pin(CP)
  for group in('input_pins','artifacts'):
   for path,digest in C[group].items():assert sha(path)==digest,path;pin(path)
  assert sha(PARENT/'game_inputs.json')=='41a52d658e5a5a92ac0bbb713cb3a313f9c61e8d68b48294540a83c45a9ec229';pin(PARENT/'game_inputs.json')
  for name in OWN:
   if name in FIXTURE_HOLD:assert sha(HERE/name)==FIXTURE_HOLD[name],name+' differs from authorized source HOLD'
   shutil.copy2(HERE/name,S/name);sourcepins[str(HERE/name)]=sha(HERE/name)
  for name in('runtime.h','runtime.cpp','cooperative_poll.h','cooperative_poll.cpp','guest_memory.h'):
   source=PARENT/'sources/recomp/whole'/name;shutil.copy2(source,SUP/name);sourcepins[str(source)]=sha(source)
  for name in('remill-lift','aarch64.bc'):
   assert C['input_pins'][str((T/name).resolve())]==sha(T/name);pin(T/name)
  for path in(T/'include').rglob('*'):
   if path.is_file():pin(path)
  projection=O/'projection'
  run([sys.executable,S/'prepare_unwind_cases.py','--candidate',CP,'--out',projection],'prepare-projection')
  P=read(projection/'projection.json');assert P['passed']is True
  required=('code','tables','traces_header','raw_ir','polled_ir')
  for key in required:
   row=P[key];assert sha(row['path'])==row['sha256'];pin(row['path'])
  shutil.copy2(P['traces_header']['path'],S/'unwind_cases_traces.h');pin(projection/'projection.json')
  code=Path(P['code']['path']);tables=Path(P['tables']['path']);assert code.stat().st_size==tables.stat().st_size==65536
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang')
  qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static')
  for path in[ndk,qemu,Path(shutil.which('clang-18')).resolve(),Path(shutil.which('clang++-18')).resolve(),Path('/mnt/c/mingw64/bin/g++.exe')]:pin(path)
  run([ndk,'-fno-emulated-tls','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(S),S/'unwind_cases_ref.c'],'arm-strict')
  run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S),S/'unwind_cases_ref.c',S/'unwind_cases_native.S','-o',O/'reference'],'arm-build')
  with(O/'reference').open('rb')as file:
   header=file.read(64);assert header[18:20]==b'\xb7\x00';phoff=struct.unpack_from('<Q',header,32)[0];width,count=struct.unpack_from('<HH',header,54);assert width==56
   tls=[]
   for index in range(count):
    file.seek(phoff+width*index);row=file.read(width)
    if struct.unpack_from('<I',row)[0]==7:tls.append(struct.unpack_from('<Q',row,48)[0])
   assert tls and all(value>=64 for value in tls),'native Bionic TLS alignment64'
  records={};observations={};fullstate={};hitmasks={};binaries={}
  def collect(key,cmd,case):
   text=run(cmd,'case-'+key+'-'+str(case),timeout=90);rec=[x for x in text.splitlines()if x.startswith('RECORD ')];obs=[x for x in text.splitlines()if x.startswith('OBSERVATION ')]
   assert len(rec)==len(obs)==1 and rec[0].startswith('RECORD case='+str(case)+' ')
   if key!='arm64':assert rec[0]==records['arm64'][case],(key,case,'800B architecture/effects mismatch')
   records[key].append(rec[0]);observations[key].append(obs[0])
   if key!='arm64':
    full=[x for x in text.splitlines()if x.startswith('FULLSTATE ')];hits=[x for x in text.splitlines()if x.startswith('HITS ')];assert len(full)==len(hits)==1
    m=re.fullmatch(r'FULLSTATE case=(\d+) bytes=1200 value=([0-9a-f]{2400}) token64=unchanged highcells=preserved',full[0]);assert m and int(m[1])==case
    h=re.fullmatch(r'HITS case=(\d+) mask=([01]{27})',hits[0]);assert h and int(h[1])==case
    fullstate[key].append(full[0]);hitmasks[key].append(h[2])
    if key.endswith('_polled'):assert full[0]==fullstate[key.replace('_polled','_raw')][case],(key,case,'full1200B raw/polled mismatch')
  records['arm64']=[];observations['arm64']=[]
  for case in range(55):collect('arm64',[qemu,O/'reference',code,tables,case],case)
  print('UNWIND-ARM64-PASS55',flush=True)
  for label,target,cxx in[('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
   D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(SUP),'-I'+conv(S)]
   run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'unwind_cases_test.cpp')],label+'-strict');common=[]
   for source in[SUP/'runtime.cpp',SUP/'cooperative_poll.cpp',S/'unwind_cases_test.cpp']:
    obj=D/(source.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if source.parent==S else[]),'-c',conv(source),'-o',conv(obj)],label+'-'+source.stem);common.append(obj)
   for kind in('raw','polled'):
    if label=='windows'and kind=='polled':obj=Path(C['candidate_object']['path']);assert sha(obj)==OBJECT_SHA;pin(obj)
    else:
     obj=D/(kind+'-entries.o');run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',C[kind+'_ir']['path'],'-o',obj],label+'-'+kind+'-entries')
    helper=D/(kind+'-helpers.o');run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',P[kind+'_ir']['path'],'-o',helper],label+'-'+kind+'-helpers')
    exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,common+[obj,helper]),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link')
    key=label+'_'+kind;records[key]=[];observations[key]=[];fullstate[key]=[];hitmasks[key]=[];binaries[key]=dict(path=str(exe),sha256=sha(exe),new_object_sha256=sha(obj),helper_object_sha256=sha(helper),actual_candidate_COFF=label=='windows'and kind=='polled')
    for case in range(55):collect(key,[exe,int(kind=='polled'),conv(code),conv(tables),case],case)
    print('UNWIND-HOST-PASS',key,55,flush=True)
  union=['0']*27
  for masks in hitmasks.values():
   for mask in masks:
    for j,value in enumerate(mask):
     if value=='1':union[j]='1'
  assert ''.join(union)=='1'*27,'every new original entry must execute in the corpus'
  for key,rows in observations.items():
   assert len(rows)==55 and all('original_words=1' in row and 'abort_body_executed=0' in row and 'old_LDURSH_const2s_skip_excluded=1' in row for row in rows)
  for path,digest in inputs.items():assert sha(path)==digest,path
  for path,digest in sourcepins.items():assert sha(path)==digest,path
  for name in OWN:assert sha(S/name)==sourcepins[str(HERE/name)],name
  record_digests={key:hashlib.sha256(('\n'.join(rows)+'\n').encode()).hexdigest()for key,rows in records.items()};assert len(set(record_digests.values()))==1
  result=dict(passed=True,scope='55 exact original table cases; original ARM and translated Linux/Windows raw/polled, no game.',records_each=55,platforms=list(records),candidate_sha256=CANDIDATE_SHA,actual_Windows_COFF_sha256=OBJECT_SHA,actual_candidate_COFF_executed_windows_polled=True,entry_heads=C['entry_heads'],definitions=27,architectural_snapshot_bytes=800,host_full_State_bytes=1200,opaque_memory_token_bytes=64,data_canaries_bytes=65536,stack_canaries_bytes=65536,record_digests=record_digests,full_state_digests={key:hashlib.sha256(('\n'.join(rows)+'\n').encode()).hexdigest()for key,rows in fullstate.items()},all27_new_entries_executed=True,entry_hit_masks=hitmasks,original_projection=P,owned_sources={str(HERE/name):sourcepins[str(HERE/name)]for name in OWN},sourcepins=sourcepins,inputs=inputs,binaries=binaries,observations=observations,corpus=dict(binary_ops=17,binary_variants=2,dereference_widths=4,dereference_variants=2,rule_variants=6,rule_inputs=2,abort_prefix_controls=1),inherited_unsupported_instruction_PCs=['0x82625a98','0x82625d78'],inherited_unsupported_instruction_bytes='80108078',excluded_original_error_paths=['const2s','skip'],actual_abort_body_executed=False,limits='Original full expression/register-rule functions return naturally for valid corpus. One shared abort-prefix case captures before abort; no abort body executes. Original code and tables, retained helper bodies and actual candidate COFF are bound. Owned TEST context/frame inputs and register-preserving memcpy bridge are labelled. 800B architecture/effects compared against originalARM, full1200B raw/polled host snapshots compared, high cells/token64/canaries checked. Two inherited LDURSH error paths excluded and preserved. No full unwinder/exception/game/frame claim.',evidence={str(path.relative_to(O)):sha(path)for path in O.rglob('*')if path.is_file()and path.name!='acceptance.json'})
  save(O/'acceptance.json',result);print('UNWIND-QUALIFIED',sha(O/'acceptance.json'),flush=True)
 except Exception as error:
  save(O/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,sourcepins=sourcepins,inputs=inputs));raise
if __name__=='__main__':main()

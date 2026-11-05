"""Qualify real Windows socket/FD transport against the same actual NDK/Bionic caller."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
OWN=('socket_transport_cases.h','socket_transport_guest.c','socket_transport_ref.c','socket_transport_test.cpp','socket_transport.md','test_socket_transport.py')
REFERENCE=OWN[:3]
PRODUCTION={'windows/filesystem.cpp','windows/filesystem.h','windows/guest_descriptors.h','windows/socket_transport.cpp','windows/socket_transport.h'}
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def hp(p):
 text=str(p)
 return Path('/mnt/'+text[0].lower()+'/'+text[3:].replace('\\','/'))if re.match(r'^[A-Za-z]:[/\\]',text)else Path(p)
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def records(p):return [s for s in Path(p).read_text().splitlines()if s.startswith('REC ')]
def digest(lines):return hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest()
def normalize(lines,bionic=False):
 result=[]
 for line in lines:
  fields=line.split(' ',6)
  if fields[4]!='-1'and fields[3]not in ('ntop_short','ntop_bad_family'):fields[5]='unspecified'
  flag_profiles={'socket_nonblock':2050,'dup_shared_status':2,'ioctl_shared_status':2050}
  if fields[3]in flag_profiles:
   expected=flag_profiles[fields[3]];assert int(fields[4])==expected+(32768 if bionic else 0),line
   if bionic:fields[4]=str(expected)
  result.append(' '.join(fields))
 return result
def api_counts(text,prefix='API '):
 result={}
 for line in text.splitlines():
  if line.startswith(prefix):
   _,mode,name,count=line.split();result.setdefault(mode,{})[name]=int(count)
 return result
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--mode',choices=('reference','qualification'),required=True)
 for k in ('ndk','out'):ap.add_argument('--'+k,type=Path,required=True)
 for k in ('lift','semantics-dir','support-source','reference','production-manifest'):ap.add_argument('--'+k,type=Path)
 a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=None):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv,component_timeout_seconds=timeout));save(out/'commands.json',commands);print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
  return (out/(label+'.log')).read_text(errors='replace')
 def regressions(source,flags,objects,loader,ndk,cxx):
  work=a.support_source/'work';result={};so=out/'dup.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/filesystem_dup_guest.c','-o',so],'regression-dup-NDK');guest=out/'dup-guest';run([sys.executable,source/'whole/compile.py',so,'--out',guest,'--base','0x76000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'regression-dup-lift');manifest=json.loads((guest/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets'];data=out/'dup-data';data.mkdir();exe=out/'filesystem-dup.exe';run([cxx,*flags,'-I'+wp(guest),'-DDUP_IMAGE="'+wp(so)+'"','-DDUP_ROOT="'+wp(data)+'"',wp(source/'windows/filesystem_dup_test.cpp'),*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-static','-pthread','-latomic','-o',wp(exe)],'regression-dup-link');text=run([exe],'regression-dup-run',120);m=re.search(r'Windows filesystem dup: (\d+) checks; (\d+) actual NDK calls/(\d+) dup calls',text);assert m;result['regular_file_dup_OFD_mapping']=dict(checks=int(m[1]),actual_NDK_calls=int(m[2]),actual_dup_calls=int(m[3]),source=desc(source/'windows/filesystem_dup_test.cpp'),NDK_source=desc(source/'windows/filesystem_dup_guest.c'),executable=desc(exe),stdout=desc(out/'regression-dup-run.log'))
  old=work/'windows-files';data=out/'filesystem-data';data.mkdir();sandbox=data/'sandbox';sandbox.mkdir();(sandbox/'bytes.bin').write_bytes(bytes((i*37+11)&255 for i in range(1000)));(sandbox/'empty.bin').write_bytes(b'')
  for n in ('sample.h','sample.json','file_traces.h','ndk_layout.json'):
   shutil.copyfile(old/n,data/n);pin(old/n)
  # Tests mount the APK read-only. Keep a second name for the same immutable
  # file, avoiding an unrelated multi-GB copy; content remains pinned pre/post.
  os.link(old/'base.apk',data/'base.apk');pin(old/'base.apk');assert sha(data/'base.apk')==held[str((old/'base.apk').resolve())]
  prior=json.loads((old/'guest/manifest.json').read_text());assert not prior['unsupported_traces']and not prior['unresolved_direct_targets'];old_objects=[old/'guest'/Path(p).name for p in prior['objects']]
  for p in [old/'guest/manifest.json',old/'file-guest.so',*old_objects,work/'zlib-native/libz-inflate.a']:pin(p)
  ff=flags+['-I'+wp(data),'-I'+wp(work/'zlib-native/zlib-1.3.2'),'-DFILES_ROOT="'+wp(data)+'"','-DHAVE_GUEST_FILE_FIXTURE','-DGUEST_FILES_IMAGE="'+wp(old/'file-guest.so')+'"'];extra=[]
  for name in ('jni_host','android_context','windows_android_id','android_assets','apk_assets'):
   obj=out/(name+'-regression.o');run([cxx,*ff,'-c',wp(source/('windows/'+name+'.cpp')),'-o',wp(obj)],'regression-'+name+'-compile');extra.append(obj)
  exe=out/'filesystem-ABI.exe';run([cxx,*ff,wp(source/'windows/filesystem_test.cpp'),*map(wp,objects+extra),wp(loader),*map(wp,old_objects),wp(work/'zlib-native/libz-inflate.a'),'-static','-pthread','-latomic','-ladvapi32','-o',wp(exe)],'regression-filesystem-link');text=run([exe],'regression-filesystem-run',120);m=re.search(r'Windows Android file ABI: (\d+) checks passed;',text);assert m;result['file_ABI_stdio_mmap']=dict(checks=int(m[1]),source=desc(source/'windows/filesystem_test.cpp'),executable=desc(exe),stdout=desc(out/'regression-filesystem-run.log'),old_NDK_manifest=desc(old/'guest/manifest.json'),APK_read_only_hardlink=True)
  return result
 try:
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk)
  if a.mode=='reference':
   source=out/'source';source.mkdir();qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');pin(qemu)
   for n in REFERENCE:shutil.copyfile(HERE/n,source/n);pin(HERE/n)
   core=out/'ndk-socket.o';exe=out/'Bionic-reference';run([ndk,'-O1','-fPIC','-fno-stack-protector','-fno-builtin','-c',source/'socket_transport_guest.c','-o',core],'compile-NDK-object');run([ndk,'-O1','-static','-fno-builtin','-fno-emulated-tls',source/'socket_transport_ref.c',core,'-o',exe],'compile-static-Bionic');programs=subprocess.check_output(['readelf','-l',str(exe)],text=True);assert 'INTERP'not in programs and 'TLS'in programs;text=run([qemu,exe,out/'file.bin'],'actual-static-Bionic',60);m=re.search(r'SOCKET-BIONIC-PASS NDK_entry_calls=(\d+) canonical_records=(\d+) TLS=17',text);lines=records(out/'actual-static-Bionic.log');counts=api_counts(text);assert m and len(lines)==int(m[2])and len(counts)==2 and all(len(values)==29 and all(n>0 for n in values.values())for values in counts.values());assert sum(sum(values.values())for values in counts.values())==int(m[1]);assert all(sha(p)==h for p,h in held.items())
   result=dict(passed=True,actual_static_Bionic=True,reference_sources={'windows/'+n:sha(source/n)for n in REFERENCE},canonical_records=dict(count=len(lines),sha256=digest(normalize(lines,True))),raw_records=dict(count=len(lines),sha256=digest(lines)),comparison_rule='Canonical validated logical steps. Successful-operation errno is unspecified; only Bionic socket_nonblock/dup_shared_status/ioctl_shared_status records remove proven QEMU8.2.2 spurious0x8000, with all other bits and exact Windows2/2050 required. FD identities/ephemeral ports/pipe capacity and nonblocking immediate-or-pending connect remain raw observations and are compared by explicit relations. Failed errno and all remaining canonical fields remain exact.',actual_NDK_entry_calls=int(m[1]),api_entry_calls=counts,NDK_object=desc(core),reference=desc(exe),stdout=desc(out/'actual-static-Bionic.log'),NDK_compiler=desc(ndk),qemu=desc(qemu),no_PT_INTERP=True,native_TLS=True,SIGPIPE_ignored_in_reference=True,commands=commands)
  else:
   assert all((a.lift,a.semantics_dir,a.support_source,a.reference,a.production_manifest));production=json.loads(a.production_manifest.read_text());assert set(production)==PRODUCTION;source=out/'source'
   for folder in ('windows','whole','fastaes'):
    target=source/folder;target.mkdir(parents=True)
    for f in(a.support_source/folder).iterdir():
     if f.is_file()and f.suffix in ('.h','.cpp','.c','.inc','.py','.md'):shutil.copyfile(f,target/f.name)
   for n in OWN:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
   for n,h in production.items():assert sha(source/n)==sha(HERE.parent/n)==h;pin(HERE.parent/n)
   pin(a.production_manifest);ref=json.loads(a.reference.read_text());assert ref['passed']is True and ref['actual_static_Bionic']is True;pin(a.reference)
   for n in REFERENCE:assert ref['reference_sources']['windows/'+n]==sha(source/'windows'/n)
   for name in ('NDK_object','reference','stdout','NDK_compiler','qemu'):row=ref[name];assert sha(row['path'])==row['sha256'];pin(row['path'])
   native=records(ref['stdout']['path']);assert ref['canonical_records']==dict(count=len(native),sha256=digest(normalize(native,True)))and ref['raw_records']==dict(count=len(native),sha256=digest(native));save(out/'Bionic-reference.json',ref);core=Path(ref['NDK_object']['path']);base=a.support_source/'work/windows-first-frame-resolver1/sources/recomp';binding=dict(passed=True,production_sources=production,baseline_sources={n:desc(base/n)for n in ('windows/filesystem.cpp','windows/filesystem.h')},candidate_sources={n:desc(source/n)for n in production});save(out/'source-binding.json',binding)
   evidence_root=a.support_source/'work';exception_evidence={n:desc(evidence_root/n)for n in ('socket-transport-reference3/source/socket_transport_cases.h','socket-transport-reference3/actual-static-Bionic.log','socket-native-error-probe1/probe.cpp','socket-native-error-probe1/probe.exe','socket-native-error-probe1/actual-Windows.log')}
   for row in exception_evidence.values():pin(row['path'])
   primary_audit=evidence_root/'socket-native-defaults-audit1/acceptance.json';assert sha(primary_audit)=='7f46c6ff7b87ac71f16423a5f37f338c6db3dc54f93e2e136aa9fbee264d08f7';pin(primary_audit);audit=json.loads(primary_audit.read_text());assert audit['passed']is True and audit['findings']['qemu_type99_errno93_is_not_Android_kernel_equivalence']is True;primary_files={}
   for name,row in audit['sources'].items():
    path=hp(row['path']);assert sha(path)==row['sha256'];pin(path);primary_files[name]=desc(path)
   fcntl_audit=evidence_root/'socket-fcntl-qemu-audit1/acceptance.json';assert sha(fcntl_audit)=='a0f97be4948a77589437690a5e3320e18cc9413dd6c5712cbbf244985ef69445';pin(fcntl_audit);fcntl_proof=json.loads(fcntl_audit.read_text());assert fcntl_proof['passed']is True and fcntl_proof['normalization']['side']=='Bionic only';fcntl_evidence={}
   for name,row in fcntl_proof['sources'].items():assert sha(row['path'])==row['sha256'];pin(row['path']);fcntl_evidence[name]=row
   pin(a.lift);pin(a.semantics_dir/'aarch64.bc');guest=out/'socket.so';run([ndk,'-shared','-nostdlib',core,'-o',guest],'link-NDK-caller');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x7b000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK-Windows');manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets'];cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cc);pin(cxx);loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.support_source/'work/remill-src/include')];focused=flags+['-I'+wp(translated),'-DSOCKET_LIBRARY="'+wp(guest)+'"','-DSOCKET_ROOT="'+wp(out/'data-sockets')+'"'];run([cxx,*focused,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(source/'windows/socket_transport_test.cpp')],'focused-precheck');objects={}
   for relative in ('windows/filesystem.cpp','windows/growdown_memory.cpp','windows/socket_transport.cpp','whole/runtime.cpp','windows/socket_transport_test.cpp'):
    obj=out/(Path(relative).stem+'.o');run([cxx,*(focused if relative.endswith('_test.cpp')else flags),*(['-Wall','-Wextra','-Werror']if relative.endswith('_test.cpp')else[]),'-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem);objects[relative]=obj
   exe=out/'socket-transport.exe';run([cxx,*map(wp,objects.values()),wp(loader),*map(wp,manifest['objects']),'-Wl,--wrap='+WRAP,'-static','-pthread','-latomic','-lws2_32','-o',wp(exe)],'link-Windows');text=run([exe],'actual-Windows',120);m=re.search(r'SOCKET-TRANSPORT-PASS checks=(\d+) canonical_NDK_entry_calls=(\d+) actual_NDK_entry_calls=(\d+) canonical_records=(\d+) bridge_calls=(\d+) APIs=(\d+) forms=2 State=1200 Memory64=1 nativeTCP=1 nativeUDP=1 concurrentPipe=1',text);assert m;host=records(out/'actual-Windows.log');assert normalize(native,True)==normalize(host),next((str(i)+': '+x[:150]+' != '+y[:150]for i,(x,y)in enumerate(zip(normalize(native,True),normalize(host)))if x!=y),'record count mismatch');assert len(host)==int(m[4]);counts=api_counts(text);assert len(counts)==2 and all(len(values)==29 and all(n>0 for n in values.values())for values in counts.values())and sum(sum(values.values())for values in counts.values())==int(m[2]);assert int(m[3])>int(m[2]);save(out/'focused-acceptance.json',dict(passed=True,production_sources=production,checks=int(m[1]),canonical_NDK_entry_calls=int(m[2]),actual_NDK_entry_calls=int(m[3]),canonical_records=ref['canonical_records'],executable=desc(exe),stdout=desc(out/'actual-Windows.log')))
   regress=regressions(source,flags,[objects[n]for n in ('windows/filesystem.cpp','windows/growdown_memory.cpp','whole/runtime.cpp')],loader,ndk,cxx)
   assert all(sha(p)==h for p,h in held.items());raw_differences=[dict(record=i,Bionic=x,Windows=y)for i,(x,y)in enumerate(zip(native,host))if x!=y];totals={line.split()[1]:int(line.split()[2])for line in text.splitlines()if line.startswith('TOTAL-API ')};assert len(totals)==29 and sum(totals.values())==int(m[3]);qemu_exception=dict(excluded_from_canonical_comparison=True,input_type=99,raw_QEMU_errno=93,Windows_kernel_contract_errno=22,reason='QEMU linux-user target_to_host_sock_type drops unknown socket flag bits before host syscall; Linux __sys_socket rejects those flags before protocol validation.',evidence=exception_evidence,primary_source_audit=desc(primary_audit),primary_source_files=primary_files,F_GETFL_named_record_artifact=dict(audit=desc(fcntl_audit),primary_sources=fcntl_evidence,normalization=fcntl_proof['normalization']))
   result=dict(passed=True,production_sources=production,owned_sources={'windows/'+n:sha(source/'windows'/n)for n in OWN},source_binding=desc(out/'source-binding.json'),Bionic_reference=desc(out/'Bionic-reference.json'),NDK_object=desc(core),differential_records=dict(count=len(host),sha256=digest(normalize(host))),raw_Windows_records=dict(count=len(host),sha256=digest(host)),comparison_rule=ref['comparison_rule'],raw_canonical_differences=raw_differences,known_QEMU_socket_flag_exception=qemu_exception,platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),canonical_NDK_entry_calls=int(m[2]),actual_NDK_entry_calls=int(m[3]),canonical_records=int(m[4]),bridge_calls=int(m[5]),APIs=int(m[6]),forms=2,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],canonical_api_entry_calls=counts,total_api_entry_calls=totals,native_environment_guarded_imports=[n for n in totals if n not in ('open','lseek')],executable=desc(exe),stdout=desc(out/'actual-Windows.log'))),regressions=regress,physical_collector_admission_claim=False,controls=['same actual typedNDKdispatcher object in actualstaticBionic and translatedWindows','all29APIs bothdirectandvolatilepointer forms; accurateentrycounts separatefromlogicalrecords','AndroidLP64 socket/ioctl/poll widths and pollfd/fdset/timeval/iovec/msghdr layout','genuineTCPUDP nativepeerbytes independentofprovidercalls including131111bytevectoredTCPpartialsend/fullWAITALL','nonblockingconnect completion/SO_ERROR/peek/options/halfclose andcontextualerrno','ownedunifiedsocket/file/pipeFDnamespace, sharedOFDflags vsperdescriptorCLOEXEC andaliasclosure','completepayloads/lengths/canaries andUDPvector/truncationsemantics','mixedpoll/select andkernelprefixonlyfdsetpublication','boundedpipeatomic4096pressure,64concurrent32byterecords,EOF/EPIPEandobservedblockingreadprogress;196643byteblockingwritewithdrainer','nativeerrno LastError nonzeroFENV on27listedimports andState1200/Memory64 atactualboundary','unchangedregularFileSystem/OFD/seek/mmap/stdio regressionsagainstcurrentfrozenprovider'],held_inputs=held,commands=commands,limits='This is local real TCP/UDP and owned byte-channel qualification, not external network or original-game evidence. Logical record counts differ from actual NDK entry counts; short I/O/pipe capacity/nonblocking connect timing can differ across OS and are retained as raw observations. Successful errno is unspecified and normalized; failed errno remains exact. QEMU drops unknown socket flag bits, so that known kernel-contract case is explicitly separate from canonical equivalence. SIGPIPE is ignored only in the standalone Bionic reference; managed signal delivery and physical collector socket-wait admission are separate gates. No network settings, external endpoints, fabricated game result or full host/game run. Optional interface binding/enumeration, ancillary control payloads, valid unsupported socket kinds and regular-file F_SETFL outside retained file policy are explicit unqualified capabilities.')
  save(out/'acceptance.json',result);print('SOCKET-TRANSPORT-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  save(out/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held));raise
if __name__=='__main__':main()

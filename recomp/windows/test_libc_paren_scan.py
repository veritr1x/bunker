"""Actual static NDK Bionic versus Windows for original (%u) format and four prior status-line formats."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
OWN=('libc_paren_scan_cases.h','libc_paren_scan_guest.c','libc_paren_scan_ref.c','libc_paren_scan_test.cpp','test_libc_paren_scan.py')
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def records(path):return [s for s in Path(path).read_text().splitlines()if s.startswith('REC ')]
def rdigest(lines):return hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in('ndk','lift','semantics-dir','out'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--qemu',type=Path,default=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static'));p.add_argument('--reference',type=Path);p.add_argument('--reference-only',action='store_true');p.add_argument('--production-cpp-sha256');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);source=out/'source';work=HERE.parent/'work';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label):
  argv=list(map(str,argv));commands.append({'stage':label,'argv':argv});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  # Freeze required sources and all local headers; avoid unrelated test CPPs.
  for folder in('windows','whole','fastaes'):
   target=source/folder;target.mkdir(parents=True)
   for f in(HERE.parent/folder).iterdir():
    if f.is_file()and (f.suffix in('.h','.inc','.py')or f.name in('libc.cpp','runtime.cpp','elfload.c','libc_scan_profiles_test.cpp','libc_scan_profiles_guest.c','libc_scan_profiles_ref.c')or f.name in OWN):shutil.copyfile(f,target/f.name)
  for name in OWN:pin(HERE/name)
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.qemu)
  libc_archive=Path(subprocess.check_output([str(ndk),'--print-file-name=libc.a'],text=True).strip());pin(libc_archive)
  if a.reference:
   ref=json.loads(a.reference.read_text());assert ref['passed']and ref['actual_static_Bionic']
   for name in OWN[:3]:assert ref['reference_sources'][name]==sha(source/'windows'/name)
   for key in('NDK_object','executable','stdout','NDK_compiler','Bionic_libc_archive','qemu'):item=ref[key];assert sha(item['path'])==item['sha256'];pin(item['path'])
   pin(a.reference);core=Path(ref['NDK_object']['path']);native=records(ref['stdout']['path']);assert ref['records']=={'count':len(native),'sha256':rdigest(native)}
  else:
   core=out/'ndk-paren-scan.o';run([ndk,'-O1','-fPIC','-fno-stack-protector','-fno-builtin','-D_FORTIFY_SOURCE=0','-c',source/'windows/libc_paren_scan_guest.c','-o',core],'compile-NDK-caller');reference=out/'Bionic-reference';run([ndk,'-O1','-static','-fno-builtin','-fno-emulated-tls',source/'windows/libc_paren_scan_ref.c',core,'-o',reference],'compile-static-Bionic')
   with reference.open('rb')as f:
    elf=ELFFile(f);segments=list(elf.iter_segments());assert elf['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in segments);tls=[s for s in segments if s['p_type']=='PT_TLS'];assert len(tls)==1 and tls[0]['p_align']>=64
   run([a.qemu,reference],'actual-static-Bionic');native=records(out/'actual-static-Bionic.log');assert 'PAREN-SCAN-BIONIC-PASS' in(out/'actual-static-Bionic.log').read_text()
   assert len(native)%2==0 and all(int(row.split()[1])==n%(len(native)//2)and int(row.split()[2])==n//(len(native)//2)for n,row in enumerate(native))
   ref={'passed':True,'actual_static_Bionic':True,'reference_sources':{name:sha(source/'windows'/name)for name in OWN[:3]},'NDK_object':desc(core),'executable':desc(reference),'stdout':desc(out/'actual-static-Bionic.log'),'NDK_compiler':desc(ndk),'Bionic_libc_archive':desc(libc_archive),'qemu':desc(a.qemu),'records':{'count':len(native),'sha256':rdigest(native)},'no_PT_INTERP':True,'PT_TLS_alignment':tls[0]['p_align'],'scope':'Actual static NDK Bionic C-locale scanner, same caller object used on Windows. Out-of-int32 range and token512 cases flagged implementation observations, not portable C guarantees.'}
  (out/'Bionic-reference.json').write_text(json.dumps(ref,indent=2)+'\n')
  if a.reference_only:
   (out/'acceptance.json').write_text(json.dumps(ref,indent=2)+'\n');print('PAREN-SCAN-REFERENCE',sha(out/'acceptance.json'),flush=True);return
  assert a.production_cpp_sha256
  production={'windows/libc.cpp':a.production_cpp_sha256,'windows/libc.h':'c905aeabd038efa235a934702f3a132e19f7e475ad6f1b1843e85022b11f749c'}
  for name,h in production.items():assert sha(source/name)==h and sha(HERE.parent/name)==h;pin(HERE.parent/name)
  dependency={'windows/libc_resolver_detail.h':sha(source/'windows/libc_resolver_detail.h')}
  parent=work/'windows-first-frame-socket-tls1/sources/recomp/windows/libc.cpp'
  def imports(path):return re.findall(r'"([^"]+)"',path.read_text().split('const char *const imports[] = {',1)[1].split('};',1)[0])
  assert imports(source/'windows/libc.cpp')==imports(parent);pin(parent)
  pin(a.lift);pin(a.semantics_dir/'aarch64.bc');cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cc);pin(cxx)
  guest=out/'paren-scan.so';run([ndk,'-shared','-nostdlib',core,'-o',guest],'link-NDK-caller');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x7d000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK-Windows');manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(work/'remill-src/include'),'-I'+wp(translated),'-DPAREN_SCAN_LIBRARY="'+wp(guest)+'"'];objects=[]
  for relative in('windows/libc.cpp','whole/runtime.cpp','windows/libc_paren_scan_test.cpp'):
   obj=out/(Path(relative).stem+'.o');strict=['-Wall','-Wextra','-Werror']if relative.endswith('_test.cpp')else[];run([cxx,*flags,*strict,'-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'paren-scan.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-Wl,--wrap='+WRAP,'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows');run([exe],'actual-Windows');text=(out/'actual-Windows.log').read_text();m=re.search(r'PAREN-SCAN-PASS checks=(\d+) canonical_NDK_calls=(\d+) actual_NDK_calls=(\d+) implementation_observation_records=(\d+) formats=5 forms=2 State=1200 Memory64=1',text);assert m;host=records(out/'actual-Windows.log');assert host==native,next((f'{i}: {x[:75]} != {y[:75]}'for i,(x,y)in enumerate(zip(native,host))if x!=y),'record count mismatch');assert len(host)==int(m[2])
  # Existing four string profiles and %llu regression with original static
  # Bionic records and exactly the original NDK object, current LibC/runtime.
  oldpath=work/'libc-scan-profiles-reference1/acceptance.json';old=json.loads(oldpath.read_text());assert old['passed']and old['actual_static_Bionic'];pin(oldpath)
  for name in('libc_scan_profiles_cases.h','libc_scan_profiles_guest.c','libc_scan_profiles_ref.c'):assert old['reference_sources']['windows/'+name]==sha(source/'windows'/name)
  for name in('NDK_object','reference','stdout'):item=old[name];assert sha(item['path'])==item['sha256'];pin(item['path'])
  olddir=out/'old-profiles';olddir.mkdir();oldguest=olddir/'scan.so';run([ndk,'-shared','-nostdlib',old['NDK_object']['path'],'-o',oldguest],'link-old-NDK-caller');ot=olddir/'guest';run([sys.executable,source/'whole/compile.py',oldguest,'--out',ot,'--base','0x7b000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-old-profiles');om=json.loads((ot/'manifest.json').read_text());assert not om['unsupported_traces']and not om['unresolved_direct_targets'];oe=olddir/'scan.exe'
  of=[f for f in flags if not f.startswith('-I')and not f.startswith('-DPAREN_SCAN_LIBRARY=')];run([cxx,*of,'-I'+wp(ot),'-DSCAN_LIBRARY="'+wp(oldguest)+'"','-Wall','-Wextra','-Werror',wp(source/'windows/libc_scan_profiles_test.cpp'),*map(wp,objects[:2]),wp(loader),*map(wp,om['objects']),'-Wl,--wrap='+WRAP,'-static','-pthread','-latomic','-o',wp(oe)],'link-old-profiles');run([oe],'old-profiles');oldtext=(out/'old-profiles.log').read_text();oldm=re.search(r'SCAN-PROFILES-PASS checks=(\d+) NDK_calls=(\d+)',oldtext);assert oldm;oldrecords=records(out/'old-profiles.log');assert oldrecords==records(old['stdout']['path'])and len(oldrecords)==int(oldm[2])
  for path,h in held.items():assert sha(path)==h,path
  result={'passed':True,'production_sources':production,'dependency_production_sources':dependency,'owned_sources':{name:sha(source/'windows'/name)for name in OWN},'Bionic_reference':desc(out/'Bionic-reference.json'),'NDK_object':desc(core),'differential_records':{'count':len(host),'sha256':rdigest(host),'raw_errno_compared':True,'normalizations':[]},'focus':{'checks':int(m[1]),'canonical_NDK_calls':int(m[2]),'actual_NDK_calls':int(m[3]),'implementation_observation_records':int(m[4]),'formats':5,'forms':2,'traces':len(manifest['traces']),'objects':len(manifest['objects']),'manifest':desc(translated/'manifest.json'),'executable':desc(exe),'stdout':desc(out/'actual-Windows.log')},'old_scanner_regression':{'checks':int(oldm[1]),'actual_NDK_calls':int(oldm[2]),'reference':desc(oldpath),'records':{'count':len(oldrecords),'sha256':rdigest(oldrecords)},'stdout':desc(out/'old-profiles.log'),'executable':desc(oe)},'source_snapshot':{str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},'unchanged_import_markers':imports(parent),'held_inputs':held,'commands':commands,'limits':'Exact original (%u) plus four prior status formats; prior four string/%llu profiles retained. Out-of-int32 and token512 cases are labeled Bionic implementation observations, not portable ISO C overflow guarantees. Complete result/output/canary/errno equality, no field normalization. Actual runtime input/status and completed TLS verification are unlogged, not inferred. Positive main counts include direct/pointer canonical plus4 alias/mismatch and16 concurrent calls; old regression separate. No general scanf/vsscanf support, invalid-C-pointer requirement, fullhost/game or network replay.'}
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PAREN-SCAN-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps({'passed':False,'error':str(e),'traceback':traceback.format_exc(),'commands':commands,'held_inputs':held},indent=2)+'\n');raise
if __name__=='__main__':main()

"""Narrow original Unity CA-export JNI gate, real Windows public ROOT oracle."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
PRODUCTION=('java_tls_trust.h','java_tls_trust.cpp','jni_host.h','jni_host.cpp')
PINS=('bf30ec0997442a250575b0b3b24d06a3f4e9470823ab69054f46f99a913c47aa','e8353b7012c5ed3b8552f8365515f2d4a4649897940702f418a01d963d0d46dd','ffdb00a30c00a8b4e4bfed4dd1db977d53f44a4bdeb6afa691b0d02cdab2ddc9','3299e8bd9673bf745591d39e35a64ac5ad9489e233f3d3b0f7f2b0b8413f9eba')
OWNED=('java_tls_trust_guest.c','java_tls_trust_test.cpp','java_tls_trust_roots.ps1','test_java_tls_trust.py')
def digest(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','out'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Preserve previous qualification';out.mkdir(parents=True);source=out/'source'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(parents=True)
  for f in(HERE.parent/directory).iterdir():
   if f.is_file()and f.suffix in('.h','.c','.cpp','.inc','.py','.ps1'):shutil.copyfile(f,target/f.name)
 assert tuple(digest(source/'windows'/f)for f in PRODUCTION)==PINS,'Production freeze changed'
 result={'production_sources':dict(zip(PRODUCTION,PINS)),'fixture_sources':{f:digest(source/'windows'/f)for f in OWNED},'support_sources':{str(f.relative_to(source)):digest(f)for f in source.rglob('*')if f.is_file()},'scope':'Original Unity accepted-issuer DER export only; native UnityTLS verification unchanged. Windows public-root sets are environment-specific, not cross-OS identical.', 'peer_verification_claim':False,'platform':'native Windows x86_64'}
 (out/'source-binding.json').write_text(json.dumps(result,indent=2)+'\n')
 def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 commands=out/'commands.jsonl'
 def run(command,log):
  command=list(map(str,command))
  with commands.open('a')as stream:stream.write(json.dumps(command)+'\n')
  observed=subprocess.run(command,capture_output=True,text=True)
  (out/(log+'.stdout.log')).write_text(observed.stdout);(out/(log+'.stderr.log')).write_text(observed.stderr)
  if observed.returncode:print(observed.stdout[-3000:],observed.stderr[-5000:],file=sys.stderr)
  observed.check_returncode();return observed
 oracle=run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',hp(source/'windows/java_tls_trust_roots.ps1'),'-OutputFile',hp(out/'roots-public.derbundle')],'oracle')
 result['oracle']=json.loads(oracle.stdout.strip());assert result['oracle']['passed']and result['oracle']['output_sha256']==digest(out/'roots-public.derbundle')
 shutil.copyfile(HERE.parent/'work/windows-files/sample.h',out/'sample.h')
 jni=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h';shutil.copyfile(jni,out/'jni.h');result['jni_header_sha256']=digest(jni)
 guest=out/'java-tls-trust.so';ndkcc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 run([ndkcc,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/java_tls_trust_guest.c','-o',guest],'ndk')
 translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x7c000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift')
 manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
 result['guest']={'library_sha256':digest(guest),'manifest_sha256':digest(translated/'manifest.json'),'traces':len(manifest['traces']),'objects':len(manifest['objects']),'toolchain':manifest['toolchain']}
 cc='/mnt/c/mingw64/bin/gcc.exe';cxx='/mnt/c/mingw64/bin/g++.exe';loader=out/'elfload.o';run([cc,'-O2','-c',hp(source/'fastaes/elfload.c'),'-o',hp(loader)],'loader')
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(HERE.parent/'work/remill-src/include'),'-I'+hp(out),'-I'+hp(translated)]
 objects=[]
 for rel in('windows/jni_host.cpp','windows/java_tls_trust.cpp','whole/runtime.cpp'):
  obj=out/(Path(rel).stem+'.o');run([cxx,*flags,'-c',hp(source/rel),'-o',hp(obj)],Path(rel).stem);objects.append(obj)
 exe=out/'java-tls-trust.exe'
 run([cxx,*flags,'-Wall','-Wextra','-Werror',f'-DTLS_LIBRARY="{hp(guest)}"',f'-DROOT_BUNDLE="{hp(out/"roots-public.derbundle")}"',hp(source/'windows/java_tls_trust_test.cpp'),*map(hp,objects),hp(loader),*map(hp,manifest['objects']),'-static','-pthread','-latomic','-o',hp(exe)],'link')
 focus=run([exe],'focus');print(focus.stdout,flush=True);m=re.search(r'JAVA-TLS-TRUST-PASS checks=(\d+) actual_NDK_entry_calls=(\d+) forms=(\d+),(\d+),(\d+)',focus.stdout);assert m
 counts={name:int(count)for name,count in re.findall(r'^NDK-CALL (\S+) (\d+)$',focus.stdout,re.M)};assert sum(counts.values())==int(m[2]);result['focus']={'checks':int(m[1]),'actual_NDK_entry_calls':int(m[2]),'forms':list(map(int,m.group(3,4,5))),'caller_counts':counts,'binary_sha256':digest(exe),'stdout_sha256':digest(out/'focus.stdout.log')}
 revoked=subprocess.run([str(exe),'--revoked'],capture_output=True,text=True);(out/'revoked.stdout.log').write_text(revoked.stdout);(out/'revoked.stderr.log').write_text(revoked.stderr);assert revoked.returncode==9 and 'Java public TLS trust service is revoked' in revoked.stderr;result['revoked']={'returncode':revoked.returncode,'stderr':revoked.stderr,'scope':'Separate child proves real installed JNI fail-closed boundary, not a catchable native callback exception.'}
 # One existing positive Windows interface-proxy regression, recompiled against
 # the current JNI catalog. Its calls omit the new optional parent-interface arg.
 proxy=out/'proxy';proxy.mkdir();pg=proxy/'proxy.so'
 run([ndkcc,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*[source/'windows'/n for n in('package_guest_fixture.c','java_init_guest.c','settings_secure_guest.c','jni_interface_proxy_guest.c')],'-o',pg],'proxy-ndk')
 pt=proxy/'guest';run([sys.executable,source/'whole/compile.py',pg,'--out',pt,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'proxy-lift');pm=json.loads((pt/'manifest.json').read_text());assert not pm['unsupported_traces']and not pm['unresolved_direct_targets']
 pf=[*flags,'-I'+hp(pt),'-I'+hp(HERE.parent/'work/zlib-native/zlib-1.3.2')]
 # traces.h must select this caller rather than the TLS caller.
 pf=[f for f in pf if f!='-I'+hp(translated)];po=[objects[0],objects[2]]
 for rel in('android_context.cpp','windows_android_id.cpp','jni_interface_proxy.cpp','android_assets.cpp','apk_assets.cpp'):
  obj=proxy/(Path(rel).stem+'.o');run([cxx,*pf,'-c',hp(source/'windows'/rel),'-o',hp(obj)],'proxy-'+Path(rel).stem);po.append(obj)
 pe=proxy/'proxy.exe';run([cxx,*pf,'-Wall','-Wextra','-Werror',f'-DPACKAGE_IMAGE="{hp(pg)}"',hp(source/'windows/jni_interface_proxy_test.cpp'),*map(hp,po),hp(loader),*map(hp,pm['objects']),hp(HERE.parent/'work/zlib-native/libz-inflate.a'),'-static','-pthread','-latomic','-ladvapi32','-o',hp(pe)],'proxy-link')
 pr=run([pe],'proxy-regression');print(pr.stdout,flush=True);assert 'checks passed' in pr.stdout;result['interface_proxy_regression']={'stdout':pr.stdout,'binary_sha256':digest(pe),'manifest_sha256':digest(pt/'manifest.json')}
 result['passed']=True;result['artifact_sources_unchanged']=all(digest(source/'windows'/f)==pin for f,pin in zip(PRODUCTION,PINS));assert result['artifact_sources_unchanged'];(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()

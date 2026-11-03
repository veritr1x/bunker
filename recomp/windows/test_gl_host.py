"""Frozen NDK typed query matrix against real ANGLE; explicit scalar additions."""
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('gl_host.cpp','gl_host_test.cpp','gl_host_guest.c','test_gl_host.py')
PROTECTED=('windows/gl_host.h','windows/egl_host.h','windows/egl_host.cpp','windows/native_window.h','windows/native_window.cpp','windows/jni_host.h','windows/jni_host.cpp','whole/runtime.h','whole/runtime.cpp','windows/gl_scalar_commands.inc','windows/gl_draw_commands.inc')+tuple('windows/gl_'+group+'_'+kind+'.inc'for group in('texture','uniform','framebuffer','misc','indexed')for kind in('commands','impl'))
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ndk',type=Path,required=True);p.add_argument('--lift',type=Path,required=True);p.add_argument('--remill',type=Path);p.add_argument('--cxx',default='clang++-18');p.add_argument('--support-commit',default='981cea5f75ba130ec746d0aef8f0a72ab5b38ccd');p.add_argument('--expected-old-rows',type=int,default=137);p.add_argument('--added-scalar',type=lambda text:int(text,0),action='append',help='Exact appended scalar enum, repeat in table order');p.add_argument('--out',type=Path,default=HERE.parent/'work/gl-framebuffer-bit-width-qualification1');a=p.parse_args();added=a.added_scalar if a.added_scalar is not None else[0xd52,0xd53,0xd54,0xd55,0xd56,0xd57];assert added and len(set(added))==len(added)and all(0<=n<=0xffffffff for n in added);O=a.out.resolve();O.mkdir(exist_ok=False)
 def hp(q):return subprocess.check_output(['wslpath','-m',str(Path(q).resolve())],text=True).strip()
 commands=[]
 def run(cmd,name,timeout=180):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with(O/(name+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(name+' exit'+str(r.returncode)+'\n'+(O/(name+'.log')).read_text(errors='replace')[-4000:])
  return(O/(name+'.log')).read_text()
 commit=subprocess.check_output(['git.exe','-C',hp(HERE.parent.parent),'rev-parse',a.support_commit],text=True).strip();archive=subprocess.check_output(['git.exe','-C',hp(HERE.parent.parent),'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(O/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tf:tf.extractall(O/'source',filter='data')
 S=O/'source/recomp';old_gl=(S/'windows/gl_host.cpp').read_text();pattern=r'const std::vector<GlHost::Query> queries=\{(.*?)\n\};';before=re.search(pattern,old_gl,re.S);assert before
 for name in OWN:shutil.copy2(HERE/name,S/'windows'/name)
 new_gl=(S/'windows/gl_host.cpp').read_text();after=re.search(pattern,new_gl,re.S);assert after
 assert old_gl[:before.start(1)]+old_gl[before.end(1):]==new_gl[:after.start(1)]+new_gl[after.end(1):],'change outside query catalog'
 old_rows=re.findall(r'\{[^{}]+\}',before[1]);new_rows=re.findall(r'\{[^{}]+\}',after[1]);assert len(old_rows)==a.expected_old_rows and new_rows[:len(old_rows)]==old_rows and len(new_rows)==len(old_rows)+len(added),'old query prefix or exact requested additions differs'
 assert all(re.fullmatch(r'\{\s*\w+\s*,\s*1\s*\}',row)for row in new_rows[len(old_rows):]),'new query must be scalar with no count query'
 (O/'gl_query_expected.h').write_text('#pragma once\nstatic const bunker::windows::GlHost::Query kOldQueries[]={'+before[1]+'\n};\nstatic const GLenum kAddedScalarQueries[]={'+','.join(map(hex,added))+'};\n')
 protected={n:sha(HERE.parent/n)for n in PROTECTED}
 for n,h in protected.items():assert sha(S/n)==h,'unchanged provider source differs: '+n
 T=a.lift.resolve().parent;assert(T/'aarch64.bc').is_file();include=(T/'include')if(T/'include').is_dir()else a.remill/'include';CC=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';ANGLE=HERE.parent/'work/angle-native';DLL=ANGLE/'bundle/bin'
 sources={str(f):sha(f)for f in S.rglob('*')if f.is_file()};inputs={str(f.resolve()):sha(f.resolve())for f in(CC,a.lift,T/'aarch64.bc',Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which(a.cxx)).resolve())}
 for directory in(include,ANGLE/'src/include',DLL):
  for f in directory.rglob('*'):
   if f.is_file():inputs[str(f)]=sha(f)
 for name in OWN:inputs[str(HERE/name)]=sha(HERE/name)
 (O/'source-pin.json').write_text(json.dumps(dict(base_commit=commit,base_archive_sha256=sha(O/'support.tar'),sources=sources,inputs=inputs,protected=protected,owned={n:sha(S/'windows'/n)for n in OWN},old_query_rows=len(old_rows),new_query_rows=len(new_rows),added_scalar_names=list(map(hex,added))),indent=2)+'\n')
 library=O/'queries.so';run([CC,'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/gl_host_guest.c','-o',library],'ndk-build')
 G=O/'guest';run([sys.executable,S/'whole/compile.py',library,'--out',G,'--lift',a.lift,'--semantics-dir',T,'--cxx',a.cxx,'--base','0x5c000000','--target','x86_64-w64-windows-gnu'],'translate');m=json.loads((G/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 loader=O/'elfload.o';run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',hp(S/'fastaes/elfload.c'),'-o',hp(loader)],'loader')
 cxx='/mnt/c/mingw64/bin/g++.exe';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(include),'-I'+hp(G),'-I'+hp(O),'-I'+hp(ANGLE/'src/include'),f'-DGL_HOST_LIBRARY="{hp(library)}"',f'-DGL_HOST_DLL_DIRECTORY=L"{hp(DLL)}"'];objects=[]
 for rel in('windows/gl_host_test.cpp','windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp'):
  source=S/rel;obj=O/(source.stem+'.o');strict=['-Wall','-Wextra','-Werror']if source.stem in('gl_host','gl_host_test','egl_host','native_window')else[];run([cxx,*flags,*strict,'-c',hp(source),'-o',hp(obj)],source.stem+'-build');objects.append(obj)
 binary=O/'test.exe';run([cxx,'-static',*map(hp,objects),hp(loader),*map(hp,m['objects']),'-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',hp(binary)],'link');text=run([binary],'focused',65);assert'GL query host:'in text
 for group in(sources,inputs):
  for n,h in group.items():assert sha(n)==h,n
 for n,h in protected.items():assert sha(HERE.parent/n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');r=dict(passed=True,base_commit=commit,owned_sources={n:sha(S/'windows'/n)for n in OWN},protected_sources=protected,source_pin_sha256=sha(O/'source-pin.json'),old_query_rows=len(old_rows),query_rows=len(new_rows),added_scalar_names=list(map(hex,added)),old_prefix_preserved=True,other_gl_source_unchanged=True,stdout=text,heads=len(m['traces']),objects=len(m['objects']),executable_sha256=sha(binary),scope='Existing actual NDK integer/float/one-byte boolean query catalog matrix against the current native ANGLE context with complete guards/errors/tracked writes; exact requested scalar widths only; no game or rendering qualification.',limits=['Only the actual current ANGLE GLES3.1+ context is exercised, not a GLES2 context or every original conditional branch.','Original NV_coverage_sample queries8ed3/8ed4 remain outside this six-bit-query addition.'],evidence={str(f):sha(f)for f in O.rglob('*')if f.is_file()and'source'not in f.relative_to(O).parts});(O/'acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print('GL-QUERY-WIDTH-PASS',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()

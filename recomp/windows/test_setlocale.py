"""Bounded Android13 setlocale against strict NDK callers and frozen locale/LibC regressions."""
import argparse,hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('libc.h','libc.cpp','setlocale_guest.c','setlocale_test.cpp','test_setlocale.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','support-source','out'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Use a fresh directory; preserve every earlier candidate';out.mkdir(parents=True);source=out/'source';work=HERE.parent/'work'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(parents=True)
  for f in(a.support_source/directory).iterdir():
   if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
 for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
 def run(command,**kwargs):return subprocess.run(list(map(str,command)),check=True,**kwargs)
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def markers(s):return re.findall(r'"([^"]+)"',s.split('const char *const imports[] = {',1)[1].split('};',1)[0])
 old=markers((a.support_source/'windows/libc.cpp').read_text());new=markers((source/'windows/libc.cpp').read_text());assert new==old+['setlocale']
 (out/'old_markers.h').write_text('#pragma once\ninline constexpr const char* kOldMarkers[]={'+','.join(json.dumps(n)for n in old)+'};\n')
 guest=out/'setlocale.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-D_FORTIFY_SOURCE=0',source/'windows/setlocale_guest.c','-o',guest])
 result=dict(support_source=str(a.support_source),source_sha256={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},owned_overlay=list(OWN),fixture_sha256=sha(guest),runner_sha256=sha(__file__),old_markers_preserved=old,platforms={})
 for windows in(True,False):
  label='windows'if windows else'linux';build=out/label;build.mkdir();translated=build/'guest';path=wp if windows else str
  run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x5b000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'])
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';loader=build/'elfload.o'
  run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(work/'remill-src/include'),'-I'+path(out)]
  objects=[]
  for rel in('windows/libc.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(obj)]);objects.append(obj)
  exe=build/('setlocale.exe'if windows else'setlocale')
  run([cxx,*flags,'-Wall','-Wextra','-Werror','-I'+path(translated),f'-DSETLOCALE_LIBRARY="{path(guest)}"',path(source/'windows/setlocale_test.cpp'),*map(path,objects),path(loader),*map(path,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)])
  tests={}
  def execute(name,exe,extra=()):
   r=subprocess.run([str(exe),*extra],capture_output=True,text=True,timeout=90);(build/(name+'.stdout.log')).write_text(r.stdout);(build/(name+'.stderr.log')).write_text(r.stderr);print(label+' '+name+': '+r.stdout,end='',flush=True);print(r.stderr,end='',file=sys.stderr,flush=True);r.check_returncode();tests[name]=dict(stdout=r.stdout,stderr=r.stderr,binary_sha256=sha(exe))
  execute('focused',exe)
  locale_prior=work/('locale-windows'if windows else'locale-linux');lm=json.loads((locale_prior/'manifest.json').read_text());assert not lm['unsupported_traces']and not lm['unresolved_direct_targets']
  locale_regression=build/('locale-regression.exe'if windows else'locale-regression');run([cxx,*flags,'-I'+path(locale_prior),f'-DLOCALE_LIBRARY="{path(locale_prior/"locale.so")}"',path(source/'windows/locale_test.cpp'),*map(path,objects),path(loader),*map(path,lm['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(locale_regression)]);execute('locale',locale_regression)
  for test in('libc',):
   regression=build/(test+('-regression.exe'if windows else'-regression'));run([cxx,*flags,path(source/f'windows/{test}_test.cpp'),*map(path,objects),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(regression)]);execute(test,regression)
  prior=work/('libc-windows'if windows else'libc-linux');pm=json.loads((prior/'manifest.json').read_text());assert not pm['unsupported_traces']and not pm['unresolved_direct_targets'];oldobjects=pm['objects']
  regression=build/('startup-regression.exe'if windows else'startup-regression');run([cxx,*flags,'-I'+path(prior),f'-DLIBC_LIBRARY="{path(prior/"libc-guest.so")}"',path(source/'windows/libc_guest_test.cpp'),*map(path,objects),path(loader),*map(path,oldobjects),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(regression)]);execute('startup',regression)
  result['platforms'][label]=dict(tests=tests,traces=len(manifest['traces']),unsupported=manifest['unsupported_traces'],unresolved=manifest['unresolved_direct_targets'],toolchain=manifest['toolchain'],prior_inputs={str(f):sha(f)for f in[prior/'manifest.json',prior/'libc-guest.so',*map(Path,oldobjects),locale_prior/'manifest.json',locale_prior/'locale.so',*map(Path,lm['objects'])]},objects_sha256={str(f):sha(f)for f in[*objects,loader,*map(Path,manifest['objects'])]});(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()

"""Twelve real ES3.1 image-uniform getter types, retained uniform query and draw regressions."""
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
BASE='973ab9e8c362319f5d9cf63fb7064d1b34464f44'
PROOF_SHA='280ba042a0e100341e4c2b60fb57059f053bcb9c2d7abcf505463623d6c8a27c'
OWN=['gl_image_uniform_guest.c','gl_image_uniform_test.cpp','test_gl_image_uniform.py']
PRODUCTION=['gl_uniform_impl.inc']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,a):Path(p).write_text(json.dumps(a,indent=2)+'\n')
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def names(root):
 cpp=(root/'windows/gl_host.cpp').read_text();draw=re.search(r'#define GL_DRAW_API\(X\)(.*?)\n// Types',cpp,re.S);assert draw
 ds=re.findall(r'X\((gl\w+),',draw[1]);out=['glGetString','glGetStringi','glGetIntegerv','glGetFloatv','glGetBooleanv','glGetError'];block=cpp[cpp.index('const char *const names[]='):cpp.index('std::string Hex(')]
 for m in re.finditer(r'#include "([^"]+)"|GL_DRAW_API\(DRAW_NAME\)',block):
  out+=re.findall(r'GL_[A-Z0-9_]+\((gl\w+),',(root/'windows'/m[1]).read_text())if m[1]else ds
 assert len(out)==len(set(out));return out
def main():
 p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);commands=[];pins={}
 def pin(path,h=None):
  path=Path(path).resolve();d=sha(path);assert h is None or d==h,str(path);pins[str(path)]=d;return d
 def run(label,cmd,timeout=240):
  cmd=list(map(str,cmd));commands.append({'label':label,'argv':cmd});save(out/'commands.json',commands);print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  text=(out/(label+'.log')).read_text(errors='replace')
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+text[-6000:])
  return text
 try:
  proofpath=W/'image-uniform-preparation1/source-proof.json';pin(proofpath,PROOF_SHA);proof=json.loads(proofpath.read_text());assert proof['passed']and proof['base_commit']==BASE
  archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
  with tarfile.open(fileobj=io.BytesIO(archive))as tar:assert tar.pax_headers['comment']==BASE;tar.extractall(out/'source',filter='data')
  source=out/'source/recomp';old=(source/'windows/gl_uniform_impl.inc').read_bytes();oldnames=names(source);assert len(oldnames)==139
  for n in OWN+PRODUCTION:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  new=(source/'windows/gl_uniform_impl.inc').read_bytes();restored=new
  for chunk in proof['added_chunks_hex']:
   value=bytes.fromhex(chunk);assert restored.count(value)==1;restored=restored.replace(value,b'',1)
  assert restored==old and names(source)==oldnames
  fullnames=names(source);(out/'gl_draw_old_commands.h').write_text('#pragma once\nstatic const char*const kOldDrawCommands[]={'+','.join(map(json.dumps,fullnames))+'};\nstatic constexpr size_t kOldObjectIndex='+str(oldnames.index('glIsVertexArray'))+';\n')
  for n,h in proof['unchanged_source_sha256'].items():pin(HERE.parent/n,h)
  sources={p.relative_to(source).as_posix():sha(p)for p in source.rglob('*')if p.is_file()};save(out/'source-hashes.json',sources)
  tool=W/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4';ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');angle=W/'angle-native';dlls=angle/'bundle/bin';cxx='/mnt/c/mingw64/bin/g++.exe'
  for f in[ndk.resolve(),tool/'remill-lift',tool/'aarch64.bc',Path(cxx),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang++-18')).resolve()]:pin(f)
  for directory in[tool/'include',angle/'src/include',dlls]:
   for f in directory.rglob('*'):
    if f.is_file():pin(f)
  syntax_headers=W/'program-resource-qualification3/guest'
  syntax_flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool/'include'),'-I'+wp(syntax_headers),'-I'+wp(out),'-I'+wp(angle/'src/include'),'-DGL_DRAW_LIBRARY="C:/syntax-only.so"','-DGL_DRAW_DLL_DIRECTORY=L"'+wp(dlls)+'"']
  run('strict-host-syntax',[cxx,*syntax_flags,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(source/'windows/gl_image_uniform_test.cpp')])
  run('strict-NDK-syntax',[ndk,'-Wall','-Wextra','-Werror','-fsyntax-only',source/'windows/gl_image_uniform_guest.c'])
  library=out/'image.so';run('NDK-build' ,[ndk,'-Wall','-Wextra','-Werror','-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',source/'windows/gl_draw_guest.c',source/'windows/gl_image_uniform_guest.c','-o',library])
  run('translate',[sys.executable,source/'whole/compile.py',library,'--out',out/'guest','--lift',tool/'remill-lift','--semantics-dir',tool,'--cxx','clang++-18','--base','0x5b000000','--target','x86_64-w64-windows-gnu'])
  manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  loader=out/'elfload.o';run('elfload',['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool/'include'),'-I'+wp(out/'guest'),'-I'+wp(out),'-I'+wp(angle/'src/include'),'-DGL_DRAW_LIBRARY="'+wp(library)+'"','-DGL_DRAW_DLL_DIRECTORY=L"'+wp(dlls)+'"']
  common=[]
  for name in['windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp']:
   obj=out/(Path(name).stem+'.o');run('compile-'+obj.stem,[cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('gl_host.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)]);common.append(obj)
  results={}
  for stem in['gl_image_uniform_test','gl_draw_test']:
   obj=out/(stem+'.o');run('compile-'+stem,[cxx,*flags,'-Wall','-Wextra','-Werror','-c',wp(source/'windows'/(stem+'.cpp')),'-o',wp(obj)])
   exe=out/(stem+'.exe');run('link-'+stem,[cxx,'-static',wp(obj),*map(wp,common),wp(loader),*map(wp,manifest['objects']),'-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)])
   text=run('run-'+stem,[exe],120);results[stem]={'stdout':text,'binary_sha256':sha(exe)}
  assert re.search(r'GL-IMAGE-UNIFORM-SUCCESS types=12 checks=\d+ NDKcalls=\d+',results['gl_image_uniform_test']['stdout'])and'checks passed'in results['gl_draw_test']['stdout']
  assert results['gl_image_uniform_test']['stdout'].count('IMAGE-RECORD type=')==12
  # Relink the genuine retained old query caller, never relift its ISA/library.
  previous=W/'gl-uniform-qualification1';prior=json.loads((previous/'guest/manifest.json').read_text());assert not prior['unsupported_traces']and not prior['unresolved_direct_targets']
  oldlib=previous/'uniforms.so';assert sha(oldlib)==prior['sha256'];pin(oldlib);pin(previous/'guest/manifest.json');pin(previous/'acceptance.json')
  for obj in prior['objects']:pin(obj)
  shutil.copyfile(previous/'gl_uniform_old_commands.h',out/'gl_uniform_old_commands.h');pin(previous/'gl_uniform_old_commands.h')
  oldflags=[x for x in flags if not x.startswith('-DGL_DRAW_')and x!='-I'+wp(out/'guest')]+['-I'+wp(previous/'guest'),'-DGL_UNIFORM_IMAGE="'+wp(oldlib)+'"','-DGL_UNIFORM_DLL_DIRECTORY=L"'+wp(dlls)+'"']
  obj=out/'old-uniform.o';run('compile-old-uniform',[cxx,*oldflags,'-Wall','-Wextra','-Werror','-c',wp(source/'windows/gl_uniform_test.cpp'),'-o',wp(obj)])
  exe=out/'old-uniform.exe';run('link-old-uniform',[cxx,'-static',wp(obj),*map(wp,common),wp(loader),*map(wp,prior['objects']),'-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)])
  text=run('run-old-uniform',[exe],120);assert'GL-UNIFORM-PASS'in text;results['old_uniform_retained']={'stdout':text,'binary_sha256':sha(exe),'original_library_sha256':sha(oldlib),'original_manifest_sha256':sha(previous/'guest/manifest.json'),'no_relift':True}
  for name,h in sources.items():assert sha(source/name)==h
  for path,h in pins.items():assert sha(path)==h,path
  evidence={str(p):sha(p)for p in out.rglob('*')if p.is_file()}
  result={'passed':True,'scope':'ActualWindowsANGLE12coreES3.1image types, scalar+arraylayoutbindings1/2/3 metadata andoneGLint32getterlocation viaNDKdirect/pointer/procedure; rejectedimage1i/1iv/fv/iv2/matrix preservebindings andneverreadpayload;nativeerrors/counttails/guardpagecanaries;retainedold14uniform-querycaller andoldDrawagainstsamecompiledproviders','limitations':['Component-onlyshadercompile/link/metadata;noGPUdispatch,imagebindingAPIororiginalframeclaim','ES3.1 forbids allUniform*imageassignments;desktop setteracceptance isnotemulated','Only12imagegetter-widthclassification changed;139commandsandalloldsetterhelperbodiesunchanged'],'owned_sources':{'windows/'+n:sha(HERE/n)for n in OWN},'production_sources':{'windows/'+n:sha(HERE/n)for n in PRODUCTION},'source_hashes':sources,'old_command_names':oldnames,'new_command_names':fullnames,'old_namespace_prefix_exact':True,'source_proof':{'path':str(proofpath),'sha256':PROOF_SHA},'results':results,'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'tool_inputs':pins,'evidence':evidence}
  save(out/'acceptance.json',result);print('IMAGE-UNIFORM-PASS',sha(out/'acceptance.json'))
 except BaseException as exc:
  save(out/'failure.json',{'passed':False,'error':str(exc),'traceback':traceback.format_exc(),'commands':commands});raise
if __name__=='__main__':main()

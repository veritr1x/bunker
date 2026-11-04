"""Focused real ANGLE/NDK uniform-block ABI plus existing typed draw regression."""
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
BASE='4848f6d69cca97822b25aebabbdbd5e0e3935bd1'
PROOF_SHA='d6ad39239d5a29d53d44ff1a7bb82e6cac024dc051ba81ed463a29c64449ca5d'
OWN=['gl_uniform_block_guest.c','gl_uniform_block_test.cpp','test_gl_uniform_block.py']
PRODUCTION=['gl_host.cpp','gl_uniform_block_commands.inc','gl_uniform_block_impl.inc']
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
  proofpath=W/'uniform-block-preparation1/source-proof.json';pin(proofpath,PROOF_SHA);proof=json.loads(proofpath.read_text());assert proof['passed']and proof['base_commit']==BASE
  archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
  with tarfile.open(fileobj=io.BytesIO(archive))as tar:assert tar.pax_headers['comment']==BASE;tar.extractall(out/'source',filter='data')
  source=out/'source/recomp';old=(source/'windows/gl_host.cpp').read_bytes();oldnames=names(source);assert len(oldnames)==131
  for n in OWN+PRODUCTION:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  new=(source/'windows/gl_host.cpp').read_bytes();restored=new
  for chunk in proof['added_chunks_hex']:
   value=bytes.fromhex(chunk);assert restored.count(value)==1;restored=restored.replace(value,b'',1)
  assert restored==old and names(source)==oldnames+['glGetActiveUniformBlockiv','glGetActiveUniformBlockName','glUniformBlockBinding','glGetActiveUniformsiv','glGetUniformIndices']
  fullnames=names(source);(out/'gl_draw_old_commands.h').write_text('#pragma once\nstatic const char*const kOldDrawCommands[]={'+','.join(map(json.dumps,fullnames))+'};\nstatic constexpr size_t kOldObjectIndex='+str(oldnames.index('glIsVertexArray'))+';\n')
  for n,h in proof['unchanged_source_sha256'].items():pin(HERE.parent/n,h)
  sources={p.relative_to(source).as_posix():sha(p)for p in source.rglob('*')if p.is_file()};save(out/'source-hashes.json',sources)
  tool=W/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4';ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');angle=W/'angle-native';dlls=angle/'bundle/bin';cxx='/mnt/c/mingw64/bin/g++.exe'
  for f in[ndk.resolve(),tool/'remill-lift',tool/'aarch64.bc',Path(cxx),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang++-18')).resolve()]:pin(f)
  for directory in[tool/'include',angle/'src/include',dlls]:
   for f in directory.rglob('*'):
    if f.is_file():pin(f)
  library=out/'uniform.so';run('NDK-build',[ndk,'-Wall','-Wextra','-Werror','-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',source/'windows/gl_draw_guest.c',source/'windows/gl_uniform_block_guest.c','-o',library])
  run('translate',[sys.executable,source/'whole/compile.py',library,'--out',out/'guest','--lift',tool/'remill-lift','--semantics-dir',tool,'--cxx','clang++-18','--base','0x5b000000','--target','x86_64-w64-windows-gnu'])
  manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  loader=out/'elfload.o';run('elfload',['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool/'include'),'-I'+wp(out/'guest'),'-I'+wp(out),'-I'+wp(angle/'src/include'),'-DGL_DRAW_LIBRARY="'+wp(library)+'"','-DGL_DRAW_DLL_DIRECTORY=L"'+wp(dlls)+'"']
  common=[]
  for name in['windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp']:
   obj=out/(Path(name).stem+'.o');run('compile-'+obj.stem,[cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('gl_host.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)]);common.append(obj)
  results={}
  for stem in['gl_uniform_block_test','gl_draw_test']:
   obj=out/(stem+'.o');run('compile-'+stem,[cxx,*flags,'-Wall','-Wextra','-Werror','-c',wp(source/'windows'/(stem+'.cpp')),'-o',wp(obj)])
   exe=out/(stem+'.exe');run('link-'+stem,[cxx,'-static',wp(obj),*map(wp,common),wp(loader),*map(wp,manifest['objects']),'-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)])
   text=run('run-'+stem,[exe],120);results[stem]={'stdout':text,'binary_sha256':sha(exe)}
  assert re.search(r'GL-UNIFORM-BLOCK-SUCCESS checks=\d+ NDKcalls=\d+',results['gl_uniform_block_test']['stdout'])and'checks passed'in results['gl_draw_test']['stdout']
  for name,h in sources.items():assert sha(source/name)==h
  for path,h in pins.items():assert sha(path)==h,path
  evidence={str(p):sha(p)for p in out.rglob('*')if p.is_file()}
  result={'passed':True,'scope':'ActualWindowsANGLE5uniform-blockGLES3APIs viaNDKdirect/volatilepointer/procedure; independentstd14096/16blocks and0/64/0offsets plusnativedriver comparisons; dynamicoutputs/namecapacities/snapshots/aliases/canaries/errors; existingoldtypedrenderfixture againstsamecompiledproviders','limitations':['Component-only realANGLEpbuffer tests; no originalgame/frame/GCclaim','No newGLcapabilityorhostnativepointer passthrough; only5appendedcommands','PinnedANGLE negative BlockName capacity leaves length/name untouched without an error; fixture compares actualdriver behavior, not portable spec semantics'],'owned_sources':{'windows/'+n:sha(HERE/n)for n in OWN},'production_sources':{'windows/'+n:sha(HERE/n)for n in PRODUCTION},'source_hashes':sources,'old_command_names':oldnames,'new_command_names':fullnames,'old_namespace_prefix_exact':True,'source_proof':{'path':str(proofpath),'sha256':PROOF_SHA},'results':results,'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'tool_inputs':pins,'evidence':evidence}
  save(out/'acceptance.json',result);print('UNIFORM-BLOCK-PASS',sha(out/'acceptance.json'))
 except BaseException as exc:
  save(out/'failure.json',{'passed':False,'error':str(exc),'traceback':traceback.format_exc(),'commands':commands});raise
if __name__=='__main__':main()

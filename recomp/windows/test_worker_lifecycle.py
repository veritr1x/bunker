"""Freeze and test optional actual pthread worker lifetimes with NDK callers."""
import argparse,hashlib,io,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
OWN=['pthread_host.h','pthread_host.cpp','worker_lifecycle_fixture.h','worker_lifecycle_guest.c','worker_lifecycle_test.cpp','test_worker_lifecycle.py','worker_lifecycle.md']

def sha(path):
 with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['ndk','lift','out']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--semantics-dir',type=Path,required=True);p.add_argument('--host-commit',required=True)
 p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src');p.add_argument('--mingw',type=Path,default=Path('/mnt/c/mingw64/bin'));p.add_argument('--cxx',default='clang++-18')
 a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True)
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
 commit=subprocess.check_output(['git','rev-parse',a.host_commit],cwd=HERE.parent.parent,text=True).strip()
 archive=subprocess.check_output(['git','archive',commit,'recomp/windows','recomp/whole','recomp/fastaes'],cwd=HERE.parent.parent)
 (out/'host-source.tar').write_bytes(archive);(out/'sources').mkdir()
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'sources',filter='data')
 source=out/'sources/recomp';windows=source/'windows';whole=source/'whole'
 for name in OWN:shutil.copyfile(HERE/name,windows/name)
 shutil.copytree(a.remill/'include',out/'remill/include')
 source_hashes={str(x.relative_to(out/'sources')):sha(x)for x in(out/'sources').rglob('*')if x.is_file()}
 header_hashes={str(x.relative_to(out/'remill')):sha(x)for x in(out/'remill').rglob('*')if x.is_file()}
 own_hashes={name:sha(HERE/name)for name in OWN}
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 def guest(cfile,directory):
  directory.mkdir();library=directory/'fixture.so'
  subprocess.run([str(cc),'-shared','-fPIC','-nostdlib','-O1','-fno-stack-protector','-D_FORTIFY_SOURCE=0',str(cfile),'-o',str(library)],check=True)
  target=directory/'guest'
  subprocess.run([sys.executable,str(whole/'compile.py'),str(library),'--out',str(target),'--lift',str(a.lift),'--semantics-dir',str(a.semantics_dir),'--base','0x70000000','--target','x86_64-w64-windows-gnu','--cxx',a.cxx],check=True,env=env)
  m=json.loads((target/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  return library,m
 fixture,manifest=guest(windows/'worker_lifecycle_guest.c',out/'focused')
 shutil.copyfile(out/'focused/guest/traces.h',out/'focused/worker_lifecycle_traces.h')
 with fixture.open('rb')as stream:
  elf=ELFFile(stream);imports=[s.name for s in elf.get_section_by_name('.dynsym').iter_symbols()if s.name and s['st_shndx']=='SHN_UNDEF']
  ranges=[(0x70000000+s['sh_addr'],0x70000000+s['sh_addr']+s['sh_size'])for s in elf.iter_sections()if s['sh_flags']&4 and s['sh_size']]
 (out/'focused/worker_lifecycle_imports.h').write_text('static const char *kWorkerLifecycleImports[]={'+','.join(json.dumps(x)for x in imports)+'};\nstruct WorkerCodeRange{addr_t low,high;};\nstatic const WorkerCodeRange kWorkerCodeRanges[]={'+','.join('{'+hex(lo)+','+hex(hi)+'}'for lo,hi in ranges)+'};\n')
 old_fixture,old_manifest=guest(windows/'pthread_guest_fixture.c',out/'regression')
 shutil.copyfile(out/'regression/guest/traces.h',out/'regression/pthread_traces.h')
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 loader=out/'elfload.o';subprocess.run([str(a.mingw/'gcc.exe'),'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],check=True)
 def build(name,test,library,m,directory,providers,define):
  binary=directory/(name+'.exe')
  command=[str(a.mingw/'g++.exe'),'-std=c++17','-O2','-static','-DADDRESS_SIZE_BITS=64',f'-D{define}="{wp(library)}"',f'-I{wp(out/"remill/include")}',f'-I{wp(directory)}',wp(windows/test)]
  command += [wp(windows/x)for x in providers]+[wp(whole/'runtime.cpp'),wp(loader),*[wp(x)for x in m['objects']],'-latomic','-lbcrypt','-o',wp(binary)]
  if name=='worker-lifecycle':command.insert(len(command)-4,wp(whole/'format.cpp'))
  subprocess.run(command,check=True)
  log=directory/'actual.log'
  with log.open('wb')as stream:result=subprocess.run([str(binary)],stdout=stream,stderr=subprocess.STDOUT)
  if result.returncode:raise RuntimeError(f'{name} failed exit{result.returncode}; preserved log {log}')
  return binary,log
 binary,log=build('worker-lifecycle','worker_lifecycle_test.cpp',fixture,manifest,out/'focused',['pthread_host.cpp','signal_host.cpp','nonlocal_jmp.cpp','libc.cpp'],'WORKER_LIFECYCLE_IMAGE')
 old_binary,old_log=build('pthread-regression','pthread_test.cpp',old_fixture,old_manifest,out/'regression',['pthread_host.cpp'],'PTHREAD_GUEST_IMAGE')
 assert '6 actual NDK workers'in log.read_text()and 'checks passed'in old_log.read_text()
 assert all(sha(out/'sources'/name)==value for name,value in source_hashes.items())
 assert all(sha(out/'remill'/name)==value for name,value in header_hashes.items())
 assert all(sha(HERE/name)==value for name,value in own_hashes.items())
 proof=dict(passed=True,host_commit=commit,host_archive_sha256=sha(out/'host-source.tar'),source_sha256=source_hashes,remill_header_sha256=header_hashes,held_source_sha256=own_hashes,ndk_compiler_sha256=sha(cc.resolve()),toolchain=manifest['toolchain'],focused_traces=len(manifest['traces']),regression_traces=len(old_manifest['traces']),fixture_sha256=sha(fixture),regression_fixture_sha256=sha(old_fixture),executable_sha256=sha(binary),regression_executable_sha256=sha(old_binary),log_sha256=sha(log),regression_log_sha256=sha(old_log),focused_result=log.read_text().strip(),regression_result=old_log.read_text().strip(),scope='optional worker lifecycle and TLS role validation; no production polls/signals/collector/Java attachment')
 (out/'acceptance.json').write_text(json.dumps(proof,indent=2)+'\n');print(proof['focused_result']);print(proof['regression_result'])
if __name__=='__main__':main()

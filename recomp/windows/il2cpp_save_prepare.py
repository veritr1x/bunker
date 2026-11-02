"""Freeze a NEW actual save-helper variant of the corrected stack4 gate."""
import argparse,copy,hashlib,json,shutil,struct,subprocess,sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
from il2cpp_stack_prepare import hashes,absolute
HERE=Path(__file__).resolve().parent
BASE_EXE='9f17b8cdbc5af6527084c473f797f2d9b639c74face4b2380cb804debed75896'
BASE_INPUT='42a9a42d309571a969a88364b6a1846836554e199a0997dd734684030aada0d1'
OWN=['il2cpp_save.cpp','il2cpp_save_audit.h','il2cpp_save_guest.S','il2cpp_save_guest.c','il2cpp_save_prepare.py','il2cpp_save_build.ps1','test_il2cpp_save.py','il2cpp_save.md']
def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--ndk',type=Path,required=True);p.add_argument('--lift',type=Path,required=True);p.add_argument('--semantics-dir',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise RuntimeError('A fresh directory is required; preserve prior candidates')
 base=a.base_build.resolve();old=json.loads((base/'il2cpp_stack_inputs.json').read_text());audit=json.loads((base/'il2cpp_stack_final_audit.json').read_text())
 assert sha(base/'il2cpp_stack_inputs.json')==BASE_INPUT and sha(base/'il2cpp-stack.exe')==BASE_EXE
 assert audit['status']=='actual original parameterless stack helper passed'and audit['executable_sha256']==BASE_EXE and audit['inputs_sha256']==BASE_INPUT
 assert old['trace_count']==393781 and len(old['objects'])==3079 and old['remaining_unsupported']==189
 expected={str(base/'sources'/k):v for k,v in old['source_sha256'].items()}
 expected.update({str(base/k):v for field in ['frozen_support_sha256','headers_sha256']for k,v in old[field].items()})
 expected.update(old['prior_artifacts_sha256']);expected.update({str(Path(old['baseline'])/x['path']):x['sha256']for x in old['original_objects']+old['objects']})
 actual=hashes([Path(x)for x in expected]);assert all(actual[str(absolute(k))]==v for k,v in expected.items()),'accepted frozen input changed'
 a.out.mkdir(parents=True);out=a.out.resolve()
 for directory in ['sources','remill-include','zlib']:shutil.copytree(base/directory,out/directory)
 for name in ['il2cpp_data.h','il2cpp_traces.h','committed-host.tar']:shutil.copy2(base/name,out/name)
 for name in OWN:shutil.copy2(HERE/name,out/'sources/recomp/windows'/name)
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';library=out/'save-probe.so'
 subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',str(out/'sources/recomp/windows/il2cpp_save_guest.S'),str(out/'sources/recomp/windows/il2cpp_save_guest.c'),'-o',str(library)],check=True)
 subprocess.run([sys.executable,str(out/'sources/recomp/whole/compile.py'),str(library),'--out',str(out/'guest'),'--base','0x62000000','--target','x86_64-w64-windows-gnu','--cxx','clang++-18','--lift',str(a.lift),'--semantics-dir',str(a.semantics_dir)],check=True)
 fixture=json.loads((out/'guest/manifest.json').read_text());assert not fixture['unsupported_traces']and not fixture['unresolved_direct_targets']and fixture['imports']==['observe_save']and not fixture['initializers']and not fixture['finalizers']
 assert fixture['base']==0x62000000 and all(x<0x80000000 for x in fixture['traces'])
 for obj in fixture['objects']:
  with Path(obj).open('rb')as f:assert struct.unpack('<H',f.read(2))[0]==0x8664
 fixture_header=(out/'guest/traces.h').read_text().replace('kTraces','kProbeTraces').replace('kInitializers','kProbeInitializers');(out/'save_probe_traces.h').write_text(fixture_header)
 # Compare recursive LLVM State layout, not merely total sizeof(State).
 subprocess.run(['/mnt/c/GitRepos/bunker/recomp/work/unity-native2-lineage/state-layout','/home/user/bunker-recomp/recomp/work/whole-il2cpp/shard-00000.ll',str(out/'guest/shard-00000.ll'),str(out/'probe-state-layout')],check=True)
 assert sha(out/'probe-state-layout.new.txt')=='ba607ad5aab3a61164b08c8fa4a07c9273c5b9a788d5789ad580e5396b898d8d'
 with Path(old['original_ELF']).open('rb')as f:
  elf=ELFFile(f)
  text=next(s for s in elf.iter_sections()if s['sh_flags']&4 and s['sh_addr']<=0x25b0544 and 0x25b05a8<=s['sh_addr']+s['sh_size']);code=text.data()[0x25b0544-text['sh_addr']:0x25b05a8-text['sh_addr']]
 assert hashlib.sha256(code).hexdigest()=='10c39e495f358675676c282732b0670c2ca886e3efb2dda30e4bab35b43c288a'
 header='#pragma once\n'+f'inline constexpr addr_t kSaveProbeBase=0x62000000,kSaveProbeSpan={fixture["image_span"]},kSaveCaller={fixture["exports"]["collector_save_probe"]},kSaveCallback={fixture["exports"]["collector_save_callback"]};\n'+f'inline constexpr uint32_t kSaveReturnInstruction={int.from_bytes(code[60:64],"little")};\n'+f'inline constexpr char kSaveProbeSha256[]="{sha(library)}";\n'
 (out/'save_probe_data.h').write_text(header)
 m=copy.deepcopy(old);m['gate']='actual825b0544 save-only +labelled strict NDK caller/callback; no GC/init/metadata/suspension/real collector callback/longjmp'
 m['base_gate']={'directory':str(base),'executable_sha256':BASE_EXE,'inputs_sha256':BASE_INPUT,'accepted_commit':'53049d7'}
 m['source_sha256']={str(x.relative_to(out/'sources')):sha(x)for x in(out/'sources').rglob('*')if x.is_file()}
 m['headers_sha256']={name:sha(out/name)for name in ['il2cpp_data.h','il2cpp_traces.h','save_probe_traces.h','save_probe_data.h']}
 m['fixture']={'library':str(library),'sha256':sha(library),'manifest_sha256':sha(out/'guest/manifest.json'),'traces':len(fixture['traces']),'objects':[{'path':x,'sha256':sha(x)}for x in fixture['objects']],'toolchain':fixture['toolchain'],'state_layout_sha256':sha(out/'probe-state-layout.new.txt')}
 m['prior_artifacts_sha256'].update({str(x):sha(x)for x in base.iterdir()if x.is_file()})
 m['preparation_source_sha256']={name:sha(HERE/name)for name in OWN}
 m['new_harness_sha256']=sha(HERE/'il2cpp_save.cpp')
 (out/'il2cpp_save_inputs.json').write_text(json.dumps(m,indent=2)+'\n')
 print('Prepared NEW actual save-helper variant:',len(old['objects']),'old objects +',len(fixture['objects']),'strict probe objects;',len(fixture['traces']),'probe traces')
if __name__=='__main__':main()

"""Recover locally guarded register snapshots after ambiguous pre-guard loops."""
import argparse,hashlib,importlib.util,inspect,io,json,subprocess,sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
from jump_tables import recover
from test_fastaes import build_reference
HERE=Path(__file__).resolve().parent
POSITIVES={'x64':(), 'w32':('SNAP_W_INDEX',), 'sxtw':('SNAP_W_INDEX','SNAP_SIGNED_W_INDEX'),
 'separate_destination':('SNAP_SEPARATE_DEST',), 'unsigned_lo':('SNAP_GUARD_LO',),
 'unsigned_ls':('SNAP_GUARD_LS',), 'positive_offsets':('SNAP_RODATA_TABLE',)}
NEGATIVES=('SOURCE_CLOBBER','W_ALIAS_CLOBBER','CONDITIONAL_CLOBBER','CALLER_CLOBBER',
 'FLAG_CLOBBER','OTHER_REGISTER','GUARD_WIDTH_MISMATCH','NARROW_LOAD_MISMATCH',
 'GUARD_BYPASS','WRONG_CONDITION','SIGNED_CONDITION','NO_GUARD','UNGUARDED_BACKEDGE',
 'STRIDE_MISMATCH','TABLE_OOB','OUTSIDE_TARGET')

def digest(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def compile_fixture(library,out,lift,semantics,cxx,windows,recovery):
 spec=importlib.util.spec_from_file_location('snapshot_compiler',HERE/'compile.py');compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler);original=compiler.inspect
 def image(path,base):
  options={'recover_jumps':False}if'recover_jumps'in inspect.signature(original).parameters else{}
  raw,start,entries,manifest=original(path,base,**options)
  if recovery:
   with path.open('rb')as stream:report=recover(ELFFile(stream))
   entries=sorted(set(entries)|{base+address for address in report['entries']});manifest['jump_tables']=report
  return raw,start,entries,manifest
 compiler.inspect=image;previous=sys.argv
 try:
  sys.argv=[str(HERE/'compile.py'),str(library),'--out',str(out),'--lift',str(lift),'--semantics-dir',str(semantics),'--base','0x50000000','--cxx',cxx,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu'];compiler.main()
 finally:sys.argv=previous

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','reference-root','out','remill'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();root=a.out.resolve();assert not root.exists(),'Preserve old variants; use a fresh output directory';root.mkdir(parents=True)
 def run(cmd,**kwargs):return subprocess.run(list(map(str,cmd)),check=True,**kwargs)
 def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';source=HERE/'snapshot_switch_fixture.S'
 results={'source_sha256':{name:digest(HERE/name)for name in('jump_tables.py','snapshot_switch_fixture.S','snapshot_switch_driver.h','snapshot_switch_ref.c','snapshot_switch_test.cpp','test_snapshot_jump_tables.py','compile.py','runtime.cpp','test_fastaes.py')},'ndk_compiler_sha256':digest(ndk.resolve()),'negatives':{},'positives':{}}
 for name,defines in [*POSITIVES.items(),*((name,('SNAP_'+name,))for name in NEGATIVES)]:
  library=root/(name+'.so');run([ndk,'-shared','-nostdlib','-Wl,--no-relax',*[f'-D{d}'for d in defines],source,'-o',library])
  with library.open('rb')as stream:report=recover(ELFFile(stream))
  (root/(name+'.report.json')).write_text(json.dumps(report,indent=2)+'\n')
  if name in NEGATIVES:
   assert not report['entries']and not report['tables']and report['unresolved'],(name,report)
   results['negatives'][name]={'rejected':True,'fixture_sha256':digest(library),'report':report};print(name,'rejected',flush=True)
  else:
   assert len(report['tables'])==1 and len(report['entries'])==16 and not report['unresolved'],(name,report)
   table=report['tables'][0];assert table['count']==16 and table['entry_size']==4 and table['signed']and table['index_snapshot']['width']==(32 if'SNAP_W_INDEX'in defines else 64)
   assert all((target<table['table'])==(name!='positive_offsets')for target in table['targets']),table
   results['positives'][name]={'fixture_sha256':digest(library),'report':report,'platforms':{}}
 (root/'static-results.json').write_text(json.dumps(results,indent=2)+'\n')
 for name,defines in POSITIVES.items():
  library=root/(name+'.so');variant=root/name;variant.mkdir()
  reference=variant/'reference';build_reference('clang-18',a.reference_root,[HERE/'snapshot_switch_ref.c',source],reference,[HERE],defines)
  expected=run([a.reference_root/'usr/bin/qemu-aarch64-static',reference],capture_output=True).stdout;(variant/'arm64-results.bin').write_bytes(expected)
  assert len(expected)==32768
  entry=results['positives'][name];entry['reference_sha256']=digest(reference);entry['output_sha256']=hashlib.sha256(expected).hexdigest();entry['cases']=len(expected)//8
  for windows in(False,True):
   platform='windows'if windows else'linux';build=variant/platform;build.mkdir();path=hp if windows else lambda p:str(p);cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18'
   loader=build/'elfload.o';run([cc,'-O2','-c',path(HERE.parent/'fastaes/elfload.c'),'-o',path(loader)])
   runs={}
   for recovered in(False,True):
    translated=build/('recovered'if recovered else'baseline');compile_fixture(library,translated,a.lift,a.semantics_dir,'clang++-18',windows,recovered)
    manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
    assert manifest['toolchain']['lifter']==digest(a.lift)and manifest['toolchain']['semantics']==digest(a.semantics_dir/'aarch64.bc')
    binary=build/(('recovered-test'if recovered else'baseline-test')+('.exe'if windows else''))
    run([cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-DSWITCH_LIBRARY="{path(library)}"','-I'+path(a.remill/'include'),'-I'+path(HERE),'-I'+path(HERE.parent/'fastaes'),'-I'+path(translated),path(HERE/'snapshot_switch_test.cpp'),path(HERE/'runtime.cpp'),path(loader),*map(path,manifest['objects']),'-latomic',*(['-static']if windows else[]),'-o',path(binary)])
    output=subprocess.run([str(binary)],capture_output=True,timeout=60)
    (build/(('recovered'if recovered else'baseline')+'.stderr.log')).write_bytes(output.stderr)
    (build/(('recovered'if recovered else'baseline')+'.results.bin')).write_bytes(output.stdout)
    if recovered:assert output.returncode==0 and output.stdout==expected,(name,platform,output.returncode,output.stderr)
    else:assert output.returncode!=0 and b'unresolved indirect target'in output.stderr,(name,platform,output.returncode,output.stderr)
    runs['recovered'if recovered else'baseline']={'returncode':output.returncode,'binary_sha256':digest(binary),'output_sha256':hashlib.sha256(output.stdout).hexdigest(),'stderr':output.stderr.decode(errors='replace'),'traces':len(manifest['traces']),'unsupported':[],'unresolved_direct':[],'manifest_sha256':digest(translated/'manifest.json'),'objects_sha256':{Path(obj).name:digest(obj)for obj in manifest['objects']}}
   entry['platforms'][platform]=runs;print(name,platform,len(expected)//8,'ARM64 records matched; baseline unresolved reproduced',flush=True)
   (root/'progress.json').write_text(json.dumps(results,indent=2)+'\n')
 results['passed']=True;(root/'acceptance.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()

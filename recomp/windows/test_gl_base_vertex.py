"""Real ANGLE indexed-draw variants through the actual State/Runtime bridge ABI.

This focused component creates no original game process or presented-frame claim.
Existing GL regressions are executed independently and bound separately.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('gl_base_vertex_test.cpp','test_gl_base_vertex.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def names(cpp,root):
 draw=re.search(r'#define GL_DRAW_API\(X\)(.*?)\n// Types',cpp,re.S);assert draw;drawnames=re.findall(r'X\((gl\w+),',draw[1]);block=cpp[cpp.index('const char *const names[]='):cpp.index('std::string Hex(')];result=[]
 for m in re.finditer(r'#include "([^"]+)"|GL_DRAW_API\(DRAW_NAME\)|"(gl\w+)"',block):
  result+=re.findall(r'GL_[A-Z0-9_]+\((gl\w+),',(root/'windows'/m[1]).read_text())if m[1]else[m[2]]if m[2]else drawnames
 assert len(result)==len(set(result));return result
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--production-packet',type=Path,default=W/'gl-base-vertex-preparation1/source-ready.json');a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=180):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 try:
  assert sha(a.production_packet)=='43537233f7fe468be9009027b8dda1b9e05933463f9be5d71aa99c520266471b';packet=json.loads(a.production_packet.read_text());production=packet['production_sources'];assert production=={'windows/gl_host.cpp':'5417cb62ecfad9be2ba38343de9ed96acbe802f66e6f75aa427006d6e1161d09'};pin(a.production_packet)
  source=out/'source';required={'windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp'}
  for folder in('windows','whole'):
   target=source/folder;target.mkdir(parents=True)
   for p in(HERE.parent/folder).iterdir():
    if p.is_file()and(p.suffix in('.h','.inc')or folder+'/'+p.name in required or p.name in OWN):shutil.copyfile(p,target/p.name)
  for name,h in production.items():assert sha(source/name)==h==sha(HERE.parent/name);pin(HERE.parent/name)
  for name in OWN:pin(HERE/name)
  shutil.copyfile(__file__,out/'executed-controller.py');oldrow=packet['source_records']['windows/gl_host.cpp']['baseline'];assert sha(oldrow['path'])==oldrow['sha256']=='859a02e64f84c69b347a5cb4b12c5b8e71c4f916ffc0960119ce4b14e11d348c';pin(oldrow['path']);old=names(Path(oldrow['path']).read_text(),source);new=names((source/'windows/gl_host.cpp').read_text(),source);assert new==old+packet['new_command_order'];assert len(packet['new_command_order'])==10
  (out/'gl_base_vertex_old_commands.h').write_text('#pragma once\nstatic const char*const kOldBaseVertexCommands[]={'+','.join(map(json.dumps,old))+'};\n')
  native_dll=Path(packet['native_GLES_DLL']['path']);assert sha(native_dll)==packet['native_GLES_DLL']['sha256'];dlls=native_dll.parent;angle=native_dll.parents[2];remill=W/'remill-src';cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cxx)
  for root in(dlls,angle/'src/include',remill/'include'):
   for p in root.rglob('*'):
    if p.is_file():pin(p)
  source_pins={str(p.relative_to(source)):sha(p)for p in source.rglob('*')if p.is_file()};(out/'source-binding.json').write_text(json.dumps(dict(production_sources=production,production_source_packet=desc(a.production_packet),old_commands=old,new_commands=new,source_sha256=source_pins),indent=2)+'\n')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(remill/'include'),'-I'+wp(out),'-I'+wp(angle/'src/include'),'-DGL_BASE_VERTEX_DLL_DIRECTORY=L"'+wp(dlls)+'"','-DGL_BASE_VERTEX_RESULT_PATH="'+wp(out/'result.txt')+'"','-DGL_BASE_VERTEX_DIAGNOSTIC_PATH=L"'+wp(out/'not-an-original-frame.png')+'"'];objects=[]
  for name in('windows/gl_base_vertex_test.cpp','windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp'):
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('gl_base_vertex_test.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'base-vertex.exe';run([cxx,*map(wp,objects),'-static','-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)],'link');run([exe],'actual-ANGLE',180)
  text=(out/'result.txt').read_text();m=re.search(r'GL-BASE-VERTEX-PASS checks=(\d+) APIs=10 comparisons=(\d+) nonuniform=(\d+) marker_draws=(\d+) guard_rejections=(\d+) State=1200 Memory64=1 offset=24',text);assert m and int(m[3])>0 and int(m[5])==20;assert not(out/'not-an-original-frame.png').exists()
  for p,h in source_pins.items():assert sha(source/p)==h,p
  for p,h in held.items():assert sha(p)==h,p
  r=dict(passed=True,prepared_only=True,selected=False,reviewed_production_sources=production,production_sources=production,production_source_packet=desc(a.production_packet),owned_sources={n:sha(source/'windows'/n)for n in OWN},focused=dict(checks=int(m[1]),APIs=10,comparisons=int(m[2]),nonuniform_draws=int(m[3]),marker_draws=int(m[4]),GPU_only_guard_rejections=int(m[5]),State_size=1200,Memory64_preserved=True,index_byte_offset=24,exact_native_pixel_and_error_controls=True,all_aliases_actual_corresponding_ANGLE_exports=True,negative_and_positive_base_vertices=True,instance_counts_zero_one_two=True,range_start_end_unshifted=True,CPU_index_emulation=False,result=desc(out/'result.txt'),stdout=desc(out/'actual-ANGLE.log'),executable=desc(exe)),old_marker_prefix_exact=True,old_commands=old,new_commands=new,source_snapshot=source_pins,held_inputs=held,commands=commands,existing_regressions_pending_separate_receipt=True,original_game_execution=False,original_or_presented_frame_claim=False,limits='Actual ANGLE GPU VBO/EBO indexed draws through Runtime typed-marker dispatch; direct native same-API controls. No translated NDK caller claimed in this focused fixture. No original game/window frame or CPU draw/index emulation. Existing regressions are separately executed and bound by an integration receipt.');(out/'acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print('GL-BASE-VERTEX-FOCUSED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()

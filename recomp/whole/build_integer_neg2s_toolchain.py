"""Bounded isolated NEG.2S build from the qualified 14f6/6dd recipe.

Rebuild Arch.cpp, Decode.cpp and the Instructions semantics only (two workers).
Borrow Lift/GuestCallLowering/Extract and every other library unchanged. Never
replace an existing frozen toolchain or select/rebuild a game cohort.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,hashlib,importlib.util,json,re,shutil,subprocess,traceback
W=Path('/mnt/c/GitRepos/bunker/recomp/work');L=Path('/home/user/bunker-recomp/recomp/work')
OLD=L/'fp-numeric-minmax-isolated1';N=L/'integer-neg2s-isolated1';O=W/'integer-neg2s-preparation1'
BASE=W/'fp-numeric-minmax-preparation1/toolchains/14f6409b2d88fbde-6dd3ed0e502e37b9'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p);return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def read(p):return json.loads(Path(p).read_bytes())
def save(p,v):assert not Path(p).exists();Path(p).write_text(json.dumps(v,indent=2)+'\n')
def functions(s):return {m[1]:m[0]for m in re.finditer(r'^define[^\n]*@([^ (]+)\([^\n]*\).*?^}',s,re.M|re.S)}
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 if not a.execute:print('Dry run: isolated3unit build only; use --execute');return
 assert sha(BASE/'remill-lift')=='14f6409b2d88fbde54b3641ff09db0b3bd03907e3efa33de405755e85542e11b'and sha(BASE/'aarch64.bc')=='6dd3ed0e502e37b97e8042de4ea6f3f95ed56066068d753d64b2f873ad83f56e'
 source_producer=Path(__file__).with_name('integer_neg2s_source.py');spec=importlib.util.spec_from_file_location('neg2s_source',source_producer);src=importlib.util.module_from_spec(spec);spec.loader.exec_module(src)
 if not(N/'source').exists():shutil.copytree(OLD/'source',N/'source');src.apply(N/'source',O/'source1')
 proof=read(O/'source1/source-proof.json')
 for name,row in proof['source_files'].items():assert sha(N/'source'/name)==row['new_sha256']and sha(OLD/'source'/name)==row['old_sha256']
 old_files={p.relative_to(OLD/'source').as_posix():sha(p)for p in(OLD/'source').rglob('*')if p.is_file()};new_files={p.relative_to(N/'source').as_posix():sha(p)for p in(N/'source').rglob('*')if p.is_file()}
 assert set(old_files)==set(new_files)and{n for n in old_files if old_files[n]!=new_files[n]}==set(src.BASELINES)
 B=O/'build1';B.mkdir();(N/'build').mkdir();(N/'lib').mkdir();(N/'bin').mkdir();(N/'semantics').mkdir();commands=[]
 recipe_path=W/'fp-numeric-minmax-preparation1/build-argv.json';assert sha(recipe_path)=='aaaf88e7bbef77f3add53423f9c82b2d2948f33304fe02696678ce44e7b94a9d';recipe=read(recipe_path)
 baseline_build=read(W/'fp-numeric-minmax-preparation1/build1/acceptance.json');assert baseline_build['passed']is True
 def replace(cmd):return [x.replace(str(OLD),str(N))for x in cmd]
 for name in ['Lift.cpp.o','GuestCallLowering.o']:shutil.copyfile(OLD/'build'/name,N/'build'/name);assert sha(OLD/'build'/name)==sha(N/'build'/name)
 archive=N/'lib/libremill_arch_aarch64.a';shutil.copyfile(BASE/'decoder-libs/libremill_arch_aarch64.a',archive)
 for name in ['aarch64_BasicBlock.cpp.bc','aarch64_Intrinsics.cpp.bc','aarch64_HyperCall.cpp.bc']:shutil.copyfile(OLD/'semantics'/name,N/'semantics'/name);assert sha(OLD/'semantics'/name)==sha(N/'semantics'/name)
 def run(stage,cmd):
  cmd=list(map(str,cmd));print('NEG2S-BUILD',stage,flush=True)
  with(B/(stage+'.log')).open('x')as log:subprocess.run(cmd,cwd=N/'build',stdout=log,stderr=subprocess.STDOUT,check=True)
  return dict(stage=stage,argv=cmd,exit_code=0)
 stages=['compile_Arch.cpp','compile_Decode.cpp','compile_semantics']
 with ThreadPoolExecutor(max_workers=2)as ex:commands.extend(ex.map(lambda k:run(k,replace(recipe[k])),stages))
 commands.append(run('replace_decoder_archive',['llvm-ar-18','rcs',archive,N/'build/Arch.cpp.o',N/'build/Decode.cpp.o']))
 commands.append(run('link',replace(recipe['link'])))
 for stage in ['link_semantics','verify_semantics']:
  original=next(c['argv']for c in baseline_build['commands']if c['stage']==stage);commands.append(run(stage,replace(original)))
 old_ir=subprocess.check_output(['llvm-dis-18',BASE/'aarch64.bc','-o','-'],text=True);new_ir=subprocess.check_output(['llvm-dis-18',N/'semantics/aarch64.bc','-o','-'],text=True)
 oldf,newf=functions(old_ir),functions(new_ir);assert set(oldf)<=set(newf)
 def normalized(body,text):
  attrs=dict(re.findall(r'^attributes #(\d+) = (.*)$',text,re.M))
  body=re.sub(r' #(\d+)(?=[ ,{\n]|$)',lambda m:' #ATTR['+attrs[m[1]]+']',body)
  return re.sub(r', !srcloc !\d+','',body)
 differences=[name for name in oldf if normalized(oldf[name],old_ir)!=normalized(newf[name],new_ir)];assert differences==[],differences
 olds=dict(re.findall(r'^(@ISEL_[^ =]+) = (.*)$',old_ir,re.M));news=dict(re.findall(r'^(@ISEL_[^ =]+) = (.*)$',new_ir,re.M));assert all(news.get(k)==v for k,v in olds.items())and set(news)-set(olds)=={'@ISEL_NEG_ASIMDMISC_R_2S'}
 old_members=subprocess.check_output(['llvm-ar-18','t',BASE/'decoder-libs/libremill_arch_aarch64.a'],text=True).splitlines();new_members=subprocess.check_output(['llvm-ar-18','t',archive],text=True).splitlines();assert old_members==new_members
 unchanged_members={}
 for name in old_members:
  if name in ['Arch.cpp.o','Decode.cpp.o']:continue
  olddata=subprocess.check_output(['llvm-ar-18','p',BASE/'decoder-libs/libremill_arch_aarch64.a',name]);newdata=subprocess.check_output(['llvm-ar-18','p',archive,name]);assert olddata==newdata;unchanged_members[name]=hashlib.sha256(newdata).hexdigest()
 identity=dict(passed=True,old_semantic_functions=len(oldf),new_semantic_functions=len(newf),all_old_semantic_operations_exact=True,attribute_IDs_resolved_by_full_content=True,only_inline_asm_source_coordinates_excluded=True,old_selectors=len(olds),new_selectors=len(news),all_old_selectors_byte_exact=True,added_selectors=['NEG_ASIMDMISC_R_2S'],unchanged_decoder_archive_members=unchanged_members,new_function_names=sorted(set(newf)-set(oldf)))
 save(B/'compiled-identity.json',identity)
 lifter=N/'bin/remill-lift-18';sem=N/'semantics/aarch64.bc';T=O/'toolchains'/(sha(lifter)[:16]+'-'+sha(sem)[:16]);T.parent.mkdir();shutil.copytree(BASE,T)
 for name in ['hashes.json','decoder-link-recipe.json']:(T/name).rename(T/('baseline-'+name))
 shutil.copyfile(lifter,T/'remill-lift');shutil.copyfile(sem,T/'aarch64.bc');shutil.copyfile(archive,T/'decoder-libs/libremill_arch_aarch64.a')
 save(T/'decoder-link-recipe.json',dict(baseline_recipe=desc(T/'baseline-decoder-link-recipe.json'),commands=commands,changed_archive=desc(T/'decoder-libs/libremill_arch_aarch64.a'),unchanged_archive_members=unchanged_members,all_other_decoder_libraries_and_headers_exact=True))
 frozen={p.relative_to(T).as_posix():sha(p)for p in T.rglob('*')if p.is_file()};save(T/'hashes.json',dict(files=frozen,toolchain={'remill-lift':sha(T/'remill-lift'),'aarch64.bc':sha(T/'aarch64.bc')}))
 result=dict(passed=True,selected=False,scope='NewisolatedNEG.2Sdecoder/semantics pair; no nativeexecution qualification or guestselection.',toolchain_dir=str(T),toolchain={'remill-lift':sha(T/'remill-lift'),'aarch64.bc':sha(T/'aarch64.bc')},source_producer=desc(source_producer),build_producer=desc(Path(__file__)),source_proof=desc(O/'source1/source-proof.json'),source_patch=desc(O/'source1/source.patch'),compiled_identity=desc(B/'compiled-identity.json'),commands=commands,max_compile_workers=2,borrowed_Lift_and_GuestCallLowering_objects={n:desc(N/'build'/n)for n in ['Lift.cpp.o','GuestCallLowering.o']},frozen_files={str(T/n):h for n,h in frozen.items()},qualified_baseline=dict(lifter=desc(BASE/'remill-lift'),semantics=desc(BASE/'aarch64.bc')),limits='OnlyQ0size2NEG genericRd/Rn addition; nootherNEGwidth/scalar/SQNEG/FPchanges. Oldsemanticoperations/selectors preserved (inlineasm sourcecoordinates excluded); decoderExtract/pass/libs borrowedunchanged. ActualARM/raw/polledsemantic/decodequalification andoriginalfunctionsplice stillrequired. No game/fullhost/cohortselection.')
 save(B/'acceptance.json',result);print('NEG2S-ISOLATED-PAIR',sha(B/'acceptance.json'),str(T),flush=True)
if __name__=='__main__':main()

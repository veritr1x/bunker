"""Real ANGLE observational snapshots; synthetic component, no game-frame claim."""
from pathlib import Path
import argparse,binascii,collections,hashlib,json,re,shutil,struct,subprocess,traceback,zlib
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
PARENT=W/'windows-first-frame-gl-draw1'
PARENT_SHA='382957667390947ffe8e7af58c38a980ea53bacf4221fb802ebf9cd74b1760e5'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def decode(p):
 data=p.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n';at=8;chunks=[];idat=bytearray();w=h=None
 while at<len(data):
  n=struct.unpack_from('>I',data,at)[0];kind=data[at+4:at+8];body=data[at+8:at+8+n];crc=struct.unpack_from('>I',data,at+8+n)[0];assert len(body)==n and binascii.crc32(kind+body)&0xffffffff==crc;at+=12+n;chunks.append(kind.decode())
  if kind==b'IHDR':w,h,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',body);assert(depth,color,compression,filtering,interlace)==(8,6,0,0,0)
  if kind==b'IDAT':idat+=body
  if kind==b'IEND':break
 assert at==len(data)and(w,h)==(320,240)and chunks[-1]=='IEND';raw=zlib.decompress(idat);stride=w*4;assert len(raw)==h*(stride+1);rows=[];pos=0
 def paeth(a,b,c):
  p=a+b-c;v=[abs(p-a),abs(p-b),abs(p-c)];return(a,b,c)[v.index(min(v))]
 for y in range(h):
  kind=raw[pos];pos+=1;row=bytearray(raw[pos:pos+stride]);pos+=stride;assert kind in range(5);up=rows[-1]if rows else bytes(stride)
  for x in range(stride):
   left=row[x-4]if x>=4 else 0;above=up[x];upperleft=up[x-4]if x>=4 else 0
   row[x]=(row[x]+(0,left,above,(left+above)//2,paeth(left,above,upperleft))[kind])&255
  rows.append(row)
 colors=collections.Counter(tuple(row[x:x+4])for row in rows for x in range(0,stride,4))
 return rows,colors,dict(file=desc(p),width=w,height=h,chunks=chunks,colors={str(k):v for k,v in colors.items()},decoder='Independent Python zlib/CRC/general PNG row filters0..4')
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=240):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 try:
  assert sha(PARENT/'overlay.json')==PARENT_SHA;pin(PARENT/'overlay.json');frozen=PARENT/'sources/recomp';source=out/'source'
  required={'windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp'}
  dependency_sources={}
  for folder in('windows','whole'):
   (source/folder).mkdir(parents=True)
   for p in(frozen/folder).iterdir():
    rel=folder+'/'+p.name
    if p.is_file()and(p.suffix in('.h','.inc')or rel in required):
     shutil.copyfile(p,source/rel);dependency_sources[rel]=desc(p);pin(p)
  for n in('gl_host.cpp','gl_host.h','frame_snapshot_test.cpp','test_frame_snapshot.py'):
   shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  # Every dependency is the selected frozen parent; only these two providers
  # and this distinct fixture/controller are taken from the workspace.
  dependency_sources={k:v for k,v in dependency_sources.items()if k not in('windows/gl_host.h',)}
  production={n:sha(source/n)for n in('windows/gl_host.cpp','windows/gl_host.h')}
  source_pins={str(p.relative_to(source)):sha(p)for p in source.rglob('*')if p.is_file()}
  native=W/'angle-scaling';dlls=native/'bundle/bin';remill=W/'remill-src';cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cxx)
  for root in(dlls,native/'src/include',remill/'include'):
   for p in root.rglob('*'):
    if p.is_file():pin(p)
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(remill/'include'),'-I'+wp(native/'src/include'),'-DCAPTURE_DLL_DIRECTORY=L"'+wp(dlls)+'"'];objects=[]
  for rel in('windows/frame_snapshot_test.cpp','windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp'):
   obj=out/(Path(rel).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if rel.endswith('frame_snapshot_test.cpp')else[]),'-c',wp(source/rel),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'frame-snapshot.exe';run([cxx,*map(wp,objects),'-static','-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)],'link')
  png=out/'first-frame.png';run([exe,wp(png)],'actual-ANGLE',180);log=(out/'actual-ANGLE.log').read_text();m=re.search(r'capture-snapshot-combined PASS checks=(\d+)',log);assert m and 'FRAME-SNAPSHOT-PASS'in log
  red=(255,0,0,255);blue=(0,0,255,255);green=(0,255,0,255);images={}
  for name,bg in(('first-frame.png',blue),('late-frame.png',green),('uniform-snapshot.png',green)):
   rows,colors,info=decode(out/name);pixel=lambda x,y:tuple(rows[y][x*4:x*4+4])
   if name=='uniform-snapshot.png':assert colors=={green:320*240}
   else:
    assert set(colors)=={red,bg}and colors[red]>500 and colors[bg]>500 and pixel(160,120)==red and pixel(2,2)==bg
    assert pixel(100,75)==bg and pixel(100,165)==red,'top-down triangle orientation';info['top_down_orientation_verified']=True
   images[name]=info
  assert images['first-frame.png']['file']['sha256']!=images['late-frame.png']['file']['sha256']!=images['uniform-snapshot.png']['file']['sha256']
  for p,h in source_pins.items():assert sha(source/p)==h,p
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,prepared_only=True,selected=False,production_sources=production,reviewed_production_sources=production,parent_manifest=desc(PARENT/'overlay.json'),frozen_parent_dependencies=dependency_sources,source_snapshot=source_pins,held_inputs=held,focused=dict(checks=int(m[1]),existing_first_frame_fixture_prefix_preserved=True,first_frame_capture_attempts=70,uniform_swaps_before_first_frame=65,UI_thread_request=True,request_performs_no_GL_calls=True,matched_original_EGL_TRUE_required=True,consumed_failed_mismatched_foreign_abandoned_tickets=True,pending_request_retries=True,first_frame_PNG_and_witness_unchanged=True,uniform_snapshot_saved_as_is=True,snapshot_write_failure_separate=True,pack_PBO_read_FBO_GL_errors_and_FENV_preserved=True,independent_PNG_decoder=True),PNGs=images,executable=desc(exe),stdout=desc(out/'actual-ANGLE.log'),commands=commands,original_game_executed=False,original_frame_claim=False,limits=['Synthetic hidden native ANGLE window only; no original Unity/game execution or game-frame claim.','All non-GL provider dependencies are copied from selected parent382957; pending runtime/thread-exit workspace changes excluded.','Existing legacy first-frame fixture prefix is preserved; later draw/clear counters advance naturally, original witness and PNG stay fixed.'])
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FRAME-SNAPSHOT-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()

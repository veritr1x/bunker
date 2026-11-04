"""One synthetic native Windows ANGLE capture-smoke; not an original Unity/game frame."""
from pathlib import Path
import argparse,hashlib,json,shutil,struct,subprocess,zlib,binascii,collections
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False)
 def sha(p):
  with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 source=O/'source';(source/'windows').mkdir(parents=True);(source/'whole').mkdir()
 needed=['frame_capture_smoke_test.cpp','egl_host.cpp','egl_host.h','gl_host.cpp','gl_host.h','gl_scalar_commands.inc','gl_draw_commands.inc','native_window.cpp','native_window.h','jni_host.cpp','jni_host.h','frame_png.h']
 needed=sorted(set(needed)|{f.name for f in HERE.glob('gl_*.inc')})
 for n in needed:shutil.copy2(HERE/n,source/'windows'/n)
 for f in(HERE.parent/'whole').iterdir():
  if f.is_file()and(f.suffix in('.h','.inc')or f.name=='runtime.cpp'):shutil.copy2(f,source/'whole'/f.name)
 shutil.copy2(__file__,O/'executed-runner.py')
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';ANGLE=W/'angle-native';dlls=ANGLE/'bundle/bin';headers=ANGLE/'src/include';cxx=Path('/mnt/c/mingw64/bin/g++.exe')
 sources={str(f):sha(f)for f in source.rglob('*')if f.is_file()};live={str(HERE/n):sha(HERE/n)for n in needed};inputs={str(cxx):sha(cxx),str(Path(__file__)):sha(__file__)}
 for root in(T/'include',headers):
  for f in root.rglob('*'):
   if f.is_file():inputs[str(f)]=sha(f)
 for f in dlls.iterdir():
  if f.is_file():inputs[str(f)]=sha(f)
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(T/'include'),'-I'+wp(headers),f'-DCAPTURE_DLL_DIRECTORY=L"{wp(dlls)}"'];commands=[]
 def run(cmd,name,timeout=180):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with(O/(name+'.log')).open('w')as f:q=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  text=(O/(name+'.log')).read_text(errors='replace')
  if q.returncode:raise RuntimeError(name+' exit'+str(q.returncode)+'\n'+text[-7000:])
  return text
 test=source/'windows/frame_capture_smoke_test.cpp';run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(test)],'strict-test-source')
 objs=[]
 for rel in('windows/frame_capture_smoke_test.cpp','windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp'):
  f=source/rel;obj=O/(f.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if f.stem=='frame_capture_smoke_test'else[]),'-c',wp(f),'-o',wp(obj)],'compile-'+f.stem);objs.append(obj)
 exe=O/'capture-smoke.exe';run([cxx,'-static',*map(wp,objs),'-latomic','-pthread','-luser32','-o',wp(exe)],'native-link')
 sourcepin=dict(scope='Actual mutable provider snapshot before the one synthetic capture-smoke',sources=sources,live_provider_and_test_sources=live,inputs=inputs,executable_sha256=sha(exe));(O/'source-pin.json').write_text(json.dumps(sourcepin,indent=2)+'\n')
 png=O/'capture-smoke.png';log=run([exe,wp(png)],'capture-smoke',60);assert 'capture-smoke PASS'in log and 'synthetic_only=1'in log
 # Independent PNG decoder: standard zlib plus general PNG filters0..4,
 # independent of the C++ writer's stored-DEFLATE/filter0 implementation.
 data=png.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n';at=8;chunks=[];idat=bytearray();w=h=None
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
   predictor=(0,left,above,(left+above)//2,paeth(left,above,upperleft))[kind];row[x]=(row[x]+predictor)&255
  rows.append(row)
 pixel=lambda x,y:tuple(rows[y][x*4:x*4+4]);colors=collections.Counter(tuple(row[x:x+4])for row in rows for x in range(0,stride,4));red=(255,0,0,255);blue=(0,0,255,255)
 assert colors[red]>500 and colors[blue]>500 and pixel(w//2,h//2)==red and pixel(2,2)==blue
 assert pixel(w*5//16,h*5//16)==blue and pixel(w*5//16,h*11//16)==red,'PNG top-down orientation differs from original GL triangle'
 for group in(sources,live,inputs):
  for p,hsh in group.items():assert sha(p)==hsh,p
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=dict(passed=True,label='capture-smoke',synthetic_component_QA=True,original_Unity_frame=False,one_native_test_execution=True,scope='Real320x240 hidden HWND/ANGLE window;65 uniform successful swaps, failed candidate and unrelated-success rejection, consumed mismatched thread/context/surface tickets, then own matching EGL_TRUE publishes typed nonuniform triangle; pack/PBO/read-FBO/GL-error and caller environment preservation',source_pin_path=str(O/'source-pin.json'),source_pin_sha256=sha(O/'source-pin.json'),source_sha256=sources,provider_live_sha256=live,input_sha256=inputs,executable_sha256=sha(exe),PNG=dict(path=str(png),sha256=sha(png),width=w,height=h,chunks=chunks,decoder='Independent Python zlib/CRC/general PNG row filter0..4',red_pixels=colors[red],blue_pixels=colors[blue],unique_colors=len(colors),top_down_orientation_verified=True),stdout=log,evidence={str(f):sha(f)for f in O.iterdir()if f.is_file()},limits=['Synthetic component only; no NDK lifting or original Unity/game execution','Triangle draw/shader/buffer calls use typed GlHost; native same-ANGLE calls only create/probe otherwise unsupported read-FBO state','No user-visible Unity image, completed init/render loop or game screenshot claim'])
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('CAPTURE-SMOKE-PASS',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl31.h>
#include <EGL/egl.h>
#include "gles_service_module.h"
#include "egl_host.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "gl_internalformat_old_commands.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <set>
#include <stdexcept>
#include <thread>
#include <vector>
using namespace bunker::windows;
namespace {
unsigned checks=0,calls=0,records=0;GlHost*graphics=nullptr;EglHost*egl_provider=nullptr;
void Check(bool ok,const char*why){if(!ok)throw std::runtime_error(why);++checks;}
addr_t Address(const void*p){return reinterpret_cast<addr_t>(p);}
template<class F>F Native(HMODULE m,const char*n){auto p=GetProcAddress(m,n);if(!p)throw std::runtime_error(n);F f;std::memcpy(&f,&p,sizeof(f));return f;}
void*Resolve(const char*n){return reinterpret_cast<void*>(!std::strcmp(n,"eglGetProcAddress")?egl_provider->Marker(n):graphics->Marker(n));}
template<class H>addr_t Invoke(H&h,const char*n,std::initializer_list<addr_t>a={}){State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};size_t i=0;for(auto v:a)(s.gpr.*r[i++]).qword=v;h.Invoke(n,s);return s.gpr.x0.qword;}
}
int main(){try{
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(90));std::fputs("internalformat component watchdog\n",stderr);std::_Exit(95);}).detach();
 bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;EglHost egl(windows,GL_INTERNALFORMAT_DLL_DIRECTORY);egl_provider=&egl;egl.Install(runtime);GlHost gl(egl,GL_INTERNALFORMAT_DLL_DIRECTORY);graphics=&gl;gl.Install(runtime);egl.SetProcedureResolver([&](const std::string&name){return FindTypedGlesProcedure(gl,name);});
 auto display=Invoke(egl,"eglGetDisplay");Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"real ANGLE display");const GLint attrs[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,EGL_NONE};addr_t config=0;GLint configs=0;Check(Invoke(egl,"eglChooseConfig",{display,Address(attrs),Address(&config),1,Address(&configs)})&&configs==1,"real GLES3 configuration");const GLint ca[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_CONTEXT_MINOR_VERSION,1,EGL_NONE},sa[]={EGL_WIDTH,8,EGL_HEIGHT,8,EGL_NONE};auto context=Invoke(egl,"eglCreateContext",{display,config,0,Address(ca)});auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,Address(sa)});Check(context&&surface,"owned GLES3.1 pbuffer/context");auto Bind=[&]{Check(Invoke(egl,"eglMakeCurrent",{display,surface,surface,context})!=0,"owned current context");};Bind();
 const auto driver=GetModuleHandleW(L"libGLESv2.dll");auto query=Native<PFNGLGETINTERNALFORMATIVPROC>(driver,"glGetInternalformativ");auto native_error=Native<PFNGLGETERRORPROC>(driver,"glGetError");auto Error=[&]{return GLenum(Invoke(gl,"glGetError"));};
 Check(std::size(kOldInternalFormatCommands)==115&&GlHost::Commands().size()==116,"exact old115 and one appended command");for(size_t n=0;n<115;++n)Check(GlHost::Commands()[n]==kOldInternalFormatCommands[n]&&gl.Marker(kOldInternalFormatCommands[n])==gl.Marker(kOldInternalFormatCommands[0])+n*8,"every old115 name/marker retained");const auto marker=gl.Marker("glGetInternalformativ");Check(marker==gl.Marker(kOldInternalFormatCommands[0])+115*8&&marker!=reinterpret_cast<addr_t>(query),"new marker appended115, never native address");
 const auto service=MakeGlesServiceModule(gl);Check(service.name=="libGLESv2.so"&&service.kind==Module::Kind::TypedService&&service.exports.size()==116&&service.exports.at("glGetInternalformativ")==marker&&!service.address_image&&service.initializers.empty()&&service.finalizers.empty(),"actual shared service factory exports the new typed marker");Check(FindTypedGlesProcedure(gl,"glGetInternalformativ")==marker&&!FindTypedGlesProcedure(gl,"notARealInternalformatProcedure"),"actual shared nullable lookup exports no native function pointer");
 elf_image image{};Check(!elf_load(GL_INTERNALFORMAT_IMAGE,0x5f000000,Resolve,&image),"actual original NDK internalformat callers");runtime.AddTraces(kTraces,std::size(kTraces));
 auto Run=[&](const char*name,GLenum target,GLenum format,GLenum pname,GLsizei capacity,addr_t output,bool poison=false){alignas(16)std::array<uint8_t,65536>stack{};State s{};const auto sp=Address(stack.data()+stack.size());s.gpr.sp.qword=sp;s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=UINT64_C(0x123456789abcdef0);s.gpr.x0.qword=target;s.gpr.x1.qword=format;s.gpr.x2.qword=pname;s.gpr.x3.qword=uint32_t(capacity);s.gpr.x4.qword=output;if(poison){s.gpr.x0.qword|=UINT64_C(0xa5a5a5a500000000);s.gpr.x3.qword|=UINT64_C(0x8765432100000000);}const auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(entry!=0,"NDK caller export");auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));Check(runtime.Run(s,entry,token)==token&&s.gpr.sp.qword==sp&&s.gpr.x19.qword==UINT64_C(0x123456789abcdef0)&&s.gpr.x30.qword==0xfeedffff&&s.gpr.pc.qword==0xfeedffff,"actual NDK return/SP/callee register/token");++calls;if(!std::strcmp(name,"internalformat_procedure"))Check(s.gpr.x0.qword==marker,"actual NDK eglGetProcAddress result is typed marker and invoked");};
 constexpr GLint sentinel=0x13572468;bool zero_count=false;GLint rgba_count=-1;
 for(GLenum format:{GL_RGBA8,GL_DEPTH_COMPONENT16,GL_RGBA8UI}){
  GLint count=-1;query(GL_RENDERBUFFER,format,GL_NUM_SAMPLE_COUNTS,1,&count);Check(native_error()==GL_NO_ERROR&&count>=0&&count<=4096,"actual native sample-count bound");if(format==GL_RGBA8)rgba_count=count;if(!count)zero_count=true;std::printf("INTERNALFORMAT native format=%#x count=%d\n",unsigned(format),count);
  std::set<GLsizei>capacities{-1,0,1,std::max(count-1,0),count,count+3,8,std::numeric_limits<GLsizei>::max()};
  for(GLenum pname:{GL_NUM_SAMPLE_COUNTS,GL_SAMPLES})for(GLsizei capacity:capacities){
   const size_t maximum=size_t(std::max(count,1));std::vector<GLint>expected(maximum+2,sentinel),actual=expected;query(GL_RENDERBUFFER,format,pname,capacity,expected.data());const auto expected_error=native_error();const char*wrapper=records%3==0?"internalformat_direct":records%3==1?"internalformat_indirect":"internalformat_procedure";Run(wrapper,GL_RENDERBUFFER,format,pname,capacity,Address(actual.data()),records==0);const auto actual_error=Error();Check(actual_error==expected_error&&actual==expected,"native counts/errors and untouched truncated/full/huge capacity tail match");const auto written=capacity>0?(pname==GL_NUM_SAMPLE_COUNTS?size_t(1):std::min(size_t(capacity),size_t(count))):size_t(0);Check(std::all_of(actual.begin()+written,actual.end(),[](GLint v){return v==sentinel;}),"only actual native footprint is published");++records;
  }
 }
 Check(rgba_count>0,"positive native sample-count format exercised");std::printf("INTERNALFORMAT native_zero_count_branch_exercised=%u; no synthetic zero-count override\n",unsigned(zero_count));
 // Literal invalid client addresses cannot be accessed when capacity is <=0.
 for(GLsizei capacity:{-1,0})for(GLenum pname:{GL_NUM_SAMPLE_COUNTS,GL_SAMPLES}){GLint unused=sentinel;query(GL_RENDERBUFFER,GL_RGBA8,pname,capacity,&unused);auto expected=native_error();Run("internalformat_direct",GL_RENDERBUFFER,GL_RGBA8,pname,capacity,1);Check(Error()==expected&&unused==sentinel,"nonpositive capacity never accesses guest output");}
 // Native target/format/capacity error ordering is retained without publication.
 struct Invalid {GLenum target,format;GLsizei capacity;};for(auto invalid:{Invalid{0,GL_RGBA8,4},Invalid{GL_RENDERBUFFER,0,4},Invalid{0,0,-1}})for(GLenum pname:{GL_NUM_SAMPLE_COUNTS,GL_SAMPLES}){std::array<GLint,6>expected,actual;expected.fill(sentinel);actual=expected;query(invalid.target,invalid.format,pname,invalid.capacity,expected.data());auto error=native_error();Run("internalformat_indirect",invalid.target,invalid.format,pname,invalid.capacity,Address(actual.data()));Check(error!=GL_NO_ERROR&&Error()==error&&actual==expected,"native invalid target/format/negative precedence leaves output untouched");}
 // Exact real output boundary; no bufSize-sized guest write or guest pointer native.
 SYSTEM_INFO info{};GetSystemInfo(&info);auto pages=static_cast<uint8_t*>(VirtualAlloc(nullptr,size_t(info.dwPageSize)*2,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(pages!=nullptr,"guard storage");DWORD old=0;Check(VirtualProtect(pages+info.dwPageSize,info.dwPageSize,PAGE_NOACCESS,&old)!=0,"native guard page");const size_t written=std::min(size_t(1),size_t(rgba_count));auto out=pages+info.dwPageSize-written*4;std::memset(pages,0xa5,info.dwPageSize);Run("internalformat_procedure",GL_RENDERBUFFER,GL_RGBA8,GL_SAMPLES,1,Address(out));Check(!Error()&&std::all_of(pages,pages+info.dwPageSize-written*4,[](uint8_t c){return c==0xa5;}),"sample query exact footprint reaches guard page");Check(VirtualFree(pages,0,MEM_RELEASE)!=0,"guard storage retired");
 Invoke(gl,"glEnable",{0xffffffffU});GLint pending=sentinel;Run("internalformat_direct",GL_RENDERBUFFER,GL_RGBA8,GL_NUM_SAMPLE_COUNTS,1,Address(&pending));Check(pending==rgba_count&&Error()==GL_INVALID_ENUM&&!Error(),"internal helper preserves preexisting native error once");
 GLint untouched=sentinel;bool rejected=false;try{Invoke(gl,"glGetInternalformativ",{GL_RENDERBUFFER,GL_RGBA8,GL_VIEWPORT,1,Address(&untouched)});}catch(const std::runtime_error&e){rejected=std::strstr(e.what(),"Unsupported GL internal-format query output width")!=nullptr;}Check(rejected&&untouched==sentinel&&!Error(),"unknown pname stays explicitly unsupported without guest publication");
 Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})!=0,"release context before tracked test");alignas(64)GLint same=rgba_count;auto tracked=bunker::test::ReserveAcrossOperation(Address(&same),4,[&]{Bind();Run("internalformat_direct",GL_RENDERBUFFER,GL_RGBA8,GL_NUM_SAMPLE_COUNTS,1,Address(&same));egl.ReleaseCurrentThread();});Check(tracked.status==1&&same==rgba_count,"same-value internalformat result is a tracked write across threads");Bind();
 Check(!Error()&&Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglTerminate",{display}),"owned context and surfaces retired");egl.ReleaseCurrentThread();egl.SetProcedureResolver({});std::printf("GL-INTERNALFORMAT-PASS checks=%u calls=%u records=%u commands=1 old_prefix=115 real_ANGLE=1 synthetic_component=1\n",checks,calls,records);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"internalformat component: %s\n",e.what());return 1;}}

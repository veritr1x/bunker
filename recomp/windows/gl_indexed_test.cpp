#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl32.h>
#include <EGL/egl.h>
#include "gl_host.h"
#include "egl_host.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
using namespace bunker::windows;
static unsigned checks;
static EglHost *egl_provider;
static void Check(bool value,const char *reason){if(!value)throw std::runtime_error(reason);++checks;}
static addr_t Address(const void *p){return reinterpret_cast<addr_t>(p);}
template<class T>static addr_t Invoke(T &host,const char *name,std::initializer_list<addr_t> args={}){
  State state{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t i=0;
  for(auto value:args)(state.gpr.*regs[i++]).qword=value;
  host.Invoke(name,state);return state.gpr.x0.qword;
}
static void *Resolve(const char *name){return reinterpret_cast<void*>(egl_provider->Marker(name));}
template<class T>static T Native(HMODULE module,const char *name){
  auto p=GetProcAddress(module,name);Check(p!=nullptr,"native symbol exists");
  T value;static_assert(sizeof(value)==sizeof(p));std::memcpy(&value,&p,sizeof(value));return value;
}
int main(){try{
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;
  EglHost egl(windows,GL_INDEXED_DLL_DIRECTORY);egl_provider=&egl;egl.Install(runtime);
  GlHost gl(egl,GL_INDEXED_DLL_DIRECTORY);gl.Install(runtime);
  egl.SetProcedureResolver([&](const std::string &name){return gl.Marker(name);});
  auto driver=GetModuleHandleW(L"libGLESv2.dll");Check(driver!=nullptr,"same actual ANGLE module");
  auto query=Native<PFNGLGETINTEGERI_VPROC>(driver,"glGetIntegeri_v");
  auto error=Native<PFNGLGETERRORPROC>(driver,"glGetError");
  const auto display=Invoke(egl,"eglGetDisplay",{0});Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"real display initialized");
  const int config_args[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,0x40,EGL_NONE};
  addr_t config=0;int count=0;Check(Invoke(egl,"eglChooseConfig",{display,Address(config_args),Address(&config),1,Address(&count)})&&count==1,"actual GLES3 config");
  const int context_args[]={EGL_CONTEXT_CLIENT_VERSION,3,0x30fb,1,EGL_NONE},surface_args[]={EGL_WIDTH,4,EGL_HEIGHT,4,EGL_NONE};
  const auto context=Invoke(egl,"eglCreateContext",{display,config,0,Address(context_args)});
  const auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,Address(surface_args)});Check(context&&surface,"actual context and pbuffer");
  auto Bind=[&]{Check(Invoke(egl,"eglMakeCurrent",{display,surface,surface,context})!=0,"bind owned context");};Bind();
  elf_image image{};Check(!elf_load(GL_INDEXED_LIBRARY,0x5d000000,Resolve,&image),"strict NDK indexed fixture loads");runtime.AddTraces(kTraces,std::size(kTraces));
  auto Guest=[&](const char *name,std::initializer_list<addr_t> args={}){
    alignas(16)std::array<uint8_t,65536> stack{};State state{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t i=0;
    for(auto value:args)(state.gpr.*regs[i++]).qword=value;
    state.gpr.sp.qword=Address(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;
    auto entry=elf_symbol(&image,name);Check(entry!=nullptr,"actual NDK entry exists");runtime.Run(state,Address(entry));
    Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==Address(stack.data()+stack.size()),"NDK normal PC/SP return");return state.gpr.x0.qword;
  };
  Check(Guest("gl_indexed_resolve")==gl.Marker("glGetIntegeri_v"),"NDK gets typed marker, never native function pointer");
  Check(gl.Marker("glGetIntegeri_v")==0x7ff450000000ULL+114*8,"new indexed marker appended at index114");
  Check(gl.Marker("glGetString")==0x7ff450000000ULL&&gl.Marker("glPixelStorei")==0x7ff450000000ULL+62*8,"original marker prefix preserved");
  auto allocation=static_cast<uint8_t*>(VirtualAlloc(nullptr,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(allocation!=nullptr,"guard allocation");
  struct Release{void *p;~Release(){VirtualFree(p,0,MEM_RELEASE);}} release{allocation};
  DWORD previous;Check(VirtualProtect(allocation+4096,4096,PAGE_NOACCESS,&previous)!=0,"native output guard page");
  auto output=reinterpret_cast<GLint*>(allocation+4092);std::memset(allocation,0xa5,4096);
  std::array<GLint,6> valid{};size_t n=0;
  for(GLenum target:{GLenum(GL_MAX_COMPUTE_WORK_GROUP_COUNT),GLenum(GL_MAX_COMPUTE_WORK_GROUP_SIZE)}){
    for(GLuint index:{0U,1U,2U,3U,0xffffffffU}){
      const GLint sentinel=0x13572468;GLint expected=sentinel;Check(error()==GL_NO_ERROR,"native reference starts without error");
      query(target,index,&expected);const GLenum native_error=error();*output=sentinel;
      Guest("gl_indexed_query",{target,index,Address(output)});const GLenum actual_error=GLenum(Invoke(gl,"glGetError"));
      Check(*output==expected&&actual_error==native_error,"NDK indexed result and error exactly match native ANGLE");
      if(index<3){Check(actual_error==GL_NO_ERROR&&*output>0,"actual native indexed capability returned");valid[n++]=*output;}
      else Check(actual_error==GL_INVALID_VALUE&&*output==sentinel,"out-of-range native index leaves output unchanged");
      bool prefix=true;for(size_t k=0;k<4092;++k)prefix=prefix&&allocation[k]==0xa5;Check(prefix,"exact four-byte guest publication at guard boundary");
    }
  }
  Invoke(gl,"glEnable",{0xffffffffU});Guest("gl_indexed_query",{GL_MAX_COMPUTE_WORK_GROUP_SIZE,0,Address(output)});
  Check(*output==valid[3]&&Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==0,"successful indexed query preserves prior native error");
  *output=0x13572468;bool rejected=false;
  try{Invoke(gl,"glGetIntegeri_v",{GL_VIEWPORT,0,Address(output)});}catch(const std::runtime_error &e){rejected=std::string(e.what()).find("Unsupported indexed GL query output width")!=std::string::npos;}
  Check(rejected&&*output==0x13572468&&Invoke(gl,"glGetError")==0,"other indexed widths remain named unsupported without guest write/native call");
  alignas(64)GLint same=valid[3];Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"release before cross-thread tracked write");
  auto tracked=bunker::test::ReserveAcrossOperation(Address(&same),4,[&]{Bind();Guest("gl_indexed_query",{GL_MAX_COMPUTE_WORK_GROUP_SIZE,0,Address(&same)});egl.ReleaseCurrentThread();});
  Check(tracked.status==1&&same==valid[3],"same-value indexed output is a tracked guest write");Bind();
  Check(Invoke(gl,"glGetError")==0,"native context remains error-free");
  Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"unbind before teardown");
  Check(Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglTerminate",{display}),"real context/surface/display teardown");
  egl.ReleaseCurrentThread();egl.SetProcedureResolver({});
  std::printf("GL indexed: count=%d,%d,%d size=%d,%d,%d; %u checks passed; one NDK signature/two scalar targets, real ANGLE, no compute execution or game claim\n",valid[0],valid[1],valid[2],valid[3],valid[4],valid[5],checks);return 0;
}catch(const std::exception &e){std::fprintf(stderr,"GL indexed failure: %s\n",e.what());return 1;}}

#define wmain graphics_probe_unused_main
#include "graphics_probe.cpp"
#undef wmain
#include "egl_host.h"
#include "../fastaes/elfload.h"
#include "../whole/bridge.h"
#include "traces.h"
#include <atomic>
#include <thread>
using bunker::windows::EglHost;
using bunker::windows::NativeWindows;
namespace {
std::atomic<unsigned> checks{0};EglHost *host;NativeWindows *windows;unsigned draws=0;void *diagnostic_window=nullptr;
thread_local const std::function<void(State&)> *reservation_body=nullptr;
Memory *ReservationEntry(State &state,addr_t,Memory *memory){(*reservation_body)(state);state.gpr.pc.qword=state.gpr.x30.qword;return memory;}
constexpr addr_t draw_marker=0x7ff420001000ULL;
void Check(bool value,const char *message){++checks;if(!value){std::fprintf(stderr,"EGL host check: %s\n",message);std::abort();}}
void *Resolve(const char *name){if(std::string(name)=="host_egl_draw_check")return reinterpret_cast<void*>(draw_marker);
  if(std::string(name).find("ANativeWindow_")==0)return reinterpret_cast<void*>(windows->Marker(name));
  return reinterpret_cast<void*>(host->Marker(name));}
addr_t Invoke(const char *name,std::initializer_list<addr_t> arguments={}){
  State state{};static constexpr Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};unsigned i=0;
  for(auto value:arguments)(state.gpr.*regs[i++]).qword=value;
  host->Invoke(name,state);return state.gpr.x0.qword;
}
U Draw(Probe &gl,I width,I height){
  bunker::windows::WindowDpiScope dpi(diagnostic_window);
  U vao=0;gl.glGenVertexArrays(1,&vao);gl.glBindVertexArray(vao);
  U program=gl.program({gl.shader(0x8b31,"#version 310 es\nvoid main(){const vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexID],0,1);}"),
    gl.shader(0x8b30,"#version 310 es\nprecision highp float;layout(location=0) out vec4 color;void main(){color=vec4(1,0,0,1);}")});
  gl.glViewport(0,0,width,height);gl.glClearColor(0,0,1,1);gl.glClear(0x4000);gl.glUseProgram(program);gl.glDrawArrays(4,0,3);gl.glFinish();
  std::array<uint8_t,256> pixels{};gl.glPixelStorei(0x0d05,1);gl.glReadPixels(0,0,8,8,0x1908,0x1401,pixels.data());gl.glCheck("EGL host native-only diagnostic draw");
  bool ok=true;for(size_t i=0;i<pixels.size();++i)ok&=pixels[i]==(i%4==0||i%4==3?255:0);
  gl.glDeleteVertexArrays(1,&vao);gl.glDeleteProgram(program);++draws;return ok;
}
}
int main(){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(60));std::fputs("EGL host watchdog\n",stderr);std::_Exit(95);}).detach();
  bunker::jni::Host java([](addr_t){return false;});recomp::Runtime runtime;NativeWindows native(java);windows=&native;native.Install(runtime);
  EglHost egl(native,EGL_HOST_DLL_DIRECTORY);host=&egl;egl.Install(runtime);
  Probe gl;gl.egl=GetModuleHandleW(L"libEGL.dll");gl.gles=GetModuleHandleW(L"libGLESv2.dll");
  gl.eglGetProcAddress=gl.eglSymbol<Probe::eglGetProcAddressT>("eglGetProcAddress");
#define LOAD_GL(ret,name,args) gl.name=gl.glSymbol<Probe::name##T>(#name);
  GL_APIS(LOAD_GL)
#undef LOAD_GL
  runtime.AddImport(draw_marker,recomp::MakeBridge<U(I,I)>([&](I w,I h){return Draw(gl,w,h);}));
  auto window=native.Create(640,360,u"Bunker EGL integration",false);auto surface=native.NewSurface(window);auto native_token=native.FromSurface(surface);diagnostic_window=native.NativeHandle(native_token);native.Release(native_token);
  elf_image image{};Check(!elf_load(EGL_HOST_LIBRARY,0x5d000000,Resolve,&image),"real NDK EGL caller loads all19 imports");
  runtime.AddTraces(kTraces,std::size(kTraces));alignas(16)uint8_t stack[131072]{};uint64_t results[64]{};State state{};
  state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=surface;state.gpr.x2.qword=reinterpret_cast<addr_t>(results);
  state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));state.gpr.x30.qword=0xfeedffff;
  runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"egl_guest")));
  Check(state.gpr.x0.qword==33&&draws==2,"complete33-result NDK EGL lifetime sequence and two real draws");
  for(size_t i=0;i<state.gpr.x0.qword;++i){if(results[i]!=1)std::fprintf(stderr,"NDK EGL result %zu failed\n",i);Check(results[i]==1,"NDK EGL result");}
  Check(state.gpr.sp.qword==reinterpret_cast<addr_t>(stack+sizeof(stack))&&java.PendingException().empty(),"balanced guest SP and clean JNI state");
  const auto display=Invoke("eglGetDisplay",{0});Check(display&&Invoke("eglInitialize",{display,0,0}),"null version outputs supported");
  const int attrs[]={0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3040,0x40,0x3033,5,0x302e,1,0x3038};addr_t config=0;int count=0;
  Check(Invoke("eglChooseConfig",{display,reinterpret_cast<addr_t>(attrs),reinterpret_cast<addr_t>(&config),1,reinterpret_cast<addr_t>(&count)})&&count==1,"Android logical visual filter translated to real config selection");
  struct Guard{uint32_t before;int value;uint32_t after;} output{0x12345678,-1,0x87654321};
  recomp::Runtime reservation_runtime;const recomp::Trace reservation_trace{0x6000,ReservationEntry};reservation_runtime.AddTraces(&reservation_trace,1);
  output.value=1;std::function<void(State&)> reserved=[&](State &reservation){
    __remill_aarch64_load_exclusive(reservation,reinterpret_cast<addr_t>(&output.value),4,0);
    std::thread writer([&]{Check(Invoke("eglGetConfigAttrib",{display,config,0x302e,reinterpret_cast<addr_t>(&output.value)}),"cross-thread tracked EGL output");egl.ReleaseCurrentThread();});writer.join();
    Check(output.value==1&&output.before==0x12345678&&output.after==0x87654321,"EGLint writes exactly four bytes");
    Check(__remill_aarch64_store_exclusive(reservation,reinterpret_cast<addr_t>(&output.value),9,4,0)==1,"same-value EGL output invalidates guest reservation");
  };
  reservation_body=&reserved;State reservation{};reservation.gpr.x30.qword=0xfeedffff;reservation_runtime.Run(reservation,0x6000);reservation_body=nullptr;
  Check(!Invoke("eglQuerySurface",{display,0x12345678,0x3057,reinterpret_cast<addr_t>(&output.value)})&&Invoke("eglGetError")==0x300d&&Invoke("eglGetError")==0x3000,"invalid opaque surface reports and clears native-style error");
  const char unknown[]="glGetString";bool unsupported=false;try{Invoke("eglGetProcAddress",{reinterpret_cast<addr_t>(unknown)});}catch(const std::runtime_error &e){unsupported=std::string(e.what()).find(unknown)!=std::string::npos;}
  Check(unsupported,"untyped GL resolver fails explicitly without native pointer");
  auto leased=native.Create(640,360,u"Bunker EGL retained HWND",false);auto leased_java=native.NewSurface(leased);auto leased_token=native.FromSurface(leased_java);
  const auto lease=Invoke("eglCreateWindowSurface",{display,config,leased_token,0});Check(lease!=0,"real window surface owns native window lease");
  native.Release(leased_token);java.DeleteLocalReference(leased_java);leased.reset();
  Check(native.Width(leased_token)==640,"EGL native reference alone retains HWND after Java and host release");
  Check(native.SetBuffersGeometry(leased_token,320,240,1)==-38&&native.Width(leased_token)==640,"nondefault buffer scaling remains explicitly unsupported");
  Check(Invoke("eglDestroySurface",{display,lease})&&native.Width(leased_token)==-19,"retiring EGL surface releases final HWND lease");
  Check(!Invoke("eglDestroySurface",{display,lease})&&Invoke("eglGetError")==0x300d,"stale EGL token cannot alias later objects");
  Check(Invoke("eglTerminate",{display}),"second initialization terminates cleanly");
  egl.ReleaseCurrentThread();native.Close(window);java.DeleteLocalReference(surface);window.reset();
  std::printf("EGL host: %u checks; actual19 NDK imports, tracked EGLint, real HWND and pbuffer draws/readback/swap, deferred lifetime; GL resolver and fixed-size scaling remain explicit.\n",checks.load());
}

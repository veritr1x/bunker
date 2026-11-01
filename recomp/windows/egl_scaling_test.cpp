#define wmain graphics_probe_unused_main
#include "graphics_probe.cpp"
#undef wmain
#include "egl_host.h"
#include "../fastaes/elfload.h"
#include "../whole/bridge.h"
#include "traces.h"
#include <atomic>
#include <thread>
using bunker::windows::EglHost;using bunker::windows::NativeWindows;
namespace {
std::atomic<unsigned> checks{0};EglHost *host;NativeWindows *native;NativeWindows::Handle window;addr_t token;unsigned draws=0,resizes=0;
constexpr addr_t draw_marker=0x7ff420001000ULL,resize_marker=0x7ff420001008ULL;
void Check(bool value,const char *why){++checks;if(!value){std::fprintf(stderr,"EGL scaling integration check: %s\n",why);std::abort();}}
void *Resolve(const char *name){const std::string text=name;if(text=="host_buffer_draw")return reinterpret_cast<void*>(draw_marker);if(text=="host_window_resize")return reinterpret_cast<void*>(resize_marker);
  if(text.find("ANativeWindow_")==0)return reinterpret_cast<void*>(native->Marker(text));
  return reinterpret_cast<void*>(host->Marker(text));}
U Draw(Probe &gl,I width,I height){
  const auto geometry=native->Describe(token);Check(geometry.width==width&&geometry.height==height,"published Android buffer geometry matches render dimensions");
  if(draws==0){int error=0;std::thread other([&]{error=native->SetBuffersGeometry(token,320,180,1);});other.join();Check(error==-16,"geometry update on another current context owner is explicitly rejected");}
  bunker::windows::WindowDpiScope dpi(native->NativeHandle(token));U vao=0;gl.glGenVertexArrays(1,&vao);gl.glBindVertexArray(vao);
  U program=gl.program({gl.shader(0x8b31,"#version 310 es\nvoid main(){const vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexID],0,1);}"),gl.shader(0x8b30,"#version 310 es\nprecision highp float;layout(location=0) out vec4 color;void main(){color=vec4(0,1,0,1);}")});
  gl.glViewport(0,0,width,height);gl.glUseProgram(program);gl.glClearColor(1,0,0,1);gl.glClear(0x4000);gl.glDrawArrays(4,0,3);gl.glFinish();
  for(auto xy:{std::pair<I,I>{0,0},{width-1,height-1},{width/2,height/2}}){std::array<uint8_t,4> pixel{};gl.glReadPixels(xy.first,xy.second,1,1,0x1908,0x1401,pixel.data());Check(pixel==std::array<uint8_t,4>{0,255,0,255},"real logical buffer corner/center readback");}
  gl.glCheck("NDK scaled buffer native draw");gl.glDeleteVertexArrays(1,&vao);gl.glDeleteProgram(program);++draws;return 1;
}
}
int main(){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(60));std::fputs("EGL scaling integration watchdog\n",stderr);std::_Exit(95);}).detach();
  bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);native=&windows;recomp::Runtime runtime;windows.Install(runtime);
  EglHost egl(windows,EGL_SCALING_DLL_DIRECTORY);host=&egl;egl.Install(runtime);window=windows.Create(640,360,u"Bunker NDK fixed-buffer integration",false);auto surface=windows.NewSurface(window);token=windows.FromSurface(surface);
  Probe gl;gl.egl=GetModuleHandleW(L"libEGL.dll");gl.gles=GetModuleHandleW(L"libGLESv2.dll");gl.eglGetProcAddress=gl.eglSymbol<Probe::eglGetProcAddressT>("eglGetProcAddress");
#define LOAD_GL(ret,name,args) gl.name=gl.glSymbol<Probe::name##T>(#name);
  GL_APIS(LOAD_GL)
#undef LOAD_GL
  runtime.AddImport(draw_marker,recomp::MakeBridge<U(I,I)>([&](I w,I h){return Draw(gl,w,h);}));
  runtime.AddImport(resize_marker,recomp::MakeBridge<U(I,I)>([&](I w,I h){windows.ResizeClient(window,w,h);auto geometry=windows.Describe(token);Check(geometry.client_width==w&&geometry.client_height==h,"physical UI client resize is exact");++resizes;return U(1);}));
  elf_image image{};Check(!elf_load(EGL_SCALING_LIBRARY,0x5a000000,Resolve,&image),"actual NDK geometry/EGL caller loads");runtime.AddTraces(kTraces,std::size(kTraces));
  alignas(16)uint8_t stack[131072]{};uint64_t output[96]{};State state{};state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=surface;state.gpr.x2.qword=reinterpret_cast<addr_t>(output);state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));state.gpr.x30.qword=0xfeedffff;
  runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"egl_scaling_guest")));
  Check(state.gpr.x0.qword==EGL_SCALING_RESULTS,"complete NDK scaling sequence");for(size_t i=0;i<state.gpr.x0.qword;++i){if(output[i]!=1)std::fprintf(stderr,"NDK scaling result%zu failed\n",i);Check(output[i]==1,"actual NDK scaling result");}
  Check(draws==4&&resizes==2,"four real draws and two physical resizes reached");Check(!windows.Describe(token).fixed_size,"default buffer mode restored only after retiring fixed surface");
  Check(state.gpr.sp.qword==reinterpret_cast<addr_t>(stack+sizeof(stack))&&java.PendingException().empty(),"guest ABI/JNI state preserved");
  egl.ReleaseCurrentThread();windows.Release(token);windows.Close(window);java.DeleteLocalReference(surface);window.reset();
  std::printf("EGL scaling integration: %u checks; %llu actual NDK assertions, equal-client fixed guarantee, real160x90 resize/readback/present, physical resize independence, reset/recreate and transactional rejection.\n",checks.load(),static_cast<unsigned long long>(state.gpr.x0.qword));
}

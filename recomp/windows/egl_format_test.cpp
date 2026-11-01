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
std::atomic<unsigned> checks{0};EglHost *host;NativeWindows *native;void *hwnd;unsigned draws=0;
constexpr addr_t draw_marker=0x7ff420001000ULL;
void Check(bool value,const char *why){++checks;if(!value){std::fprintf(stderr,"EGL format check: %s\n",why);std::abort();}}
void *Resolve(const char *name){const std::string text=name;if(text=="host_egl_format_draw")return reinterpret_cast<void*>(draw_marker);
  if(text.find("ANativeWindow_")==0)return reinterpret_cast<void*>(native->Marker(text));
  return reinterpret_cast<void*>(host->Marker(text));}
addr_t Invoke(const char *name,std::initializer_list<addr_t> args={}){
  State state{};static constexpr Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};unsigned i=0;
  for(auto value:args)(state.gpr.*registers[i++]).qword=value;
  host->Invoke(name,state);return state.gpr.x0.qword;
}
U Draw(Probe &gl,I format){
  bunker::windows::WindowDpiScope dpi(hwnd);I alpha=-1;gl.glGetIntegerv(0x0d55,&alpha);gl.glCheck("real framebuffer alpha bits");
  Check(alpha==(format==1?8:0),"actual default framebuffer alpha bits match logical RGBA/RGBX format");
  U vao=0;gl.glGenVertexArrays(1,&vao);gl.glBindVertexArray(vao);U program=gl.program({gl.shader(0x8b31,"#version 310 es\nvoid main(){const vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexID],0,1);}"),
    gl.shader(0x8b30,"#version 310 es\nprecision highp float;layout(location=0) out vec4 color;void main(){color=vec4(1,0,0,0);}")});
  gl.glViewport(0,0,640,360);gl.glClearColor(0,0,0,0);gl.glClear(0x4000);gl.glUseProgram(program);gl.glDrawArrays(4,0,3);gl.glFinish();
  std::array<uint8_t,256> pixels{};gl.glPixelStorei(0x0d05,1);gl.glReadPixels(0,0,8,8,0x1908,0x1401,pixels.data());gl.glCheck("real RGBA/RGBX draw/readback");
  const uint8_t expected[]={255,0,0,uint8_t(format==1?0:255)};bool match=true;for(size_t i=0;i<pixels.size();++i)match&=pixels[i]==expected[i%4];
  if(!match)std::fprintf(stderr,"format%d first pixel %u,%u,%u,%u expected %u,%u,%u,%u\n",format,pixels[0],pixels[1],pixels[2],pixels[3],expected[0],expected[1],expected[2],expected[3]);
  gl.glDeleteVertexArrays(1,&vao);gl.glDeleteProgram(program);++draws;return match;
}
}
int main(){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(60));std::fputs("EGL format watchdog\n",stderr);std::_Exit(95);}).detach();
  bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);native=&windows;recomp::Runtime runtime;windows.Install(runtime);
  auto egl=std::make_unique<EglHost>(windows,EGL_HOST_DLL_DIRECTORY);host=egl.get();host->Install(runtime);
  auto window=windows.Create(640,360,u"Bunker EGL formats",false);auto surface=windows.NewSurface(window);auto token=windows.FromSurface(surface);hwnd=windows.NativeHandle(token);
  Check(windows.SetBuffersGeometry(token,0,0,2)==-38&&windows.Describe(token).format==1,"format change before native EGL initialization is explicit unsupported");
  Probe gl;gl.egl=GetModuleHandleW(L"libEGL.dll");gl.gles=GetModuleHandleW(L"libGLESv2.dll");gl.eglGetProcAddress=gl.eglSymbol<Probe::eglGetProcAddressT>("eglGetProcAddress");
#define LOAD_GL(ret,name,args) gl.name=gl.glSymbol<Probe::name##T>(#name);
  GL_APIS(LOAD_GL)
#undef LOAD_GL
  runtime.AddImport(draw_marker,recomp::MakeBridge<U(I)>([&](I format){return Draw(gl,format);}));
  elf_image image{};Check(!elf_load(EGL_HOST_LIBRARY,0x5b000000,Resolve,&image),"actual NDK EGL format caller loads");runtime.AddTraces(kTraces,std::size(kTraces));
  for(I format:{1,2}){alignas(16)uint8_t stack[65536]{};uint64_t output[64]{};State state{};
    state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=surface;state.gpr.x2.qword=format;state.gpr.x3.qword=reinterpret_cast<addr_t>(output);state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));state.gpr.x30.qword=0xfeedffff;
    runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"egl_format_guest")));
    Check(state.gpr.x0.qword==25,"complete25-result NDK format sequence");for(size_t i=0;i<state.gpr.x0.qword;++i){if(output[i]!=1)std::fprintf(stderr,"NDK format%d result%zu failed\n",format,i);Check(output[i]==1,"actual NDK format operation");}
  }
  Check(draws==4&&windows.Describe(token).format==1,"four real format draws and default restore");
  const auto display=Invoke("eglGetDisplay",{0});I untouched=-1;
  Check(!Invoke("eglGetConfigAttrib",{display,0,0x302e,reinterpret_cast<addr_t>(&untouched)}),"pending EGL config error established");
  Check(Invoke("eglInitialize",{display,0,0}),"real window configs initialized for race gate");
  Check(Invoke("eglGetError")==0x3005&&Invoke("eglGetError")==0x3000,"internal window-format discovery preserves pending guest EGL error");
  auto Config=[&](I format){const I attributes[]={0x302e,format,0x3033,4,0x3040,0x40,0x3038};addr_t config=0;I count=0;
    Check(Invoke("eglChooseConfig",{display,reinterpret_cast<addr_t>(attributes),reinterpret_cast<addr_t>(&config),1,reinterpret_cast<addr_t>(&count)})&&count==1,"real presentable logical-format config");return config;};
  const auto rgba=Config(1),rgbx=Config(2);
  const I rgb565_attributes[]={0x302e,4,0x3033,4,0x3038};I rgb565_count=-1;
  Check(Invoke("eglChooseConfig",{display,reinterpret_cast<addr_t>(rgb565_attributes),0,0,reinterpret_cast<addr_t>(&rgb565_count)}),"real RGB565 window-config availability queried");
  Check(windows.SetBuffersGeometry(token,0,0,4)==-38,"unvalidated RGB565 format remains unsupported");
  std::atomic<bool> stop{false},started{false};std::atomic<unsigned> geometry_calls{0};
  std::thread mutation([&]{started=true;while(!stop.load()){const I format=(geometry_calls.load()&1)?1:2;const auto error=windows.SetBuffersGeometry(token,0,0,format);
    Check(error==0||error==-16,"concurrent format mutation either commits or explicitly rejects incompatible live surface");++geometry_calls;std::this_thread::yield();}});
  while(!started.load())std::this_thread::yield();
  unsigned created=0,rejected=0;
  for(unsigned i=0;i<32;++i){const auto format=windows.Describe(token).format;const auto config=format==1?rgba:rgbx;
    const auto created_surface=Invoke("eglCreateWindowSurface",{display,config,token,0});
    if(created_surface){++created;Check(windows.Describe(token).format==format,"concurrent creation cannot publish an incompatible window descriptor");Check(Invoke("eglDestroySurface",{display,created_surface}),"race surface retired");}
    else{++rejected;Check(Invoke("eglGetError")==0x3009,"precommit race fails conservatively with EGL_BAD_MATCH");}
  }
  stop=true;mutation.join();Check(created+rejected==32&&geometry_calls>0,"all racing creates resolve explicitly and geometry callbacks exercised");
  Check(Invoke("eglGetError")==0x3000,"format race preserves clean EGL error flag");
  std::atomic<bool> retire_stop{false};std::atomic<unsigned> retire_calls{0};
  std::thread retirement([&]{for(unsigned attempt=0;attempt<256&&!retire_stop.load();++attempt){
    const auto current=windows.Describe(token).format;const auto error=windows.SetBuffersGeometry(token,0,0,current==1?2:1);
    Check(error==0||error==-38||error==-19,"copied geometry callback remains safe across EGL owner destruction");++retire_calls;std::this_thread::yield();}});
  while(!retire_calls.load())std::this_thread::yield();
  egl.reset();host=nullptr;retire_stop=true;retirement.join();
  const auto before=windows.Describe(token).format;
  Check(windows.SetBuffersGeometry(token,0,0,before==1?2:1)==-38&&windows.Describe(token).format==before,"EGL destruction clears geometry callback without committing format");
  windows.Release(token);windows.Close(window);java.DeleteLocalReference(surface);window.reset();
  std::printf("EGL format backend: %u checks; RGBA8888/RGBX8888 real NDK configs, alpha/readback/swap and deferred incompatible-surface gates; %u real race creations/%u conservative rejections, %u geometry calls; RGB565 native window-config count%d remains unsupported; fixed buffers unsupported.\n",checks.load(),created,rejected,geometry_calls.load(),rgb565_count);
}

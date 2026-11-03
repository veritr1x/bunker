#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl32.h>
#include "gl_host.h"
#include "gl_query_expected.h"
#include "egl_host.h"
#include "../whole/bridge.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <thread>
using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};EglHost *egl_provider;
thread_local const std::function<void(State&)> *body=nullptr;
Memory *Entry(State &state,addr_t,Memory *memory){(*body)(state);state.gpr.pc.qword=state.gpr.x30.qword;return memory;}
void Check(bool condition,const char *why){++checks;if(!condition){std::fprintf(stderr,"GL query check: %s\n",why);std::abort();}}
template<class F>F Symbol(HMODULE module,const char *name){auto address=GetProcAddress(module,name);Check(address!=nullptr,"native query symbol exists");F f;std::memcpy(&f,&address,sizeof(f));return f;}
template<class Host>addr_t Invoke(Host &host,const char *name,std::initializer_list<addr_t> args={}){
  State state{};static constexpr Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};unsigned n=0;
  for(auto arg:args)(state.gpr.*registers[n++]).qword=arg;
  host.Invoke(name,state);return state.gpr.x0.qword;
}
void *Resolve(const char *name){return reinterpret_cast<void*>(egl_provider->Marker(name));}
std::string Text(addr_t pointer){Check(pointer!=0,"guest driver string pointer");std::string value;for(size_t n=0;n<65536;++n){char c;recomp::ReadGuestMemory(&c,pointer+n,1);if(!c)return value;value+=c;}throw std::runtime_error("driver string exceeds64KiB");}
}
int main(){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(60));std::fputs("GL query watchdog\n",stderr);std::_Exit(95);}).detach();
  bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;
  EglHost egl(windows,GL_HOST_DLL_DIRECTORY);egl_provider=&egl;egl.Install(runtime);
  GlHost gl(egl,GL_HOST_DLL_DIRECTORY);gl.Install(runtime);egl.SetProcedureResolver([&](const std::string &name){return gl.Marker(name);});
  auto display=Invoke(egl,"eglGetDisplay",{0});Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"actual Vulkan display initialization");
  const int attrs[]={0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3033,1,0x3040,0x40,0x3038};addr_t config=0;int n=0;
  Check(Invoke(egl,"eglChooseConfig",{display,reinterpret_cast<addr_t>(attrs),reinterpret_cast<addr_t>(&config),1,reinterpret_cast<addr_t>(&n)})&&n==1,"real GLES3 pbuffer config");
  const int context_attrs[]={0x3098,3,0x30fb,1,0x3038},surface_attrs[]={0x3057,8,0x3056,8,0x3038};
  auto context=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(context_attrs)});
  auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,reinterpret_cast<addr_t>(surface_attrs)});
  Check(context&&surface&&Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"real current GLES3.1+ context");
  auto module=GetModuleHandleW(L"libGLESv2.dll");
  auto getString=Symbol<PFNGLGETSTRINGPROC>(module,"glGetString");auto getStringi=Symbol<PFNGLGETSTRINGIPROC>(module,"glGetStringi");
  auto getInteger=Symbol<PFNGLGETINTEGERVPROC>(module,"glGetIntegerv");auto getFloat=Symbol<PFNGLGETFLOATVPROC>(module,"glGetFloatv");
  auto getBoolean=Symbol<PFNGLGETBOOLEANVPROC>(module,"glGetBooleanv");auto getError=Symbol<PFNGLGETERRORPROC>(module,"glGetError");
  Symbol<PFNGLVIEWPORTPROC>(module,"glViewport")(3,5,17,19);Symbol<PFNGLSCISSORPROC>(module,"glScissor")(7,9,11,13);
  Symbol<PFNGLCLEARCOLORPROC>(module,"glClearColor")(0.125f,0.5f,0.75f,1.0f);Symbol<PFNGLCOLORMASKPROC>(module,"glColorMask")(0,1,0,1);
  Check(getError()==GL_NO_ERROR,"nondefault vector state initialized");
  std::printf("GL driver: %s; %s\n",getString(GL_VERSION),getString(GL_RENDERER));
  const auto &catalog=GlHost::Queries();
  Check(catalog.size()==std::size(kOldQueries)+4,"exactly four scalar query rows appended");
  for(size_t i=0;i<std::size(kOldQueries);++i)Check(catalog[i].name==kOldQueries[i].name&&catalog[i].count==kOldQueries[i].count&&catalog[i].count_query==kOldQueries[i].count_query,"old query prefix and widths preserved");
  for(GLenum name:{0x90d9u,0x90d8u,0x90d7u,0x84ffu}){
    auto found=std::find_if(catalog.begin(),catalog.end(),[&](const auto&q){return q.name==name;});
    Check(found!=catalog.end()&&found->count==1&&!found->count_query&&std::count_if(catalog.begin(),catalog.end(),[&](const auto&q){return q.name==name;})==1,"new query is exactly one scalar row");
  }
std::vector<uint32_t> names;std::vector<size_t> counts;size_t largest=0;
  constexpr size_t stride=4096;std::vector<uint8_t> storage(catalog.size()*3*stride,0xa5),expected(storage.size(),0xa5);
  for(size_t i=0;i<catalog.size();++i){const auto &query=catalog[i];names.push_back(query.name);const auto count=gl.QueryComponents(query.name);counts.push_back(count);largest=std::max(largest,count);Check(count*4+16<stride,"query fits bounded guarded fixture");
    std::vector<GLint> integers(std::max<size_t>(1,count));std::vector<GLfloat> floats(std::max<size_t>(1,count));std::vector<GLboolean> booleans(std::max<size_t>(1,count));
    getInteger(query.name,integers.data());Check(getError()==GL_NO_ERROR,"native integer query catalog is valid");getFloat(query.name,floats.data());Check(getError()==GL_NO_ERROR,"native float query catalog is valid");getBoolean(query.name,booleans.data());Check(getError()==GL_NO_ERROR,"native boolean query catalog is valid");
    if(count){std::memcpy(expected.data()+(i*3+0)*stride+16,integers.data(),count*4);std::memcpy(expected.data()+(i*3+1)*stride+16,floats.data(),count*4);std::memcpy(expected.data()+(i*3+2)*stride+16,booleans.data(),count);}
  }
  elf_image image{};Check(!elf_load(GL_HOST_LIBRARY,0x5c000000,Resolve,&image),"NDK typed GL resolver caller loads");runtime.AddTraces(kTraces,std::size(kTraces));
  std::vector<uint64_t> results(16+catalog.size()*3);alignas(16)uint8_t stack[65536]{};State state{};
  state.gpr.x0.qword=reinterpret_cast<addr_t>(names.data());state.gpr.x1.qword=names.size();state.gpr.x2.qword=stride;state.gpr.x3.qword=reinterpret_cast<addr_t>(storage.data());state.gpr.x4.qword=reinterpret_cast<addr_t>(results.data());state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));state.gpr.x30.qword=0xfeedffff;
  runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"gl_query_guest")));
  Check(state.gpr.x0.qword==catalog.size()&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack+sizeof(stack)),"NDK query count and balanced stack");
  Check(storage==expected,"all integer/float/one-byte boolean results and full prefix/tail canaries match native driver exactly");
  for(size_t i=0;i<catalog.size()*3;++i)Check(results[16+i]==GL_NO_ERROR,"NDK catalog query error-free");
  const GLenum string_names[]={GL_VENDOR,GL_RENDERER,GL_VERSION,GL_SHADING_LANGUAGE_VERSION,GL_EXTENSIONS};
  for(size_t i=0;i<std::size(string_names);++i){const auto *native=getString(string_names[i]);Check(Text(results[i])==reinterpret_cast<const char*>(native),"driver string copied without rewriting");Check(results[i]!=reinterpret_cast<addr_t>(native),"guest string is a tracked provider copy");}
  Check(Text(results[5])==reinterpret_cast<const char*>(getStringi(GL_EXTENSIONS,0)),"real indexed extension string");
  Check(results[6]==0&&!results[7]&&results[8]&&results[9]==GL_INVALID_VALUE&&!results[10],"indexed string error survives a later successful query and clears once");
  Check(!results[11]&&results[12]&&results[13]==GL_INVALID_ENUM&&!results[14],"native string enum error preserved");
  uint8_t untouched[32];std::fill(std::begin(untouched),std::end(untouched),0xa5);getString(0xffffffffu);
  bool rejected=false;try{Invoke(gl,"glGetIntegerv",{0xffffffffu,reinterpret_cast<addr_t>(untouched)});}catch(const std::runtime_error &){rejected=true;}
  Check(rejected&&getError()==GL_INVALID_ENUM&&std::all_of(std::begin(untouched),std::end(untouched),[](auto v){return v==0xa5;}),"unknown query width neither touches memory nor consumes native GL error");
  rejected=false;try{gl.Marker("glMapBufferRange");}catch(const std::runtime_error &){rejected=true;}Check(rejected,"unimplemented mapped-memory signature explicitly rejected");
  getString(0xffffffffu);std::vector<GLint> compressed(gl.QueryComponents(GL_COMPRESSED_TEXTURE_FORMATS));
  Invoke(gl,"glGetIntegerv",{GL_COMPRESSED_TEXTURE_FORMATS,reinterpret_cast<addr_t>(compressed.data())});
  Check(Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==GL_NO_ERROR,"internal driver-sized-array query preserves earlier GL error");
  // A second real context runs the writer concurrently; no context is migrated
  // while current on another thread and no guest-memory lock spans EGL calls.
  auto worker_context=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(context_attrs)});
  auto worker_surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,reinterpret_cast<addr_t>(surface_attrs)});
  struct Guard {uint32_t before;GLint value;uint32_t after;} output{0x12345678,0,0x87654321};getInteger(GL_MAX_TEXTURE_SIZE,&output.value);
  recomp::Runtime reserve_runtime;const recomp::Trace trace{0x6000,Entry};reserve_runtime.AddTraces(&trace,1);
  std::function<void(State&)> reserve=[&](State &s){const auto old=__remill_aarch64_load_exclusive(s,reinterpret_cast<addr_t>(&output.value),4,0);
    std::thread writer([&]{Check(Invoke(egl,"eglMakeCurrent",{display,worker_surface,worker_surface,worker_context}),"worker owns distinct real GLES context");Invoke(gl,"glGetIntegerv",{GL_MAX_TEXTURE_SIZE,reinterpret_cast<addr_t>(&output.value)});Check(Invoke(gl,"glGetError")==0,"worker query succeeds");egl.ReleaseCurrentThread();});writer.join();
    Check(__remill_aarch64_store_exclusive(s,reinterpret_cast<addr_t>(&output.value),old,4,0)==1,"same-value GL query publication invalidates guest reservation");};
  body=&reserve;State reserved{};reserved.gpr.x30.qword=0xfeedffff;reserve_runtime.Run(reserved,0x6000);body=nullptr;
  Check(output.before==0x12345678&&output.after==0x87654321,"tracked GL scalar preserves adjacent canaries");
  Check(Invoke(egl,"eglDestroySurface",{display,worker_surface})&&Invoke(egl,"eglDestroyContext",{display,worker_context}),"worker resources retire after thread unbind");
  Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglTerminate",{display}),"main GLES resources retire");
  egl.ReleaseCurrentThread();egl.SetProcedureResolver({});
  std::printf("GL query host: %u checks, %zu enum widths x3 typed getters via NDK resolver, largest array%zu, exact results/canaries/error flags/tracked writes; six GL signatures.\n",checks.load(),catalog.size(),largest);
}

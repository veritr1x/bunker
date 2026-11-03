#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl31.h>
#include <EGL/egl.h>
#include "gles_service_module.h"
#include "egl_host.h"
#include "module_registry_elf.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <thread>
#include <chrono>
#include <cstdlib>
using namespace bunker::windows;
namespace {
unsigned checks=0;ModuleRegistry*registry;EglHost*egl_provider;
void Check(bool b,const char*why){if(!b)throw std::runtime_error(why);++checks;}
template<class F>F Native(HMODULE m,const char*n){auto a=GetProcAddress(m,n);Check(a!=nullptr,"real native GLES function");F f;std::memcpy(&f,&a,sizeof(f));return f;}
template<class H>addr_t Invoke(H&h,const char*n,std::initializer_list<addr_t>args={}){State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};unsigned i=0;for(auto v:args)(s.gpr.*r[i++]).qword=v;h.Invoke(n,s);return s.gpr.x0.qword;}
void*Resolve(const char*n){if(!std::strcmp(n,"eglGetProcAddress"))return reinterpret_cast<void*>(egl_provider->Marker(n));return reinterpret_cast<void*>(registry->Marker(n));}
std::string Text(addr_t p){Check(p!=0,"nonnull string");std::string v;for(unsigned n=0;n<65536;++n){char c;recomp::ReadGuestMemory(&c,p+n,1);if(!c)return v;v+=c;}throw std::runtime_error("bounded string exceeded");}
template<class F>void Reject(F f){bool rejected=false;try{f();}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"invalid typed service rejected");}
}
int main(){try{
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
 std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(60));std::fputs("GLES module watchdog\n",stderr);std::_Exit(95);}).detach();
 bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;EglHost egl(windows,GL_MODULE_DLL_DIRECTORY);egl.Install(runtime);GlHost gl(egl,GL_MODULE_DLL_DIRECTORY);gl.Install(runtime);egl_provider=&egl;egl.SetProcedureResolver([&](const std::string&n){return FindTypedGlesProcedure(gl,n);});
 auto display=Invoke(egl,"eglGetDisplay",{0});Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"actual ANGLE display");
 const int attrs[]={0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3033,1,0x3040,0x40,0x3038};addr_t config=0;int count=0;
 Check(Invoke(egl,"eglChooseConfig",{display,reinterpret_cast<addr_t>(attrs),reinterpret_cast<addr_t>(&config),1,reinterpret_cast<addr_t>(&count)})&&count==1,"GLES3 pbuffer configuration");
 const int ctxattrs[]={0x3098,3,0x30fb,1,0x3038},surfattrs[]={0x3057,8,0x3056,8,0x3038};auto context=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(ctxattrs)});auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,reinterpret_cast<addr_t>(surfattrs)});Check(context&&surface&&Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"actual current GLES3.1 context");
 auto native=GetModuleHandleW(L"libGLESv2.dll");auto getString=Native<PFNGLGETSTRINGPROC>(native,"glGetString");auto getInteger=Native<PFNGLGETINTEGERVPROC>(native,"glGetIntegerv");auto getIndexed=Native<PFNGLGETSTRINGIPROC>(native,"glGetStringi");auto getError=Native<PFNGLGETERRORPROC>(native,"glGetError");GLint expected=0,extensions=0;getInteger(GL_MAX_TEXTURE_SIZE,&expected);getInteger(GL_NUM_EXTENSIONS,&extensions);Check(expected>0&&extensions>0&&getError()==GL_NO_ERROR,"native query oracle");auto version=std::string(reinterpret_cast<const char*>(getString(GL_VERSION)));auto extension=std::string(reinterpret_cast<const char*>(getIndexed(GL_EXTENSIONS,0)));Check(getError()==GL_NO_ERROR,"native string oracle");
 unsigned lifecycle=0;ModuleRegistry modules([&](addr_t){++lifecycle;});registry=&modules;modules.Install(runtime);auto service=MakeGlesServiceModule(gl);Check(service.name=="libGLESv2.so"&&service.aliases.empty()&&service.kind==Module::Kind::TypedService&&!service.address_image&&service.initializers.empty()&&service.finalizers.empty(),"explicit service has no false ELF/lifecycle metadata");Check(service.exports.size()==63&&service.exports.size()==GlHost::Commands().size(),"exact existing command catalog");for(const auto&name:GlHost::Commands())Check(service.exports.at(name)==gl.Marker(name),"every export is existing typed marker");
 unsigned invalid=0;auto Bad=[&](auto edit){auto bad=service;bad.name="invalid"+std::to_string(++invalid);edit(bad);Reject([&]{modules.Add(std::move(bad));});};
 Bad([](Module&m){m.initializers={0x1000};});Bad([](Module&m){m.finalizers={0x1000};});Bad([](Module&m){m.export_policy=Module::ExportPolicy::BionicRawSymbols;});Bad([](Module&m){m.exports.begin()->second=0;});Bad([](Module&m){m.exports.begin()->second|=1;});Bad([](Module&m){m.kind=static_cast<Module::Kind>(99);});
 std::ifstream file(GL_MODULE_IMAGE,std::ios::binary);Check(bool(file),"real NDK caller file");std::vector<uint8_t>bytes{std::istreambuf_iterator<char>(file),{}};
 auto metadata=DescribeModuleElf(bytes.data(),bytes.size(),0x5c000000,"/guest/loader-caller.so");Bad([&](Module&m){m.address_image=metadata;});modules.Add(service);
 elf_image image{};Check(!elf_load(GL_MODULE_IMAGE,0x5c000000,Resolve,&image),"NDK dlopen/dlsym caller image");runtime.AddTraces(kTraces,std::size(kTraces));auto address=reinterpret_cast<addr_t>(elf_symbol(&image,"loader_gl_queries"));Check(address!=0,"actual query caller export");
 Module caller;caller.name="loader-caller.so";caller.exports={{"loader_gl_queries",address}};caller.address_image=std::move(metadata);modules.Add(std::move(caller));auto caller_handle=modules.Open("loader-caller.so",2);Check(caller_handle!=0,"actual ELF metadata registered separately");
 auto Run=[&](const char*name,std::initializer_list<addr_t>args={}){alignas(16)std::array<uint8_t,65536>stack{};State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};unsigned i=0;for(auto v:args)(s.gpr.*r[i++]).qword=v;s.gpr.x19.qword=0x123456789abcdef0ULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));Check(runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)),token)==token&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x30.qword==0xfeedffff&&s.gpr.x19.qword==0x123456789abcdef0ULL&&s.gpr.pc.qword==0xfeedffff,"actual NDK caller SP/return/callee register/token");return s.gpr.x0.qword;};

 // Lookup itself must not consume a preexisting EGL error or expose native entrypoints.
 egl.SetProcedureResolver({});GLint untouched_surface=0x12345678;
 Check(!Invoke(egl,"eglQuerySurface",{display,0x12345678,EGL_WIDTH,reinterpret_cast<addr_t>(&untouched_surface)})&&untouched_surface==0x12345678,"seed existing EGL_BAD_SURFACE without output write");
 bool default_rejected=false;try{Invoke(egl,"eglGetProcAddress",{reinterpret_cast<addr_t>("glDebugMessageControl")});}catch(const std::runtime_error&e){default_rejected=std::strstr(e.what(),"Unsupported typed graphics resolver signature")!=nullptr;}Check(default_rejected,"unconfigured EGL resolver retains throwing fence");
 egl.SetProcedureResolver([&](const std::string&n){return FindTypedGlesProcedure(gl,n);});
 auto native_egl_error=Native<PFNEGLGETERRORPROC>(GetModuleHandleW(L"libEGL.dll"),"eglGetError");std::array<uint64_t,8>procedures;procedures.fill(UINT64_C(0xa5a5a5a5a5a5a5a5));
 Check(Run("loader_egl_procedures",{reinterpret_cast<addr_t>(procedures.data())})==0,"actual NDK EGL known and optional lookups");
 Check(procedures[0]==gl.Marker("glGetString")&&procedures[1]==egl.Marker("eglGetError")&&!procedures[2]&&!procedures[3],"known GL/EGL typed markers and unsupported debug NULL");
 Check(procedures[0]!=reinterpret_cast<addr_t>(getString)&&procedures[1]!=reinterpret_cast<addr_t>(native_egl_error),"procedure lookup never returns native pointers");
 Check(Text(procedures[4])==version&&procedures[4]!=reinterpret_cast<addr_t>(getString(GL_VERSION)),"returned GL procedure is invoked and returns tracked exact text");
 Check(procedures[5]==EGL_BAD_SURFACE&&procedures[6]==EGL_SUCCESS&&procedures[7]==UINT64_C(0xa5a5a5a5a5a5a5a5),"lookups preserve pending EGL error until known error procedure consumes once; guard intact");
 auto Query=[&](){std::array<uint64_t,8>out;out.fill(UINT64_C(0xa5a5a5a5a5a5a5a5));struct{uint32_t before;GLint value;uint32_t after;}guard{0x12345678,-1,0x87654321};Check(Run("loader_gl_queries",{reinterpret_cast<addr_t>("libGLESv2.so"),reinterpret_cast<addr_t>(out.data()),reinterpret_cast<addr_t>(&guard.value)})==0,"NDK loader to three typed GL signatures");Check(out[0]&&out[1]==gl.Marker("glGetString")&&out[2]==gl.Marker("glGetIntegerv")&&out[3]==gl.Marker("glGetStringi"),"dlsym returns markers not native pointers");Check(out[1]!=reinterpret_cast<addr_t>(getString)&&out[2]!=reinterpret_cast<addr_t>(getInteger)&&out[3]!=reinterpret_cast<addr_t>(getIndexed),"no native function pointer exposed");Check(Text(out[4])==version&&Text(out[5])==extension&&out[4]!=reinterpret_cast<addr_t>(getString(GL_VERSION))&&out[5]!=reinterpret_cast<addr_t>(getIndexed(GL_EXTENSIONS,0)),"native driver text exact provider-owned copies");Check(guard.value==expected&&guard.before==0x12345678&&guard.after==0x87654321&&out[6]==UINT64_C(0xa5a5a5a5a5a5a5a5)&&out[7]==out[6]&&getError()==GL_NO_ERROR,"real tracked GLint query and complete guards");return out[0];};
 auto handle=Query();Check(modules.ReferenceCount("libGLESv2.so")==1,"one service open");Check(Run("loader_open",{reinterpret_cast<addr_t>("libGLESv2.so"),2})==handle&&modules.ReferenceCount("libGLESv2.so")==2,"repeat NDK open retains handle");
 AndroidDlInfo info{};Check(Run("loader_address",{address,reinterpret_cast<addr_t>(&info)})==1&&info.base==0x5c000000&&std::strcmp(reinterpret_cast<const char*>(info.filename),"/guest/loader-caller.so")==0&&std::strcmp(reinterpret_cast<const char*>(info.symbol_name),"loader_gl_queries")==0&&info.symbol_address==address,"real ELF dladdr works with GLES service open");
 AndroidDlInfo untouched{0x1111,0x2222,0x3333,0x4444},copy=untouched;Check(Run("loader_address",{gl.Marker("glGetString"),reinterpret_cast<addr_t>(&untouched)})==0&&std::memcmp(&untouched,&copy,sizeof(copy))==0,"provider marker has no false ELF ownership");
 Module opaque;opaque.name="opaque.so";modules.Add(std::move(opaque));auto opaque_handle=modules.Open("opaque.so",1);bool incomplete=false;try{modules.Address(address,&info);}catch(const std::runtime_error&e){incomplete=std::strstr(e.what(),"incomplete")!=nullptr;}Check(incomplete&&modules.Close(opaque_handle)==0,"ordinary incomplete ELF guard remains intact");
 Check(!Run("loader_symbol",{handle,reinterpret_cast<addr_t>("notARealGLSymbol")}),"unimplemented symbol absent");Check(Run("loader_symbol",{handle,reinterpret_cast<addr_t>("glGetString")})==gl.Marker("glGetString"),"successful symbol remains exact typed bridge");auto error=Run("loader_error");Check(error&&Text(error).find("notARealGLSymbol")!=std::string::npos&&!Run("loader_error"),"pending dlerror survives success and clears once");
 Check(!Run("loader_close",{handle})&&modules.ReferenceCount("libGLESv2.so")==1&&Run("loader_symbol",{handle,reinterpret_cast<addr_t>("glGetStringi")})==gl.Marker("glGetStringi"),"nonfinal close preserves service");Check(!Run("loader_close",{handle})&&!modules.ReferenceCount("libGLESv2.so"),"final close retires registry handle");Check(!Run("loader_symbol",{handle,reinterpret_cast<addr_t>("glGetString")})&&Run("loader_error")&&!Run("loader_error"),"stale handle rejected");auto reopened=Query();Check(reopened!=handle&&modules.ReferenceCount("libGLESv2.so")==1&&!Run("loader_close",{reopened})&&lifecycle==0,"stateless reopen new handle without ELF lifecycle");Check(modules.Close(caller_handle)==0,"caller metadata retires separately");
 Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglTerminate",{display}),"offscreen resources retired");egl.ReleaseCurrentThread();egl.SetProcedureResolver({});
 std::printf("GLES-MODULE-PASS checks=%u exports=63 typed_signatures=3 real_ANGLE=1 no_false_ELF=1 nullable_proc=1\n",checks);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"GLES module test: %s\n",e.what());return 1;}}

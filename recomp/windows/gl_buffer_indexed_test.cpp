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
#include "gl_buffer_indexed_old_commands.h"
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <thread>
using namespace bunker::windows;
namespace {
unsigned checks=0,calls=0,records=0;GlHost *graphics;EglHost *egl_provider;
void Check(bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;}
addr_t Address(const void *p){return reinterpret_cast<addr_t>(p);}
template<class F>F Native(HMODULE module,const char *name){auto p=GetProcAddress(module,name);Check(p!=nullptr,"actual native symbol");F f;static_assert(sizeof(f)==sizeof(p));std::memcpy(&f,&p,sizeof(f));return f;}
void *Resolve(const char *name){return reinterpret_cast<void*>(!std::strcmp(name,"eglGetProcAddress")?egl_provider->Marker(name):graphics->Marker(name));}
template<class H>addr_t Invoke(H &host,const char *name,std::initializer_list<addr_t> args={}){State state{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};size_t i=0;for(auto value:args)(state.gpr.*r[i++]).qword=value;host.Invoke(name,state);return state.gpr.x0.qword;}
struct Category{GLenum target,binding,start,size,limit;const char *name;};
struct Binding{GLint general=-1,indexed=-1;GLint64 start=-1,size=-1,store=-1;bool store_queried=false;};
bool Equal(const Binding &a,const Binding &b){return a.general==b.general&&a.indexed==b.indexed&&a.start==b.start&&a.size==b.size&&a.store==b.store&&a.store_queried==b.store_queried;}
}
int main(){try{
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
 std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(90));std::fputs("indexed buffer component watchdog\n",stderr);std::_Exit(95);}).detach();
 bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;
 EglHost egl(windows,GL_BUFFER_INDEXED_DLL_DIRECTORY);egl_provider=&egl;egl.Install(runtime);
 GlHost gl(egl,GL_BUFFER_INDEXED_DLL_DIRECTORY);graphics=&gl;gl.Install(runtime);egl.SetProcedureResolver([&](const std::string &name){return FindTypedGlesProcedure(gl,name);});
 const auto display=Invoke(egl,"eglGetDisplay");Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"real ANGLE display");
 const GLint attrs[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,EGL_NONE};addr_t config=0;GLint configs=0;
 Check(Invoke(egl,"eglChooseConfig",{display,Address(attrs),Address(&config),1,Address(&configs)})&&configs==1,"actual GLES3 config");
 const GLint ca[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_CONTEXT_MINOR_VERSION,1,EGL_NONE},sa[]={EGL_WIDTH,8,EGL_HEIGHT,8,EGL_NONE};
 const auto context=Invoke(egl,"eglCreateContext",{display,config,0,Address(ca)}),surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,Address(sa)});Check(context&&surface,"owned GLES3.1 context and surface");
 auto Bind=[&]{Check(Invoke(egl,"eglMakeCurrent",{display,surface,surface,context})!=0,"actual owned current context");};Bind();
 auto driver=GetModuleHandleW(L"libGLESv2.dll");Check(driver!=nullptr,"pinned shared ANGLE module");
 auto bind=Native<PFNGLBINDBUFFERBASEPROC>(driver,"glBindBufferBase");auto get=Native<PFNGLGETINTEGERVPROC>(driver,"glGetIntegerv");
 auto geti=Native<PFNGLGETINTEGERI_VPROC>(driver,"glGetIntegeri_v");auto get64=Native<PFNGLGETINTEGER64I_VPROC>(driver,"glGetInteger64i_v");
 auto getstore=Native<PFNGLGETBUFFERPARAMETERI64VPROC>(driver,"glGetBufferParameteri64v");auto native_error=Native<PFNGLGETERRORPROC>(driver,"glGetError");
 auto gen=Native<PFNGLGENBUFFERSPROC>(driver,"glGenBuffers");auto remove=Native<PFNGLDELETEBUFFERSPROC>(driver,"glDeleteBuffers");
 auto ordinary=Native<PFNGLBINDBUFFERPROC>(driver,"glBindBuffer");auto data=Native<PFNGLBUFFERDATAPROC>(driver,"glBufferData");auto is=Native<PFNGLISBUFFERPROC>(driver,"glIsBuffer");
 auto Error=[&]{return GLenum(Invoke(gl,"glGetError"));};
 Check(std::size(kOldBufferIndexedCommands)==116&&GlHost::Commands().size()==121,"exact old116 plus sampler4 and indexed-buffer1");
 for(size_t i=0;i<116;++i)Check(GlHost::Commands()[i]==kOldBufferIndexedCommands[i]&&gl.Marker(kOldBufferIndexedCommands[i])==gl.Marker(kOldBufferIndexedCommands[0])+i*8,"every old116 command and marker preserved");
 const char *samplers[]={"glGenSamplers","glDeleteSamplers","glBindSampler","glSamplerParameteri"};
 for(size_t i=0;i<4;++i)Check(GlHost::Commands()[116+i]==samplers[i]&&gl.Marker(samplers[i])==gl.Marker(kOldBufferIndexedCommands[0])+(116+i)*8,"sampler append order is exact");
 const auto marker=gl.Marker("glBindBufferBase");Check(GlHost::Commands()[120]=="glBindBufferBase"&&marker==gl.Marker(kOldBufferIndexedCommands[0])+120*8,"single new command appended last");
 const auto service=MakeGlesServiceModule(gl);Check(service.kind==Module::Kind::TypedService&&!service.address_image&&service.exports.size()==121&&service.exports.at("glBindBufferBase")==marker&&FindTypedGlesProcedure(gl,"glBindBufferBase")==marker&&marker!=reinterpret_cast<addr_t>(GetProcAddress(driver,"glBindBufferBase")),"typed resolver/service marker, no native pointer or fabricated ELF owner");
 elf_image image{};Check(!elf_load(GL_BUFFER_INDEXED_IMAGE,0x5e000000,Resolve,&image),"actual NDK direct/procedure/function-pointer callers load");runtime.AddTraces(kTraces,std::size(kTraces));
 auto Run=[&](const char *name,std::initializer_list<addr_t> args={}){
  alignas(16)std::array<uint8_t,65536> stack{};State state{};const auto sp=Address(stack.data()+stack.size());state.gpr.sp.qword=sp;state.gpr.x30.qword=0xfeedffff;state.gpr.x19.qword=UINT64_C(0x123456789abcdef0);
  Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t i=0;for(auto value:args)(state.gpr.*r[i++]).qword=value;
  auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(entry!=0,"NDK wrapper export");auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));
  Check(runtime.Run(state,entry,token)==token&&state.gpr.sp.qword==sp&&state.gpr.x19.qword==UINT64_C(0x123456789abcdef0)&&state.gpr.x30.qword==0xfeedffff&&state.gpr.pc.qword==0xfeedffff,"NDK callee register/SP/LR/token normal return");++calls;return state.gpr.x0.qword;
 };
 Check(Run("gl_buffer_indexed_resolve")==marker,"actual NDK procedure lookup returns typed marker");
 const Category categories[]={
  {GL_UNIFORM_BUFFER,GL_UNIFORM_BUFFER_BINDING,GL_UNIFORM_BUFFER_START,GL_UNIFORM_BUFFER_SIZE,GL_MAX_UNIFORM_BUFFER_BINDINGS,"uniform"},
  {GL_TRANSFORM_FEEDBACK_BUFFER,GL_TRANSFORM_FEEDBACK_BUFFER_BINDING,GL_TRANSFORM_FEEDBACK_BUFFER_START,GL_TRANSFORM_FEEDBACK_BUFFER_SIZE,GL_MAX_TRANSFORM_FEEDBACK_SEPARATE_ATTRIBS,"transform-feedback"},
  {GL_SHADER_STORAGE_BUFFER,GL_SHADER_STORAGE_BUFFER_BINDING,GL_SHADER_STORAGE_BUFFER_START,GL_SHADER_STORAGE_BUFFER_SIZE,GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS,"shader-storage"},
  {GL_ATOMIC_COUNTER_BUFFER,GL_ATOMIC_COUNTER_BUFFER_BINDING,GL_ATOMIC_COUNTER_BUFFER_START,GL_ATOMIC_COUNTER_BUFFER_SIZE,GL_MAX_ATOMIC_COUNTER_BUFFER_BINDINGS,"atomic-counter"}};
 auto Observe=[&](const Category &c,GLuint index){Binding out;get(c.binding,&out.general);geti(c.binding,index,&out.indexed);get64(c.start,index,&out.start);get64(c.size,index,&out.size);if(out.general){getstore(c.target,GL_BUFFER_SIZE,&out.store);out.store_queried=true;}Check(native_error()==GL_NO_ERROR,"native-only general/indexed binding and64-bit range/store observers");return out;};
 auto Call=[&](unsigned path,GLenum target,GLuint index,GLuint buffer){if(path==0)Run("gl_buffer_indexed_direct",{UINT64_C(0xa5a5a5a500000000)|target,UINT64_C(0x1234567800000000)|index,UINT64_C(0xfedcba9800000000)|buffer});else if(path==1)Run("gl_buffer_indexed_procedure",{target,index,buffer});else Run("gl_buffer_indexed_pointer",{marker,target,index,buffer});};
 for(const auto &c:categories){
  GLint limit=0;get(c.limit,&limit);Check(!native_error()&&limit>=2,"actual native target-specific binding limit");
  std::array<GLuint,2> objects{},oracle{};
  for(size_t i=0;i<2;++i){Run("gl_buffer_indexed_create",{Address(&objects[i]),(i+1)*256});Check(!Error()&&objects[i]&&is(objects[i]),"existing NDK creation/storage helpers produce real native buffer");gen(1,&oracle[i]);ordinary(GL_ARRAY_BUFFER,oracle[i]);data(GL_ARRAY_BUFFER,GLsizeiptr((i+1)*256),nullptr,GL_DYNAMIC_DRAW);Check(!native_error()&&oracle[i]&&is(oracle[i]),"separate actual native buffer oracle");}
  auto Good=[&](unsigned path,GLuint index,GLuint object,GLuint reference){
   bind(c.target,index,reference);Check(!native_error(),"native reference bind succeeds");auto expected=Observe(c,index);
   Call(path,c.target,index,object);Check(!Error(),"NDK bind succeeds");auto actual=Observe(c,index);
   Check(GLuint(expected.general)==reference&&GLuint(expected.indexed)==reference&&GLuint(actual.general)==object&&GLuint(actual.indexed)==object,"real generic and indexed native IDs agree with local identities");
   expected.general=actual.general=expected.indexed=actual.indexed=0;Check(Equal(actual,expected)&&actual.start==0,"native-reported offset/size/store exactly match; base startsat0");
   if(object){Check(actual.store_queried&&actual.store>0,"real underlying data store remains allocated");}++records;
  };
  for(unsigned path=0;path<3;++path){Good(path,0,objects[0],oracle[0]);Good(path,1,objects[1],oracle[1]);Check(GLuint(Observe(c,0).indexed)==objects[0],"binding index1 preserves index0");Good(path,0,0,0);Check(GLuint(Observe(c,1).indexed)==objects[1],"zero unbind preserves other index");}
  Good(0,0,objects[0],oracle[0]);
  for(unsigned path=0;path<3;++path){
   const std::array<std::array<GLuint,2>,3> invalid_cases={std::array<GLuint,2>{c.target,GLuint(limit)},std::array<GLuint,2>{c.target,0xffffffffU},std::array<GLuint,2>{GL_ARRAY_BUFFER,0}};
   for(auto invalid:invalid_cases){
    auto before=Observe(c,0);bind(invalid[0],invalid[1],objects[0]);const auto expected_error=native_error();Check(expected_error!=GL_NO_ERROR&&Equal(Observe(c,0),before),"native invalid target/index leaves bindings untouched");
    Call(path,invalid[0],invalid[1],objects[0]);Check(Error()==expected_error&&Equal(Observe(c,0),before),"NDK invalid target/index errors and unchanged state match native");++records;
   }
  }
  Invoke(gl,"glEnable",{0xffffffffU});Call(1,c.target,0,objects[0]);Check(Error()==GL_INVALID_ENUM&&!Error()&&GLuint(Observe(c,0).indexed)==objects[0],"successful pointer-free bind preserves prior error exactly once");
  GLint untouched=0x13572468;bool rejected=false;try{Invoke(gl,"glGetIntegeri_v",{c.binding,0,Address(&untouched)});}catch(const std::runtime_error &e){rejected=std::strstr(e.what(),"Unsupported indexed GL query output width")!=nullptr;}
  Check(rejected&&untouched==0x13572468&&!Error(),"existing guest indexed-query whitelist remains narrow");
  bind(c.target,0,oracle[0]);ordinary(GL_ARRAY_BUFFER,oracle[0]);data(GL_ARRAY_BUFFER,768,nullptr,GL_DYNAMIC_DRAW);Check(!native_error(),"native oracle store resized after base binding");auto resized=Observe(c,0);
  Call(2,c.target,0,objects[0]);Invoke(gl,"glBindBuffer",{GL_ARRAY_BUFFER,objects[0]});Invoke(gl,"glBufferData",{GL_ARRAY_BUFFER,768,0,GL_DYNAMIC_DRAW});Check(!Error(),"existing typed allocation resizes actual buffer without rebinding base");auto actual=Observe(c,0);
  Check(actual.store==768&&resized.store==768&&actual.start==resized.start&&actual.size==resized.size,"native effective whole-store and reported range stay truthful after resize");
  bind(c.target,0,oracle[0]);bind(c.target,1,oracle[0]);remove(1,&oracle[0]);Check(!native_error(),"native bound reference deletion");const auto deleted0=Observe(c,0),deleted1=Observe(c,1);
  Call(0,c.target,0,objects[0]);Call(2,c.target,1,objects[0]);Run("gl_buffer_indexed_delete",{objects[0]});Check(!Error()&&!is(objects[0]),"actual NDK deletion ends native object lifetime");
  Check(Equal(Observe(c,0),deleted0)&&Equal(Observe(c,1),deleted1)&&deleted0.general==0&&deleted0.indexed==0&&deleted1.indexed==0,"deleting buffer unbinds both indexed slots and generic target exactly like native");
  Run("gl_buffer_indexed_delete",{objects[1]});remove(1,&oracle[1]);Check(!Error()&&!is(objects[1]),"remaining real buffers deleted");
  std::printf("GL indexed buffer: %s limit=%d resized_native_store=%lld reported_base_size=%lld\n",c.name,limit,static_cast<long long>(actual.store),static_cast<long long>(actual.size));++records;
 }
 alignas(64)uint32_t unrelated=0x12345678;Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"release context for read-only guest-memory check");
 auto reservation=bunker::test::ReserveAcrossOperation(Address(&unrelated),4,[&]{Bind();Call(0,GL_UNIFORM_BUFFER,0,0);egl.ReleaseCurrentThread();});Check(reservation.status==0&&unrelated==0x12345678,"pointer-free native bind does not publish unrelated guest memory");Bind();
 Check(!Error(),"final native context error-free");Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglTerminate",{display}),"owned resources retired");egl.ReleaseCurrentThread();egl.SetProcedureResolver({});
 std::printf("GL-BUFFER-INDEXED-PASS checks=%u calls=%u records=%u commands=1 old_prefix=116 total_commands=121 real_ANGLE=1 synthetic_component=1\n",checks,calls,records);return 0;
}catch(const std::exception &e){std::fprintf(stderr,"indexed buffer component: %s\n",e.what());return 1;}}

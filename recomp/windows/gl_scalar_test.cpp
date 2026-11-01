#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl32.h>
#include "gl_host.h"
#include "egl_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
using namespace bunker::windows;
static unsigned checks;
static HMODULE driver;
static EglHost *egl_provider;
static void Check(bool good,const char *why){if(!good)throw std::runtime_error(why);++checks;}
template<class T>static T NativeSymbol(const char *name){auto raw=GetProcAddress(driver,name);Check(raw!=nullptr,"native scalar/query symbol exists");T result;std::memcpy(&result,&raw,sizeof(result));return result;}
#define GL_NATIVE_REFERENCE
#define gl_scalar_guest native_scalar_reference
#include "gl_scalar_guest.c"
#undef gl_scalar_guest
#undef GL_NATIVE_REFERENCE
template<class T>static addr_t Invoke(T &host,const char *name,std::initializer_list<addr_t> args={}){
  State state{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};size_t at=0;
  for(auto value:args)(state.gpr.*regs[at++]).qword=value;
  host.Invoke(name,state);return state.gpr.x0.qword;
}
static void *Resolve(const char *name){return reinterpret_cast<void*>(egl_provider->Marker(name));}
static const GLenum integer_names[]={GL_ACTIVE_TEXTURE,GL_BLEND,GL_CULL_FACE,GL_DEPTH_TEST,GL_SCISSOR_TEST,GL_DITHER,
 GL_VIEWPORT,GL_SCISSOR_BOX,GL_COLOR_WRITEMASK,GL_DEPTH_WRITEMASK,GL_DEPTH_FUNC,GL_STENCIL_CLEAR_VALUE,
 GL_STENCIL_WRITEMASK,GL_STENCIL_BACK_WRITEMASK,GL_STENCIL_FUNC,GL_STENCIL_BACK_FUNC,GL_STENCIL_REF,GL_STENCIL_BACK_REF,
 GL_STENCIL_VALUE_MASK,GL_STENCIL_BACK_VALUE_MASK,GL_STENCIL_FAIL,GL_STENCIL_PASS_DEPTH_FAIL,GL_STENCIL_PASS_DEPTH_PASS,
 GL_STENCIL_BACK_FAIL,GL_STENCIL_BACK_PASS_DEPTH_FAIL,GL_STENCIL_BACK_PASS_DEPTH_PASS,GL_BLEND_EQUATION_RGB,
 GL_BLEND_EQUATION_ALPHA,GL_BLEND_SRC_RGB,GL_BLEND_DST_RGB,GL_BLEND_SRC_ALPHA,GL_BLEND_DST_ALPHA,GL_CULL_FACE_MODE,
 GL_FRONT_FACE,GL_SAMPLE_COVERAGE_INVERT,GL_GENERATE_MIPMAP_HINT};
static const GLenum float_names[]={GL_COLOR_CLEAR_VALUE,GL_DEPTH_CLEAR_VALUE,GL_DEPTH_RANGE,GL_BLEND_COLOR,
 GL_POLYGON_OFFSET_FACTOR,GL_POLYGON_OFFSET_UNITS,GL_SAMPLE_COVERAGE_VALUE,GL_LINE_WIDTH};
struct Snapshot{std::vector<GLint> integers;std::vector<GLfloat> floats;std::array<uint8_t,256> pixels{};};
static Snapshot Capture(){
  Snapshot s;auto integer=NativeSymbol<PFNGLGETINTEGERVPROC>("glGetIntegerv");auto floating=NativeSymbol<PFNGLGETFLOATVPROC>("glGetFloatv");
  for(auto name:integer_names){GLint values[4]={};integer(name,values);s.integers.insert(s.integers.end(),values,values+4);}
  for(auto name:float_names){GLfloat values[4]={};floating(name,values);s.floats.insert(s.floats.end(),values,values+4);}
  NativeSymbol<PFNGLREADPIXELSPROC>("glReadPixels")(0,0,8,8,GL_RGBA,GL_UNSIGNED_BYTE,s.pixels.data());
  Check(NativeSymbol<PFNGLGETERRORPROC>("glGetError")()==0,"independent native state/pixel capture error-free");return s;
}
int main(){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;
  EglHost egl(windows,GL_SCALAR_DLL_DIRECTORY);egl_provider=&egl;egl.Install(runtime);
  GlHost gl(egl,GL_SCALAR_DLL_DIRECTORY);gl.Install(runtime);egl.SetProcedureResolver([&](const std::string &name){return gl.Marker(name);});
  driver=GetModuleHandleW(L"libGLESv2.dll");Check(driver!=nullptr,"real pinned ANGLE DLL loaded");
  auto display=Invoke(egl,"eglGetDisplay",{0});Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"actual Vulkan display");
  const int attrs[]={0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3026,8,0x3033,1,0x3040,0x40,0x3038};addr_t config=0;int count=0;
  Check(Invoke(egl,"eglChooseConfig",{display,reinterpret_cast<addr_t>(attrs),reinterpret_cast<addr_t>(&config),1,reinterpret_cast<addr_t>(&count)})&&count==1,"RGBA8/depth24/stencil8 real pbuffer config");
  const int ca[]={0x3098,3,0x30fb,1,0x3038},sa[]={0x3057,8,0x3056,8,0x3038};
  auto context=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(ca)});
  auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,reinterpret_cast<addr_t>(sa)});
  Check(context&&surface&&Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"reference current native GLES3 context");
  uint32_t reference_out[6]={};Check(native_scalar_reference(reference_out)==28,"direct driver reference sequence");auto reference=Capture();
  auto guest_context=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(ca)});
  auto guest_surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,reinterpret_cast<addr_t>(sa)});
  Check(guest_context&&guest_surface&&Invoke(egl,"eglMakeCurrent",{display,guest_surface,guest_surface,guest_context}),"separate guest native GLES3 context");
  elf_image image{};Check(!elf_load(GL_SCALAR_LIBRARY,0x5c000000,Resolve,&image),"actual strict NDK scalar caller loads");runtime.AddTraces(kTraces,std::size(kTraces));
  struct Guard {uint64_t before=0x1122334455667788ULL;uint32_t out[6]={};uint64_t after=0x8877665544332211ULL;} guard;
  alignas(16)std::array<uint8_t,65536> stack{};State state{};state.gpr.x0.qword=reinterpret_cast<addr_t>(guard.out);
  state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;
  runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"gl_scalar_guest")));
  Check(state.gpr.x0.qword==28&&state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"actual NDK scalar sequence balanced PC/SP/result");
  Check(guard.before==0x1122334455667788ULL&&guard.after==0x8877665544332211ULL,"NDK output canaries intact");
  Check(guard.out[0]==1&&guard.out[1]==0&&guard.out[2]==0,"one-byte enabled returns and all valid state commands");
  std::sort(guard.out+3,guard.out+5);std::sort(reference_out+3,reference_out+5);
  Check(guard.out[3]==GL_INVALID_ENUM&&guard.out[4]==GL_INVALID_VALUE&&guard.out[5]==0,"distinct driver errors survive successful scalar call and each clear once");
  Check(std::equal(std::begin(guard.out),std::end(guard.out),std::begin(reference_out)),"NDK and direct-driver status results agree");
  auto actual=Capture();Check(actual.integers==reference.integers,"all 36 integer/vector driver state queries match direct reference");
  Check(actual.floats==reference.floats,"all eight float/vector states match direct reference exactly");Check(actual.pixels==reference.pixels,"all 64 RGBA pixels equal direct driver reference");
  for(unsigned y=0;y<8;++y)for(unsigned x=0;x<8;++x){bool inside=x>=2&&x<5&&y>=1&&y<6;const int wanted[]={inside?32:0,inside?191:0,inside?128:0,inside?128:255};
    for(unsigned c=0;c<4;++c)Check(std::abs(int(actual.pixels[(y*8+x)*4+c])-wanted[c])<=1,"independent scissor/color-mask image expectation");}
  State narrow{};narrow.gpr.x0.qword=0xabcdef0100000000ULL|GL_BLEND;narrow.gpr.x1.qword=0x123456789abcdef0ULL;
  gl.Invoke("glIsEnabled",narrow);Check(narrow.gpr.x0.qword==1&&narrow.gpr.x1.qword==0x123456789abcdef0ULL,"GLboolean return zero-extends and preserves unrelated register");
  State mixed{};mixed.gpr.x0.qword=0x1234567800000080ULL;float coverage=.375f;std::memcpy(&mixed.simd.v[0],&coverage,4);gl.Invoke("glSampleCoverage",mixed);
  GLfloat got=0;NativeSymbol<PFNGLGETFLOATVPROC>("glGetFloatv")(GL_SAMPLE_COVERAGE_VALUE,&got);GLint inverted=0;NativeSymbol<PFNGLGETINTEGERVPROC>("glGetIntegerv")(GL_SAMPLE_COVERAGE_INVERT,&inverted);
  Check(got==coverage&&inverted==GL_TRUE,"mixed FP/GPR signature reads scalar float and low GLboolean only");
  Check(gl.Marker("glGetString")==0x7ff450000000ULL&&gl.Marker("glGetError")==0x7ff450000028ULL,"existing query marker identities preserved");
  bool rejected=false;try{gl.Marker("glMapBufferRange");}catch(const std::runtime_error&){rejected=true;}Check(rejected,"unimplemented pointer/output rendering signature still decisive");
  Check(Invoke(gl,"glGetError")==0,"scalar padding tests leave no GL errors");
  Check(!Invoke(gl,"glGetString",{0xffffffffU}),"query records a real pending enum error");
  Invoke(gl,"glViewport",{0,0,0xffffffffU,1});Invoke(gl,"glEnable",{GL_BLEND});
  Check(Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==GL_INVALID_VALUE&&Invoke(gl,"glGetError")==0,"query-cached and new scalar errors combine without loss");
  Check(egl.UsesGlesModule(driver)&&!egl.UsesGlesModule(nullptr),"GL module identity is bound to the actual EGL provider");
  Check(!Invoke(gl,"glGetString",{0xffffffffU}),"cache enum error on guest context B");
  Check(Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"switch current context B to A on same thread");
  Check(Invoke(gl,"glGetError")==0,"cached B error never leaks to A");
  Invoke(gl,"glViewport",{0,0,0xffffffffU,1});Invoke(gl,"glGetString",{GL_VENDOR});
  Check(Invoke(egl,"eglMakeCurrent",{display,guest_surface,guest_surface,guest_context}),"restore current B");
  Check(Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==0,"B retains its own enum error across context switches");
  Check(Invoke(egl,"eglMakeCurrent",{display,surface,surface,context})&&Invoke(gl,"glGetError")==GL_INVALID_VALUE&&Invoke(gl,"glGetError")==0,"A retains its separate value error");
  Check(Invoke(egl,"eglMakeCurrent",{display,guest_surface,guest_surface,guest_context}),"select B for actual thread migration");
  Invoke(gl,"glGetString",{0xffffffffU});Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"release B before migrating to another native thread");
  std::exception_ptr worker_error;bool migrated=false;
  std::thread worker([&]{try{
    if(!Invoke(egl,"eglMakeCurrent",{display,guest_surface,guest_surface,guest_context}))throw std::runtime_error("worker cannot bind migrated B");
    migrated=Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==0;
    Invoke(gl,"glViewport",{0,0,0xffffffffU,1});Invoke(gl,"glGetString",{GL_VENDOR});
    egl.ReleaseCurrentThread();
  }catch(...){worker_error=std::current_exception();try{egl.ReleaseCurrentThread();}catch(...){}}});worker.join();
  if(worker_error)std::rethrow_exception(worker_error);
  Check(migrated,"cached error follows actual EGL context migration to worker");
  Check(Invoke(egl,"eglMakeCurrent",{display,guest_surface,guest_surface,guest_context})&&Invoke(gl,"glGetError")==GL_INVALID_VALUE&&Invoke(gl,"glGetError")==0,"worker-cached error follows B back to original thread");
  Check(Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"select A for deferred destruction");
  Invoke(gl,"glGetString",{0xffffffffU});Check(Invoke(egl,"eglDestroyContext",{display,context}),"destroy current A is deferred");
  Check(egl.ContextAlive(context)&&egl.CurrentContextToken()==context&&Invoke(gl,"glGetError")==GL_INVALID_ENUM,"deferred-deleted current context retains its own errors");
  Invoke(gl,"glGetString",{0xffffffffU});Check(Invoke(egl,"eglMakeCurrent",{display,guest_surface,guest_surface,guest_context})&&!egl.ContextAlive(context),"unbind retires deleted context A");
  auto replacement=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(ca)});
  Check(replacement&&replacement!=context&&Invoke(egl,"eglMakeCurrent",{display,surface,surface,replacement}),"replacement context has fresh provider identity");
  Check(Invoke(gl,"glGetError")==0,"destroyed context errors never reach a fresh context");
  Check(Invoke(egl,"eglMakeCurrent",{display,guest_surface,guest_surface,guest_context})&&Invoke(egl,"eglDestroyContext",{display,replacement}),"retire replacement after unbind");
  GLint untouched=0x12345678;Check(!Invoke(egl,"eglGetConfigAttrib",{display,0xdeadbeef,0x3024,reinterpret_cast<addr_t>(&untouched)}),"establish real provider EGL_BAD_CONFIG");
  Check(Invoke(gl,"glGetError")==0&&Invoke(egl,"eglGetError")==0x3005&&untouched==0x12345678,"GL context observation preserves pending EGL error and output");
  Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"explicitly unbind final context");
  rejected=false;try{Invoke(gl,"glGetError");}catch(const std::runtime_error&){rejected=true;}Check(rejected,"GL call without an owned current EGL context fails explicitly");
  Check(Invoke(egl,"eglDestroySurface",{display,guest_surface})&&Invoke(egl,"eglDestroyContext",{display,guest_context})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglTerminate",{display}),"all real GLES resources retired");
  egl.ReleaseCurrentThread();egl.SetProcedureResolver({});std::printf("GL scalar commands: %u checks passed; 28 actual NDK signatures, 64 real RGBA pixels, native state/error/ABI parity\n",checks);
}

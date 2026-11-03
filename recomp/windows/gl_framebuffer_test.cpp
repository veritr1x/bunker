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
static HMODULE driver;
static EglHost *egl_provider;
static void Check(bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;}
template<class T>static T NativeSymbol(const char *name){
  auto p=GetProcAddress(driver,name);if(!p)throw std::runtime_error(name);
  T value;static_assert(sizeof(value)==sizeof(p));std::memcpy(&value,&p,sizeof(value));return value;
}
#define GL_FRAMEBUFFER_NATIVE_REFERENCE
#define gl_framebuffer_create native_create
#define gl_framebuffer_setup native_setup
#define gl_framebuffer_attach_texture native_attach_texture
#define gl_framebuffer_names native_names
#define gl_framebuffer_delete native_delete
#define gl_framebuffer_renderbuffer_query native_renderbuffer_query
#define gl_framebuffer_attachment_query native_attachment_query
#define gl_framebuffer_cleanup native_cleanup
#include "gl_framebuffer_guest.c"
#undef gl_framebuffer_create
#undef gl_framebuffer_setup
#undef gl_framebuffer_attach_texture
#undef gl_framebuffer_names
#undef gl_framebuffer_delete
#undef gl_framebuffer_renderbuffer_query
#undef gl_framebuffer_attachment_query
#undef gl_framebuffer_cleanup
#undef GL_FRAMEBUFFER_NATIVE_REFERENCE
static addr_t Address(const void *p){return reinterpret_cast<addr_t>(p);}
template<class T>static addr_t Invoke(T &host,const char *name,std::initializer_list<addr_t> args={}){
  State state{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t i=0;
  for(auto value:args)(state.gpr.*regs[i++]).qword=value;
  host.Invoke(name,state);return state.gpr.x0.qword;
}
static void *Resolve(const char *name){return reinterpret_cast<void*>(egl_provider->Marker(name));}
struct GuardPage{
  uint8_t *base=static_cast<uint8_t*>(VirtualAlloc(nullptr,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
  GuardPage(){Check(base!=nullptr,"guard-page allocation");DWORD old;Check(VirtualProtect(base+4096,4096,PAGE_NOACCESS,&old)!=0,"no-access trailing page");std::memset(base,0xa5,4096);}
  ~GuardPage(){if(base)VirtualFree(base,0,MEM_RELEASE);}
  uint32_t *End(size_t words){return reinterpret_cast<uint32_t*>(base+4096-words*4);}
  void Prefix(size_t words){bool equal=true;for(size_t i=0;i<4096-words*4;++i)equal=equal&&base[i]==0xa5;Check(equal,"exact guest output prefix unchanged");}
};
// Native-only storage observer. This does not qualify guest non-default-FBO
// glReadPixels, which remains outside the provider's existing readback scope.
static std::array<uint8_t,256> NativePixels(){
  NativeSymbol<PFNGLDISABLEPROC>("glDisable")(GL_DITHER);
  NativeSymbol<PFNGLDISABLEPROC>("glDisable")(GL_SCISSOR_TEST);
  NativeSymbol<PFNGLCLEARCOLORPROC>("glClearColor")(1,0,0,1);
  NativeSymbol<PFNGLCLEARPROC>("glClear")(GL_COLOR_BUFFER_BIT);
  NativeSymbol<PFNGLPIXELSTOREIPROC>("glPixelStorei")(GL_PACK_ALIGNMENT,1);
  std::array<uint8_t,256> result{};
  NativeSymbol<PFNGLREADPIXELSPROC>("glReadPixels")(0,0,8,8,GL_RGBA,GL_UNSIGNED_BYTE,result.data());
  Check(NativeSymbol<PFNGLGETERRORPROC>("glGetError")()==GL_NO_ERROR,"actual native FBO clear/readback succeeds");
  return result;
}
static GLuint NativeTexture(bool cube){
  GLuint texture=0;NativeSymbol<PFNGLGENTEXTURESPROC>("glGenTextures")(1,&texture);
  const GLenum target=cube?GL_TEXTURE_CUBE_MAP:GL_TEXTURE_2D;
  NativeSymbol<PFNGLBINDTEXTUREPROC>("glBindTexture")(target,texture);
  NativeSymbol<PFNGLTEXPARAMETERIPROC>("glTexParameteri")(target,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
  NativeSymbol<PFNGLTEXPARAMETERIPROC>("glTexParameteri")(target,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
  std::array<uint8_t,64> pixels{};
  for(unsigned face=0;face<(cube?6U:1U);++face)
    NativeSymbol<PFNGLTEXIMAGE2DPROC>("glTexImage2D")(cube?GL_TEXTURE_CUBE_MAP_POSITIVE_X+face:GL_TEXTURE_2D,0,GL_RGBA,4,4,0,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());
  Check(texture&&NativeSymbol<PFNGLGETERRORPROC>("glGetError")()==GL_NO_ERROR,"native-only texture fixture storage");
  return texture;
}
int main(){try{
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;
  EglHost egl(windows,GL_FRAMEBUFFER_DLL_DIRECTORY);egl_provider=&egl;egl.Install(runtime);
  GlHost gl(egl,GL_FRAMEBUFFER_DLL_DIRECTORY);gl.Install(runtime);
  egl.SetProcedureResolver([&](const std::string &name){return gl.Marker(name);});
  driver=GetModuleHandleW(L"libGLESv2.dll");Check(driver!=nullptr,"pinned ANGLE module loaded");
  auto display=Invoke(egl,"eglGetDisplay",{0});Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"actual ANGLE display initialized");
  const int attrs[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,0x40,EGL_NONE};
  addr_t config=0;int count=0;Check(Invoke(egl,"eglChooseConfig",{display,Address(attrs),Address(&config),1,Address(&count)})&&count==1,"actual pbuffer config");
  const int ca[]={EGL_CONTEXT_CLIENT_VERSION,3,0x30fb,1,EGL_NONE},sa[]={EGL_WIDTH,8,EGL_HEIGHT,8,EGL_NONE};
  auto Context=[&]{auto c=Invoke(egl,"eglCreateContext",{display,config,0,Address(ca)});Check(c!=0,"independent owned context");return c;};
  auto Surface=[&]{auto s=Invoke(egl,"eglCreatePbufferSurface",{display,config,Address(sa)});Check(s!=0,"owned pbuffer");return s;};
  auto Bind=[&](addr_t c,addr_t s){Check(Invoke(egl,"eglMakeCurrent",{display,s,s,c})!=0,"owned context made current");};
  const auto reference_context=Context(),reference_surface=Surface(),context=Context(),surface=Surface();
  Bind(reference_context,reference_surface);FramebufferObjects reference_objects{};FramebufferReport reference{};
  native_create(&reference_objects);native_setup(&reference_objects,&reference);auto expected_pixels=NativePixels();
  Check(reference.attachment[1]==int32_t(reference_objects.renderbuffers[0]),"native reference attachment identity");reference.attachment[1]=1;
  Bind(context,surface);elf_image image{};Check(!elf_load(GL_FRAMEBUFFER_LIBRARY,0x5c000000,Resolve,&image),"strict NDK fixture loads");runtime.AddTraces(kTraces,std::size(kTraces));
  auto Guest=[&](const char *name,std::initializer_list<addr_t> args={}){
    alignas(16)std::array<uint8_t,65536> stack{};State state{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t at=0;
    for(auto value:args)(state.gpr.*regs[at++]).qword=value;
    state.gpr.sp.qword=Address(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;
    auto entry=elf_symbol(&image,name);Check(entry!=nullptr,"actual NDK entry exists");runtime.Run(state,Address(entry));
    Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==Address(stack.data()+stack.size()),"NDK PC/SP normal return");return state.gpr.x0.qword;
  };
  std::array<uint64_t,14> resolved{};resolved.front()=0x1122334455667788ULL;resolved.back()=0x8877665544332211ULL;
  Guest("gl_framebuffer_resolve",{Address(resolved.data()+1)});size_t index=1;addr_t previous=0;
#define GL_FRAMEBUFFER_COMMAND(name,type) Check(resolved[index++]==gl.Marker(#name),"actual NDK resolves typed framebuffer marker");if(previous)Check(gl.Marker(#name)==previous+8,"framebuffer marker group order");previous=gl.Marker(#name);
#include "gl_framebuffer_commands.inc"
#undef GL_FRAMEBUFFER_COMMAND
  Check(resolved.front()==0x1122334455667788ULL&&resolved.back()==0x8877665544332211ULL,"resolver output canaries");
  Check(gl.Marker("glGetString")==0x7ff450000000ULL&&gl.Marker("glPixelStorei")==0x7ff450000000ULL+62*8,"old marker range unchanged");
  struct {uint64_t before=0x123456789abcdef0ULL;FramebufferObjects objects{};uint64_t after=0xfedcba9876543210ULL;} names;
  Guest("gl_framebuffer_create",{Address(&names.objects)});const auto &objects=names.objects;
  Check(names.before==0x123456789abcdef0ULL&&names.after==0xfedcba9876543210ULL,"GLuint generation bounded writes");
  FramebufferReport actual{};Guest("gl_framebuffer_setup",{Address(&objects),Address(&actual)});
  Check(actual.attachment[1]==int32_t(objects.renderbuffers[0]),"actual NDK native attachment identity");actual.attachment[1]=1;
  Check(!std::memcmp(&actual,&reference,sizeof(actual)),"all NDK status and nine scalar RBO queries equal separate native reference");
  Check(actual.empty_status!=GL_FRAMEBUFFER_COMPLETE&&actual.complete_status==GL_FRAMEBUFFER_COMPLETE,"real empty/incomplete then allocated/complete framebuffer");
  Check(actual.renderbuffer[0]==8&&actual.renderbuffer[1]==8&&actual.attachment[0]==GL_RENDERBUFFER,"actual storage dimensions/type");
  Check(NativePixels()==expected_pixels,"actual FBO GPU storage matches native reference pixels");
  for(bool cube:{false,true}){
    const GLenum face=cube?GL_TEXTURE_CUBE_MAP_POSITIVE_X:GL_TEXTURE_2D;
    Bind(reference_context,reference_surface);GLuint rt=NativeTexture(cube);FramebufferTextureReport expected{};native_attach_texture(rt,face,&expected);
    Check(expected.attachment[1]==int32_t(rt),"native texture attachment identity");expected.attachment[1]=1;
    Bind(context,surface);GLuint texture=NativeTexture(cube);FramebufferTextureReport got{};Guest("gl_framebuffer_attach_texture",{texture,face,Address(&got)});
    Check(got.attachment[1]==int32_t(texture),"NDK attachment uses actual texture ID");got.attachment[1]=1;
    Check(!std::memcmp(&got,&expected,sizeof(got))&&got.attachment[0]==GL_TEXTURE&&got.attachment[2]==0&&got.attachment[3]==int32_t(cube?face:0),"all four texture attachment scalars match native reference");
    NativeSymbol<PFNGLDELETETEXTURESPROC>("glDeleteTextures")(1,&texture);
    Bind(reference_context,reference_surface);NativeSymbol<PFNGLDELETETEXTURESPROC>("glDeleteTextures")(1,&rt);
  }
  Bind(context,surface);Invoke(gl,"glFramebufferRenderbuffer",{GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_RENDERBUFFER,objects.renderbuffers[0]});
  GuardPage output;auto scalar=reinterpret_cast<int32_t*>(output.End(1));
  Guest("gl_framebuffer_renderbuffer_query",{GL_RENDERBUFFER,GL_RENDERBUFFER_WIDTH,Address(scalar)});Check(*scalar==8,"query exactly four bytes at guard boundary");output.Prefix(1);
  *scalar=0x13572468;Guest("gl_framebuffer_renderbuffer_query",{GL_RENDERBUFFER,0xffffffffU,Address(scalar)});
  Check(*scalar==0x13572468&&Invoke(gl,"glGetError")==GL_INVALID_ENUM,"invalid RBO pname does not publish output");
  Guest("gl_framebuffer_attachment_query",{0xffffffffU,GL_COLOR_ATTACHMENT0,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE,Address(scalar)});
  Check(*scalar==0x13572468&&Invoke(gl,"glGetError")==GL_INVALID_ENUM,"invalid FBO target does not publish output");
  Guest("gl_framebuffer_attachment_query",{GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,0xffffffffU,Address(scalar)});
  Check(*scalar==0x13572468&&Invoke(gl,"glGetError")==GL_INVALID_ENUM,"invalid FBO pname does not publish output");
  Check(Invoke(gl,"glCheckFramebufferStatus",{0xffffffffU})==0&&Invoke(gl,"glGetError")==GL_INVALID_ENUM,"status returns real native failure rather than fabricated completeness");
  Invoke(gl,"glEnable",{0xffffffffU});Guest("gl_framebuffer_renderbuffer_query",{GL_RENDERBUFFER,GL_RENDERBUFFER_WIDTH,Address(scalar)});
  Check(*scalar==8&&Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==0,"successful query retains prior native error");
  Invoke(gl,"glRenderbufferStorage",{GL_RENDERBUFFER,GL_RGBA4,uint64_t(-1),8});
  Check(Invoke(gl,"glGetError")==GL_INVALID_VALUE,"negative storage width uses native signed validation");
  Guest("gl_framebuffer_renderbuffer_query",{GL_RENDERBUFFER,GL_RENDERBUFFER_WIDTH,Address(scalar)});Check(*scalar==8,"failed storage preserves old storage");
  for(uint32_t rbo:{0U,1U}){
    Guest("gl_framebuffer_names",{rbo,0,0});Guest("gl_framebuffer_delete",{rbo,0,0});Check(Invoke(gl,"glGetError")==0,"zero count never accesses null array");
    Guest("gl_framebuffer_names",{rbo,uint64_t(-1),0});Check(Invoke(gl,"glGetError")==GL_INVALID_VALUE,"negative generation count native error without pointer access");
    Guest("gl_framebuffer_delete",{rbo,uint64_t(-1),0});Check(Invoke(gl,"glGetError")==GL_INVALID_VALUE,"negative deletion count native error without pointer access");
    GuardPage array;auto values=array.End(2);Guest("gl_framebuffer_names",{rbo,2,Address(values)});Check(values[0]&&values[1]&&values[0]!=values[1],"two real generated names");array.Prefix(2);
    Guest("gl_framebuffer_delete",{rbo,2,Address(values)});Guest("gl_framebuffer_delete",{rbo,2,Address(values)});Check(Invoke(gl,"glGetError")==0,"repeated deleted names ignored by driver");
  }
  alignas(64)int32_t width=8;Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"release context before query reservation");
  auto write=bunker::test::ReserveAcrossOperation(Address(&width),4,[&]{Bind(context,surface);Guest("gl_framebuffer_renderbuffer_query",{GL_RENDERBUFFER,GL_RENDERBUFFER_WIDTH,Address(&width)});egl.ReleaseCurrentThread();});
  Check(write.loaded==8&&write.status==1&&width==8,"same-value query is actual tracked guest write");
  alignas(64)uint32_t zero_name=0;
  auto read=bunker::test::ReserveAcrossOperation(Address(&zero_name),4,[&]{Bind(context,surface);Guest("gl_framebuffer_delete",{0,1,Address(&zero_name)});egl.ReleaseCurrentThread();});
  Check(read.status==0&&zero_name==0,"deletion snapshots input without guest write");Bind(context,surface);
  Guest("gl_framebuffer_delete",{1,1,Address(&objects.renderbuffers[0])});
  GLint binding=-1;NativeSymbol<PFNGLGETINTEGERVPROC>("glGetIntegerv")(GL_RENDERBUFFER_BINDING,&binding);Check(binding==0,"deleting bound RBO really unbinds it");
  Guest("gl_framebuffer_attachment_query",{GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE,Address(scalar)});Check(*scalar==GL_NONE,"deleting current FBO attachment really detaches");
  Guest("gl_framebuffer_delete",{0,1,Address(&objects.framebuffers[0])});NativeSymbol<PFNGLGETINTEGERVPROC>("glGetIntegerv")(GL_FRAMEBUFFER_BINDING,&binding);Check(binding==0,"deleting bound FBO really binds default");
  Guest("gl_framebuffer_cleanup",{Address(&objects)});Check(Invoke(gl,"glGetError")==0,"actual NDK cleanup succeeds");
  Bind(reference_context,reference_surface);native_cleanup(&reference_objects);Check(NativeSymbol<PFNGLGETERRORPROC>("glGetError")()==0,"native reference cleanup succeeds");
  Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"unbind before teardown");
  for(auto c:{reference_context,context})Check(Invoke(egl,"eglDestroyContext",{display,c}),"real context retired");
  for(auto s:{reference_surface,surface})Check(Invoke(egl,"eglDestroySurface",{display,s}),"real pbuffer retired");
  Check(Invoke(egl,"eglTerminate",{display}),"real display terminated");egl.ReleaseCurrentThread();egl.SetProcedureResolver({});
  std::printf("GL framebuffer: %u checks passed; 12 actual NDK signatures, native ANGLE storage/attachments/errors/deletion, guarded tracked outputs; no game/window presentation claim\n",checks);return 0;
}catch(const std::exception &e){std::fprintf(stderr,"GL framebuffer failure: %s\n",e.what());return 1;}}

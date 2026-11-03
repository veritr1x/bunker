#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl31.h>
#include <EGL/egl.h>
#include "gl_host.h"
#include "egl_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <thread>
#include <vector>
using namespace bunker::windows;
namespace {
unsigned checks=0,calls=0;GlHost *graphics=nullptr;
void Check(bool ok,const char*why){if(!ok)throw std::runtime_error(why);++checks;}
template<class F>F Native(HMODULE m,const char*n){auto p=GetProcAddress(m,n);if(!p)throw std::runtime_error(n);F f;std::memcpy(&f,&p,sizeof(f));return f;}
void *Resolve(const char*n){return reinterpret_cast<void*>(graphics->Marker(n));}
template<class H>addr_t Invoke(H&h,const char*n,std::initializer_list<addr_t>a={}){State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};size_t i=0;for(auto v:a)(s.gpr.*r[i++]).qword=v;h.Invoke(n,s);return s.gpr.x0.qword;}
struct Driver {
 HMODULE m;
#define NATIVE(name,type) type name;
 NATIVE(glGetError,PFNGLGETERRORPROC) NATIVE(glGetIntegerv,PFNGLGETINTEGERVPROC)
 NATIVE(glGenTextures,PFNGLGENTEXTURESPROC) NATIVE(glDeleteTextures,PFNGLDELETETEXTURESPROC)
 NATIVE(glBindTexture,PFNGLBINDTEXTUREPROC) NATIVE(glTexParameteri,PFNGLTEXPARAMETERIPROC)
 NATIVE(glTexParameterf,PFNGLTEXPARAMETERFPROC) NATIVE(glGetTexParameteriv,PFNGLGETTEXPARAMETERIVPROC)
 NATIVE(glTexImage2D,PFNGLTEXIMAGE2DPROC) NATIVE(glTexSubImage2D,PFNGLTEXSUBIMAGE2DPROC)
 NATIVE(glCompressedTexImage2D,PFNGLCOMPRESSEDTEXIMAGE2DPROC) NATIVE(glCompressedTexSubImage2D,PFNGLCOMPRESSEDTEXSUBIMAGE2DPROC)
 NATIVE(glCopyTexImage2D,PFNGLCOPYTEXIMAGE2DPROC) NATIVE(glCopyTexSubImage2D,PFNGLCOPYTEXSUBIMAGE2DPROC)
 NATIVE(glPixelStorei,PFNGLPIXELSTOREIPROC) NATIVE(glBindBuffer,PFNGLBINDBUFFERPROC)
 NATIVE(glGenBuffers,PFNGLGENBUFFERSPROC) NATIVE(glBufferData,PFNGLBUFFERDATAPROC) NATIVE(glDeleteBuffers,PFNGLDELETEBUFFERSPROC)
 NATIVE(glCreateShader,PFNGLCREATESHADERPROC) NATIVE(glShaderSource,PFNGLSHADERSOURCEPROC)
 NATIVE(glCompileShader,PFNGLCOMPILESHADERPROC) NATIVE(glGetShaderiv,PFNGLGETSHADERIVPROC)
 NATIVE(glDeleteShader,PFNGLDELETESHADERPROC) NATIVE(glCreateProgram,PFNGLCREATEPROGRAMPROC)
 NATIVE(glAttachShader,PFNGLATTACHSHADERPROC) NATIVE(glLinkProgram,PFNGLLINKPROGRAMPROC)
 NATIVE(glGetProgramiv,PFNGLGETPROGRAMIVPROC) NATIVE(glUseProgram,PFNGLUSEPROGRAMPROC)
 NATIVE(glDeleteProgram,PFNGLDELETEPROGRAMPROC) NATIVE(glGetUniformLocation,PFNGLGETUNIFORMLOCATIONPROC)
 NATIVE(glUniform1i,PFNGLUNIFORM1IPROC) NATIVE(glDrawArrays,PFNGLDRAWARRAYSPROC)
 NATIVE(glViewport,PFNGLVIEWPORTPROC) NATIVE(glReadPixels,PFNGLREADPIXELSPROC)
 NATIVE(glBindFramebuffer,PFNGLBINDFRAMEBUFFERPROC) NATIVE(glGenFramebuffers,PFNGLGENFRAMEBUFFERSPROC)
 NATIVE(glFramebufferTexture2D,PFNGLFRAMEBUFFERTEXTURE2DPROC) NATIVE(glCheckFramebufferStatus,PFNGLCHECKFRAMEBUFFERSTATUSPROC)
 NATIVE(glDeleteFramebuffers,PFNGLDELETEFRAMEBUFFERSPROC) NATIVE(glClearColor,PFNGLCLEARCOLORPROC)
 NATIVE(glClear,PFNGLCLEARPROC) NATIVE(glActiveTexture,PFNGLACTIVETEXTUREPROC)
#undef NATIVE
 Driver():m(GetModuleHandleW(L"libGLESv2.dll")){
#define NATIVE(name,type) name=Native<type>(m,#name);
 NATIVE(glGetError,PFNGLGETERRORPROC)
 NATIVE(glGetIntegerv,PFNGLGETINTEGERVPROC)
 NATIVE(glGenTextures,PFNGLGENTEXTURESPROC)
 NATIVE(glDeleteTextures,PFNGLDELETETEXTURESPROC)
 NATIVE(glBindTexture,PFNGLBINDTEXTUREPROC)
 NATIVE(glTexParameteri,PFNGLTEXPARAMETERIPROC)
 NATIVE(glTexParameterf,PFNGLTEXPARAMETERFPROC)
 NATIVE(glGetTexParameteriv,PFNGLGETTEXPARAMETERIVPROC)
 NATIVE(glTexImage2D,PFNGLTEXIMAGE2DPROC)
 NATIVE(glTexSubImage2D,PFNGLTEXSUBIMAGE2DPROC)
 NATIVE(glCompressedTexImage2D,PFNGLCOMPRESSEDTEXIMAGE2DPROC)
 NATIVE(glCompressedTexSubImage2D,PFNGLCOMPRESSEDTEXSUBIMAGE2DPROC)
 NATIVE(glCopyTexImage2D,PFNGLCOPYTEXIMAGE2DPROC)
 NATIVE(glCopyTexSubImage2D,PFNGLCOPYTEXSUBIMAGE2DPROC)
 NATIVE(glPixelStorei,PFNGLPIXELSTOREIPROC)
 NATIVE(glBindBuffer,PFNGLBINDBUFFERPROC)
 NATIVE(glGenBuffers,PFNGLGENBUFFERSPROC)
 NATIVE(glBufferData,PFNGLBUFFERDATAPROC)
 NATIVE(glDeleteBuffers,PFNGLDELETEBUFFERSPROC)
 NATIVE(glCreateShader,PFNGLCREATESHADERPROC)
 NATIVE(glShaderSource,PFNGLSHADERSOURCEPROC)
 NATIVE(glCompileShader,PFNGLCOMPILESHADERPROC)
 NATIVE(glGetShaderiv,PFNGLGETSHADERIVPROC)
 NATIVE(glDeleteShader,PFNGLDELETESHADERPROC)
 NATIVE(glCreateProgram,PFNGLCREATEPROGRAMPROC)
 NATIVE(glAttachShader,PFNGLATTACHSHADERPROC)
 NATIVE(glLinkProgram,PFNGLLINKPROGRAMPROC)
 NATIVE(glGetProgramiv,PFNGLGETPROGRAMIVPROC)
 NATIVE(glUseProgram,PFNGLUSEPROGRAMPROC)
 NATIVE(glDeleteProgram,PFNGLDELETEPROGRAMPROC)
 NATIVE(glGetUniformLocation,PFNGLGETUNIFORMLOCATIONPROC)
 NATIVE(glUniform1i,PFNGLUNIFORM1IPROC)
 NATIVE(glDrawArrays,PFNGLDRAWARRAYSPROC)
 NATIVE(glViewport,PFNGLVIEWPORTPROC)
 NATIVE(glReadPixels,PFNGLREADPIXELSPROC)
 NATIVE(glBindFramebuffer,PFNGLBINDFRAMEBUFFERPROC)
 NATIVE(glGenFramebuffers,PFNGLGENFRAMEBUFFERSPROC)
 NATIVE(glFramebufferTexture2D,PFNGLFRAMEBUFFERTEXTURE2DPROC)
 NATIVE(glCheckFramebufferStatus,PFNGLCHECKFRAMEBUFFERSTATUSPROC)
 NATIVE(glDeleteFramebuffers,PFNGLDELETEFRAMEBUFFERSPROC)
 NATIVE(glClearColor,PFNGLCLEARCOLORPROC)
 NATIVE(glClear,PFNGLCLEARPROC)
 NATIVE(glActiveTexture,PFNGLACTIVETEXTUREPROC)
#undef NATIVE
 }
 GLuint New(){GLuint t=0;glGenTextures(1,&t);glBindTexture(GL_TEXTURE_2D,t);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);return t;}
 void Unpack(GLint alignment=1,GLint row=0,GLint skiprows=0,GLint skippixels=0){glPixelStorei(GL_UNPACK_ALIGNMENT,alignment);glPixelStorei(GL_UNPACK_ROW_LENGTH,row);glPixelStorei(GL_UNPACK_SKIP_ROWS,skiprows);glPixelStorei(GL_UNPACK_SKIP_PIXELS,skippixels);}
 GLuint Program(){
  const char*vs="#version 300 es\nout vec2 uv;void main(){vec2 p=vec2((gl_VertexID==1)?3.0:-1.0,(gl_VertexID==2)?3.0:-1.0);uv=(p+1.0)*0.5;gl_Position=vec4(p,0,1);}";
  const char*fs="#version 300 es\nprecision highp float;in vec2 uv;uniform sampler2D tex;out vec4 color;void main(){color=texture(tex,uv);}";
  auto Shader=[&](GLenum type,const char*source){auto s=glCreateShader(type);glShaderSource(s,1,&source,nullptr);glCompileShader(s);GLint ok=0;glGetShaderiv(s,GL_COMPILE_STATUS,&ok);Check(ok!=0,"native oracle shader compile");return s;};
  auto v=Shader(GL_VERTEX_SHADER,vs),f=Shader(GL_FRAGMENT_SHADER,fs),p=glCreateProgram();glAttachShader(p,v);glAttachShader(p,f);glLinkProgram(p);GLint ok=0;glGetProgramiv(p,GL_LINK_STATUS,&ok);Check(ok!=0,"native oracle link");glDeleteShader(v);glDeleteShader(f);glUseProgram(p);glUniform1i(glGetUniformLocation(p,"tex"),0);return p;
 }
 std::vector<uint8_t> Sample(GLuint texture,GLuint program){
  glBindFramebuffer(GL_FRAMEBUFFER,0);glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,texture);glUseProgram(program);glViewport(0,0,16,16);glDrawArrays(GL_TRIANGLES,0,3);
  glBindBuffer(GL_PIXEL_PACK_BUFFER,0);glPixelStorei(GL_PACK_ALIGNMENT,1);glPixelStorei(GL_PACK_ROW_LENGTH,0);glPixelStorei(GL_PACK_SKIP_ROWS,0);glPixelStorei(GL_PACK_SKIP_PIXELS,0);
  std::vector<uint8_t> pixels(16*16*4);glReadPixels(0,0,16,16,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());Check(glGetError()==GL_NO_ERROR,"native sampling oracle error");return pixels;
 }
};
}
int main(){try{
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
 std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(90));std::fputs("texture component watchdog\n",stderr);std::_Exit(95);}).detach();
 bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;EglHost egl(windows,GL_TEXTURE_DLL_DIRECTORY);egl.Install(runtime);GlHost gl(egl,GL_TEXTURE_DLL_DIRECTORY);graphics=&gl;gl.Install(runtime);
 auto display=Invoke(egl,"eglGetDisplay");Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"real ANGLE display");
 const GLint attributes[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT, EGL_NONE};addr_t config=0;GLint count=0;
 Check(Invoke(egl,"eglChooseConfig",{display,reinterpret_cast<addr_t>(attributes),reinterpret_cast<addr_t>(&config),1,reinterpret_cast<addr_t>(&count)})&&count==1,"real pbuffer configuration");
 const GLint context_attributes[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_CONTEXT_MINOR_VERSION,1,EGL_NONE},surface_attributes[]={EGL_WIDTH,16,EGL_HEIGHT,16,EGL_NONE};auto context=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(context_attributes)});auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,reinterpret_cast<addr_t>(surface_attributes)});Check(context&&surface&&Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"real GLES3.1 context");
 const char*old_names[]={"glGetString","glGetStringi","glGetIntegerv","glGetFloatv","glGetBooleanv","glGetError","glActiveTexture","glEnable","glDisable","glIsEnabled","glViewport","glScissor","glClearColor","glClearDepthf","glClearStencil","glClear","glColorMask","glDepthMask","glDepthFunc","glDepthRangef","glStencilMaskSeparate","glStencilFuncSeparate","glStencilOpSeparate","glBlendColor","glBlendEquationSeparate","glBlendFuncSeparate","glCullFace","glFrontFace","glPolygonOffset","glSampleCoverage","glLineWidth","glHint","glFlush","glFinish","glCreateShader","glShaderSource","glCompileShader","glGetShaderiv","glGetShaderInfoLog","glDeleteShader","glCreateProgram","glAttachShader","glDetachShader","glLinkProgram","glGetProgramiv","glGetProgramInfoLog","glUseProgram","glDeleteProgram","glGenBuffers","glBindBuffer","glBufferData","glBufferSubData","glDeleteBuffers","glGenVertexArrays","glBindVertexArray","glDeleteVertexArrays","glEnableVertexAttribArray","glDisableVertexAttribArray","glVertexAttribPointer","glDrawArrays","glDrawElements","glReadPixels","glPixelStorei"};
 Check(GlHost::Commands().size()>=77,"old prefix and additive texture catalog");for(size_t i=0;i<63;++i)Check(GlHost::Commands()[i]==old_names[i]&&gl.Marker(old_names[i])==gl.Marker(old_names[0])+i*8,"all original63 marker indices unchanged");
#define GL_TEXTURE_COMMAND(name,type) Check(gl.Marker(#name)!=0,"dynamic texture marker: " #name);
#include "gl_texture_commands.inc"
#undef GL_TEXTURE_COMMAND
 Driver d;auto program=d.Program();
 elf_image image{};Check(!elf_load(GL_TEXTURE_IMAGE,0x5d000000,Resolve,&image),"original NDK texture callers");runtime.AddTraces(kTraces,std::size(kTraces));
 auto Run=[&](const char*name,std::initializer_list<addr_t>arguments={},const GLfloat*fp=nullptr){
  alignas(16)std::array<uint8_t,65536>stack{};State s{};const addr_t sp=reinterpret_cast<addr_t>(stack.data()+stack.size()-64);s.gpr.sp.qword=sp;s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x123456789abcdef0ULL;Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t i=0;for(auto a:arguments){if(i<8)(s.gpr.*regs[i]).qword=a;else std::memcpy(reinterpret_cast<void*>(sp+(i-8)*8),&a,8);++i;}if(fp)std::memcpy(&s.simd.v[0],fp,4);
  auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));const auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(entry!=0,"NDK wrapper export");Check(runtime.Run(s,entry,token)==token&&s.gpr.sp.qword==sp&&s.gpr.x19.qword==0x123456789abcdef0ULL&&s.gpr.x30.qword==0xfeedffff&&s.gpr.pc.qword==0xfeedffff,"actual NDK ABI state and token");++calls;
 };
 auto Error=[&](){return GLenum(Invoke(gl,"glGetError"));};
 struct{uint32_t a;GLuint value;uint32_t b;}name{0x12345678,0,0x87654321};Run("tx_gen",{1,reinterpret_cast<addr_t>(&name.value)});Check(name.value&&name.a==0x12345678&&name.b==0x87654321&&!Error(),"tracked GLuint generation and guards");GLuint texture=name.value;
 Run("tx_bind",{UINT64_C(0x1234567800000000)|GL_TEXTURE_2D,texture});Run("tx_parameteri",{GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST});Run("tx_parameteri",{GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST});
 GLfloat lod=-0.5f;Run("tx_parameterf",{GL_TEXTURE_2D,GL_TEXTURE_MIN_LOD},&lod);GLint expected=0;d.glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_MIN_LOD,&expected);struct{uint32_t a;GLint v;uint32_t b;}q{0x12345678,0x13572468,0x87654321};Run("tx_getparameteriv",{GL_TEXTURE_2D,GL_TEXTURE_MIN_LOD,reinterpret_cast<addr_t>(&q.v)});Check(q.v==expected&&q.a==0x12345678&&q.b==0x87654321&&!Error(),"S0 float transport/native conversion/tracked getter");
 GLint wrap=GL_CLAMP_TO_EDGE;Run("tx_parameteriv",{GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,reinterpret_cast<addr_t>(&wrap)});Run("tx_parameteriv",{GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,reinterpret_cast<addr_t>(&wrap)});Check(!Error(),"GLint input parameter");
 q.v=0x13572468;Run("tx_getparameteriv",{0,GL_TEXTURE_MIN_FILTER,reinterpret_cast<addr_t>(&q.v)});Check(Error()==GL_INVALID_ENUM&&q.v==0x13572468,"getter native error leaves guest output unchanged");
 auto Compare=[&](GLuint reference){Check(d.Sample(texture,program)==d.Sample(reference,program),"actual sampled texture equals independent native upload");d.glBindTexture(GL_TEXTURE_2D,texture);};
 std::array<uint8_t,256>source{};for(size_t i=0;i<source.size();++i)source[i]=uint8_t(i*37+11);
 for(GLint a:{1,2,4,8}){
  d.Unpack(a,5,1,1);d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_image",{GL_TEXTURE_2D,0,GL_RGB,3,2,0,GL_RGB,GL_UNSIGNED_BYTE,reinterpret_cast<addr_t>(source.data())});Check(!Error(),"RGB row/skip upload");auto ref=d.New();d.glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,3,2,0,GL_RGB,GL_UNSIGNED_BYTE,source.data());Check(d.glGetError()==GL_NO_ERROR,"native RGB upload");Compare(ref);d.glDeleteTextures(1,&ref);
 }
 d.Unpack(4,1,1,0);d.glPixelStorei(GL_UNPACK_SKIP_IMAGES,7);d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_image",{GL_TEXTURE_2D,0,GL_RGBA,3,2,0,GL_RGBA,GL_UNSIGNED_BYTE,reinterpret_cast<addr_t>(source.data()+1)});Check(!Error(),"overlapping rows and unaligned client pointer;2D ignores skipped images");auto overlapping=d.New();d.glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,3,2,0,GL_RGBA,GL_UNSIGNED_BYTE,source.data()+1);Compare(overlapping);d.glDeleteTextures(1,&overlapping);GLint still_rows=0,still_images=0;d.glGetIntegerv(GL_UNPACK_ROW_LENGTH,&still_rows);d.glGetIntegerv(GL_UNPACK_SKIP_IMAGES,&still_images);Check(still_rows==1&&still_images==7,"upload preserves caller unpack state");d.glPixelStorei(GL_UNPACK_SKIP_IMAGES,0);
 d.Unpack();d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_image_indirect",{GL_TEXTURE_2D,0,GL_RGBA,4,4,0,GL_RGBA,GL_UNSIGNED_BYTE,reinterpret_cast<addr_t>(source.data())});Check(!Error(),"indirect9GP image upload");auto ref=d.New();d.glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,4,4,0,GL_RGBA,GL_UNSIGNED_BYTE,source.data());Compare(ref);
 for(const char*n:{"tx_subimage","tx_subimage_indirect"}){d.glBindTexture(GL_TEXTURE_2D,texture);Run(n,{GL_TEXTURE_2D,0,1,1,2,2,GL_RGBA,GL_UNSIGNED_BYTE,reinterpret_cast<addr_t>(source.data()+64)});Check(!Error(),"subimage ninth argument");d.glBindTexture(GL_TEXTURE_2D,ref);d.glTexSubImage2D(GL_TEXTURE_2D,0,1,1,2,2,GL_RGBA,GL_UNSIGNED_BYTE,source.data()+64);Compare(ref);}d.glDeleteTextures(1,&ref);
 for(GLenum type:{GL_UNSIGNED_SHORT_5_6_5,GL_UNSIGNED_SHORT_4_4_4_4,GL_UNSIGNED_SHORT_5_5_5_1}){const auto format=type==GL_UNSIGNED_SHORT_5_6_5?GL_RGB:GL_RGBA;d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_image",{GL_TEXTURE_2D,0,addr_t(format),3,2,0,addr_t(format),type,reinterpret_cast<addr_t>(source.data())});Check(!Error(),"packed pixel upload");auto r=d.New();d.glTexImage2D(GL_TEXTURE_2D,0,format,3,2,0,format,type,source.data());Compare(r);d.glDeleteTextures(1,&r);}
 // No client access for allocation or zero-size; defined data is supplied before sampling.
 d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_image",{GL_TEXTURE_2D,0,GL_RGBA,4,4,0,GL_RGBA,GL_UNSIGNED_BYTE,0});Check(!Error(),"real NULL allocation");Run("tx_image",{GL_TEXTURE_2D,0,GL_RGBA,0,0,0,GL_RGBA,GL_UNSIGNED_BYTE,1});Check(!Error(),"zero-sized invalid-address upload reads no client bytes");Run("tx_image",{GL_TEXTURE_2D,0,GL_RGBA,addr_t(-1),1,0,GL_RGBA,GL_UNSIGNED_BYTE,1});Check(Error()==GL_INVALID_VALUE,"negative dimension native error without client read");
 SYSTEM_INFO si{};GetSystemInfo(&si);auto *pages=static_cast<uint8_t*>(VirtualAlloc(nullptr,size_t(si.dwPageSize)*2,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));Check(pages!=nullptr,"guard fixture storage");DWORD prior=0;Check(VirtualProtect(pages,si.dwPageSize,PAGE_NOACCESS,&prior)!=0,"unreadable skipped prefix");std::memcpy(pages+si.dwPageSize,source.data(),4);d.Unpack(4,GLint(si.dwPageSize/4),1,0); // RGBA row length => exact page stride.
 Run("tx_image",{GL_TEXTURE_2D,0,GL_RGBA,1,1,0,GL_RGBA,GL_UNSIGNED_BYTE,reinterpret_cast<addr_t>(pages)});Check(!Error(),"unreadable skipped prefix is not snapshotted");Check(VirtualProtect(pages,si.dwPageSize,PAGE_READWRITE,&prior)!=0,"restore prefix protection");Check(VirtualProtect(pages+si.dwPageSize,si.dwPageSize,PAGE_NOACCESS,&prior)!=0,"guard after final pixel row");std::memcpy(pages+si.dwPageSize-3,source.data(),3);d.Unpack(8);Run("tx_image",{GL_TEXTURE_2D,0,GL_RGB,1,1,0,GL_RGB,GL_UNSIGNED_BYTE,reinterpret_cast<addr_t>(pages+si.dwPageSize-3)});Check(!Error(),"no padding read after final RGB row");Check(VirtualFree(pages,0,MEM_RELEASE)!=0,"guard fixture released");
 d.Unpack();GLuint pbo=0;d.glGenBuffers(1,&pbo);d.glBindBuffer(GL_PIXEL_UNPACK_BUFFER,pbo);d.glBufferData(GL_PIXEL_UNPACK_BUFFER,source.size(),source.data(),GL_STATIC_DRAW);
 for(addr_t offset:{addr_t(0),addr_t(16)}){d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_image",{GL_TEXTURE_2D,0,GL_RGBA,4,4,0,GL_RGBA,GL_UNSIGNED_BYTE,offset});Check(!Error(),"PBO offset is not a client pointer");auto r=d.New();d.glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,4,4,0,GL_RGBA,GL_UNSIGNED_BYTE,reinterpret_cast<const void*>(offset));Compare(r);d.glDeleteTextures(1,&r);}
 d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_image",{GL_TEXTURE_2D,0,GL_RGBA,4,4,0,GL_RGBA,GL_UNSIGNED_BYTE,250});Check(Error()==GL_INVALID_OPERATION,"native PBO bounds error");Run("tx_image",{GL_TEXTURE_2D,0,GL_RGB,1,1,0,GL_RGB,GL_UNSIGNED_SHORT_5_6_5,1});Check(Error()==GL_INVALID_OPERATION,"native packed datum offset alignment");d.glBindBuffer(GL_PIXEL_UNPACK_BUFFER,0);d.glDeleteBuffers(1,&pbo);
 d.glBindTexture(GL_TEXTURE_2D,texture);d.Unpack(8,17,3,5);std::array<uint8_t,16>etc{};Run("tx_compressedimage",{GL_TEXTURE_2D,0,GL_COMPRESSED_RGB8_ETC2,4,4,0,8,reinterpret_cast<addr_t>(etc.data())});Check(!Error(),"compressed ignores poisoned unpack state");ref=d.New();d.glCompressedTexImage2D(GL_TEXTURE_2D,0,GL_COMPRESSED_RGB8_ETC2,4,4,0,8,etc.data());Compare(ref);d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_compressedsub",{GL_TEXTURE_2D,0,0,0,4,4,GL_COMPRESSED_RGB8_ETC2,8,reinterpret_cast<addr_t>(etc.data())});Check(!Error(),"compressed subimage ninth GP");Compare(ref);Run("tx_compressedsub",{GL_TEXTURE_2D,0,0,0,4,4,GL_COMPRESSED_RGB8_ETC2,7,reinterpret_cast<addr_t>(etc.data())});Check(Error()==GL_INVALID_VALUE,"compressed exact imageSize enforced natively");Run("tx_compressedimage",{GL_TEXTURE_2D,0,GL_COMPRESSED_RGB8_ETC2,4,4,0,addr_t(-1),1});Check(Error()==GL_INVALID_VALUE,"negative compressed size no client read");Run("tx_compressedimage",{GL_TEXTURE_2D,0,GL_COMPRESSED_RGB8_ETC2,4,4,0,8,0});Check(!Error(),"compressed null allocation");d.glDeleteTextures(1,&ref);
 d.glGenBuffers(1,&pbo);d.glBindBuffer(GL_PIXEL_UNPACK_BUFFER,pbo);d.glBufferData(GL_PIXEL_UNPACK_BUFFER,etc.size(),etc.data(),GL_STATIC_DRAW);
 // Pin native ANGLE behavior with the exact same poisoned unpack state. The
 // provider delegates buffer-offset validation; this is not a spec-conformance claim.
 for(bool clean:{false,true}){
  if(clean)d.Unpack();
  ref=d.New();d.glCompressedTexImage2D(GL_TEXTURE_2D,0,GL_COMPRESSED_RGB8_ETC2,4,4,0,8,reinterpret_cast<const void*>(uintptr_t(3)));const auto expected_pbo_error=d.glGetError();
  d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_compressedimage",{GL_TEXTURE_2D,0,GL_COMPRESSED_RGB8_ETC2,4,4,0,8,3});const auto actual_pbo_error=Error();
  std::printf("GL-TEXTURE-COMPRESSED-PBO clean=%u native_error=%#x provider_error=%#x\n",unsigned(clean),unsigned(expected_pbo_error),unsigned(actual_pbo_error));
  Check(actual_pbo_error==expected_pbo_error,"compressed PBO native error parity with identical unpack state");
  if(clean)Check(expected_pbo_error==GL_NO_ERROR,"clean compressed PBO offset3 accepted by native driver");
  if(expected_pbo_error==GL_NO_ERROR)Compare(ref);
  d.glDeleteTextures(1,&ref);
 }
 d.glBindBuffer(GL_PIXEL_UNPACK_BUFFER,0);d.glDeleteBuffers(1,&pbo);
 d.Unpack();d.glBindFramebuffer(GL_FRAMEBUFFER,0);d.glClearColor(0.25f,0.5f,0.75f,1);d.glClear(GL_COLOR_BUFFER_BIT);d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_copyimage",{GL_TEXTURE_2D,0,GL_RGBA,0,0,4,4,0});Check(!Error(),"actual framebuffer texture copy");ref=d.New();d.glCopyTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,0,0,4,4,0);Compare(ref);d.glBindFramebuffer(GL_FRAMEBUFFER,0);d.glClearColor(1,0,0,1);d.glClear(GL_COLOR_BUFFER_BIT);d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_copysub",{GL_TEXTURE_2D,0,1,1,0,0,2,2});Check(!Error(),"actual framebuffer subcopy");d.glBindTexture(GL_TEXTURE_2D,ref);d.glCopyTexSubImage2D(GL_TEXTURE_2D,0,1,1,0,0,2,2);Compare(ref);d.glDeleteTextures(1,&ref);
 d.glBindTexture(GL_TEXTURE_2D,texture);Run("tx_mipmap",{GL_TEXTURE_2D});Check(!Error(),"actual mip generation");GLuint fbo=0;d.glGenFramebuffers(1,&fbo);d.glBindFramebuffer(GL_FRAMEBUFFER,fbo);d.glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,1);Check(d.glCheckFramebufferStatus(GL_FRAMEBUFFER)==GL_FRAMEBUFFER_COMPLETE,"generated mip level is a real attachment");d.glBindFramebuffer(GL_FRAMEBUFFER,0);d.glDeleteFramebuffers(1,&fbo);
 // A preexisting native error must survive all internal unpack queries.
 d.glBindTexture(GL_TEXTURE_2D,texture);d.glTexParameteri(GL_TEXTURE_2D,0,0);Run("tx_image",{GL_TEXTURE_2D,0,GL_RGBA,1,1,0,GL_RGBA,GL_UNSIGNED_BYTE,reinterpret_cast<addr_t>(source.data())});Check(Error()==GL_INVALID_ENUM&&!Error(),"preexisting error survives upload internal queries once");
 Run("tx_delete",{1,reinterpret_cast<addr_t>(&texture)});Check(!Error(),"actual deletion input snapshot");d.glDeleteProgram(program);
 Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglTerminate",{display}),"owned EGL resources retired");egl.ReleaseCurrentThread();
 std::printf("GL-TEXTURE-PASS checks=%u calls=%u commands=14 real_ANGLE=1 synthetic_component=1\n",checks,calls);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"texture component: %s\n",e.what());return 1;}}

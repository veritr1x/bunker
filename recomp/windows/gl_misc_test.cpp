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
using namespace bunker::windows;
namespace {
unsigned checks=0,calls=0;GlHost*graphics=nullptr;
void Check(bool ok,const char*why){if(!ok)throw std::runtime_error(why);++checks;}
template<class F>F Native(HMODULE m,const char*n){auto p=GetProcAddress(m,n);if(!p)throw std::runtime_error(n);F f;std::memcpy(&f,&p,sizeof(f));return f;}
void*Resolve(const char*n){return reinterpret_cast<void*>(graphics->Marker(n));}
template<class H>addr_t Invoke(H&h,const char*n,std::initializer_list<addr_t>a={}){State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};size_t i=0;for(auto v:a)(s.gpr.*r[i++]).qword=v;h.Invoke(n,s);return s.gpr.x0.qword;}
struct Driver {
#define MISC_NATIVE(name,type) type name;
 MISC_NATIVE(glGetError,PFNGLGETERRORPROC) MISC_NATIVE(glGetIntegerv,PFNGLGETINTEGERVPROC)
 MISC_NATIVE(glCreateShader,PFNGLCREATESHADERPROC) MISC_NATIVE(glShaderSource,PFNGLSHADERSOURCEPROC)
 MISC_NATIVE(glCompileShader,PFNGLCOMPILESHADERPROC) MISC_NATIVE(glGetShaderiv,PFNGLGETSHADERIVPROC)
 MISC_NATIVE(glDeleteShader,PFNGLDELETESHADERPROC) MISC_NATIVE(glCreateProgram,PFNGLCREATEPROGRAMPROC)
 MISC_NATIVE(glAttachShader,PFNGLATTACHSHADERPROC) MISC_NATIVE(glLinkProgram,PFNGLLINKPROGRAMPROC)
 MISC_NATIVE(glGetProgramiv,PFNGLGETPROGRAMIVPROC) MISC_NATIVE(glDeleteProgram,PFNGLDELETEPROGRAMPROC)
 MISC_NATIVE(glGetActiveAttrib,PFNGLGETACTIVEATTRIBPROC) MISC_NATIVE(glGetAttribLocation,PFNGLGETATTRIBLOCATIONPROC)
 MISC_NATIVE(glGetShaderPrecisionFormat,PFNGLGETSHADERPRECISIONFORMATPROC) MISC_NATIVE(glGetShaderSource,PFNGLGETSHADERSOURCEPROC)
 MISC_NATIVE(glGetVertexAttribiv,PFNGLGETVERTEXATTRIBIVPROC) MISC_NATIVE(glVertexAttrib4f,PFNGLVERTEXATTRIB4FPROC)
 MISC_NATIVE(glVertexAttrib4fv,PFNGLVERTEXATTRIB4FVPROC) MISC_NATIVE(glValidateProgram,PFNGLVALIDATEPROGRAMPROC)
 MISC_NATIVE(glBlendEquation,PFNGLBLENDEQUATIONPROC) MISC_NATIVE(glStencilMask,PFNGLSTENCILMASKPROC)
#undef MISC_NATIVE
 Driver(){const auto m=GetModuleHandleW(L"libGLESv2.dll");
#define MISC_NATIVE(name,type) name=Native<type>(m,#name);
 MISC_NATIVE(glGetError,PFNGLGETERRORPROC) MISC_NATIVE(glGetIntegerv,PFNGLGETINTEGERVPROC)
 MISC_NATIVE(glCreateShader,PFNGLCREATESHADERPROC) MISC_NATIVE(glShaderSource,PFNGLSHADERSOURCEPROC)
 MISC_NATIVE(glCompileShader,PFNGLCOMPILESHADERPROC) MISC_NATIVE(glGetShaderiv,PFNGLGETSHADERIVPROC)
 MISC_NATIVE(glDeleteShader,PFNGLDELETESHADERPROC) MISC_NATIVE(glCreateProgram,PFNGLCREATEPROGRAMPROC)
 MISC_NATIVE(glAttachShader,PFNGLATTACHSHADERPROC) MISC_NATIVE(glLinkProgram,PFNGLLINKPROGRAMPROC)
 MISC_NATIVE(glGetProgramiv,PFNGLGETPROGRAMIVPROC) MISC_NATIVE(glDeleteProgram,PFNGLDELETEPROGRAMPROC)
 MISC_NATIVE(glGetActiveAttrib,PFNGLGETACTIVEATTRIBPROC) MISC_NATIVE(glGetAttribLocation,PFNGLGETATTRIBLOCATIONPROC)
 MISC_NATIVE(glGetShaderPrecisionFormat,PFNGLGETSHADERPRECISIONFORMATPROC) MISC_NATIVE(glGetShaderSource,PFNGLGETSHADERSOURCEPROC)
 MISC_NATIVE(glGetVertexAttribiv,PFNGLGETVERTEXATTRIBIVPROC) MISC_NATIVE(glVertexAttrib4f,PFNGLVERTEXATTRIB4FPROC)
 MISC_NATIVE(glVertexAttrib4fv,PFNGLVERTEXATTRIB4FVPROC) MISC_NATIVE(glValidateProgram,PFNGLVALIDATEPROGRAMPROC)
 MISC_NATIVE(glBlendEquation,PFNGLBLENDEQUATIONPROC) MISC_NATIVE(glStencilMask,PFNGLSTENCILMASKPROC)
#undef MISC_NATIVE
 }
 GLuint Shader(GLenum type,const char*text){auto s=glCreateShader(type);glShaderSource(s,1,&text,nullptr);glCompileShader(s);GLint ok=0;glGetShaderiv(s,GL_COMPILE_STATUS,&ok);Check(ok!=0,"native shader setup");return s;}
};
template<class T,size_t N>struct Guard {uint32_t before=0x12345678;std::array<T,N> values;uint32_t after=0x87654321;Guard(){std::memset(values.data(),0x5a,sizeof(values));}bool Safe()const{return before==0x12345678&&after==0x87654321;}};
}
int main(){try{
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(90));std::fputs("misc component watchdog\n",stderr);std::_Exit(95);}).detach();
 bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;EglHost egl(windows,GL_MISC_DLL_DIRECTORY);egl.Install(runtime);GlHost gl(egl,GL_MISC_DLL_DIRECTORY);graphics=&gl;gl.Install(runtime);
 auto display=Invoke(egl,"eglGetDisplay");Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"real ANGLE display");const GLint attrs[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,EGL_NONE};addr_t config=0;GLint count=0;Check(Invoke(egl,"eglChooseConfig",{display,reinterpret_cast<addr_t>(attrs),reinterpret_cast<addr_t>(&config),1,reinterpret_cast<addr_t>(&count)})&&count==1,"real GLES3 configuration");const GLint ca[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_CONTEXT_MINOR_VERSION,1,EGL_NONE},sa[]={EGL_WIDTH,8,EGL_HEIGHT,8,EGL_NONE};auto context=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(ca)});auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,reinterpret_cast<addr_t>(sa)});Check(context&&surface&&Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"real GLES3.1 current context");
 Driver d;elf_image image{};Check(!elf_load(GL_MISC_IMAGE,0x5e000000,Resolve,&image),"actual original NDK misc callers");runtime.AddTraces(kTraces,std::size(kTraces));
 auto Run=[&](const char*name,std::initializer_list<addr_t>arguments={},const std::array<GLfloat,4>*fp=nullptr){alignas(16)std::array<uint8_t,65536>stack{};State s{};const auto sp=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.sp.qword=sp;s.gpr.x19.qword=0x123456789abcdef0ULL;s.gpr.x30.qword=0xfeedffff;Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t i=0;for(auto v:arguments)(s.gpr.*r[i++]).qword=v;if(fp)for(size_t n=0;n<4;++n)std::memcpy(&s.simd.v[n],&(*fp)[n],4);const auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(entry!=0,"NDK misc wrapper export");auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));Check(runtime.Run(s,entry,token)==token&&s.gpr.sp.qword==sp&&s.gpr.x19.qword==0x123456789abcdef0ULL&&s.gpr.x30.qword==0xfeedffff&&s.gpr.pc.qword==0xfeedffff,"NDK SP/LR/callee register/token");++calls;return s.gpr.x0.dword;};
 auto Error=[&](){return GLenum(Invoke(gl,"glGetError"));};
 // Root appends groups in a fixed order; no new group base is assumed here.
 const char*old_names[]={"glGetString","glGetStringi","glGetIntegerv","glGetFloatv","glGetBooleanv","glGetError","glActiveTexture","glEnable","glDisable","glIsEnabled","glViewport","glScissor","glClearColor","glClearDepthf","glClearStencil","glClear","glColorMask","glDepthMask","glDepthFunc","glDepthRangef","glStencilMaskSeparate","glStencilFuncSeparate","glStencilOpSeparate","glBlendColor","glBlendEquationSeparate","glBlendFuncSeparate","glCullFace","glFrontFace","glPolygonOffset","glSampleCoverage","glLineWidth","glHint","glFlush","glFinish","glCreateShader","glShaderSource","glCompileShader","glGetShaderiv","glGetShaderInfoLog","glDeleteShader","glCreateProgram","glAttachShader","glDetachShader","glLinkProgram","glGetProgramiv","glGetProgramInfoLog","glUseProgram","glDeleteProgram","glGenBuffers","glBindBuffer","glBufferData","glBufferSubData","glDeleteBuffers","glGenVertexArrays","glBindVertexArray","glDeleteVertexArrays","glEnableVertexAttribArray","glDisableVertexAttribArray","glVertexAttribPointer","glDrawArrays","glDrawElements","glReadPixels","glPixelStorei"};
 Check(GlHost::Commands().size()>=74,"old prefix and additive misc catalog");for(size_t i=0;i<63;++i)Check(GlHost::Commands()[i]==old_names[i]&&gl.Marker(old_names[i])==gl.Marker(old_names[0])+i*8,"all original63 marker indices unchanged");
#define GL_MISC_COMMAND(name,type) Check(gl.Marker(#name)!=0,"dynamic misc marker: " #name);
#include "gl_misc_commands.inc"
#undef GL_MISC_COMMAND
 const char*vs="#version 300 es\nin vec4 positionVector;void main(){gl_Position=positionVector;}";const char*fs="#version 300 es\nprecision highp float;out vec4 c;void main(){c=vec4(1.0);}";auto vertex=d.Shader(GL_VERTEX_SHADER,vs),fragment=d.Shader(GL_FRAGMENT_SHADER,fs);auto program=d.glCreateProgram();d.glAttachShader(program,vertex);d.glAttachShader(program,fragment);Run("mx_bind",{program,3,reinterpret_cast<addr_t>("positionVector")});d.glLinkProgram(program);GLint linked=0;d.glGetProgramiv(program,GL_LINK_STATUS,&linked);Check(linked&&!Error(),"real bind attrib location before native link");Check(Run("mx_location",{program,reinterpret_cast<addr_t>("positionVector")})==3,"real signed GLint attribute location");Check(int32_t(Run("mx_location",{program,reinterpret_cast<addr_t>("notActive")}))==-1&&!Error(),"missing active name remains-1 without GL error");
 for(GLsizei cap:{0,1,5,64}){
  Guard<GLchar,64>actual,expected;Guard<GLint,1>as,es;Guard<GLenum,1>at,et;Guard<GLsizei,1>al,el;
  d.glGetActiveAttrib(program,0,cap,el.values.data(),es.values.data(),et.values.data(),cap?expected.values.data():nullptr);Check(d.glGetError()==GL_NO_ERROR,"native active attrib oracle");Run("mx_active",{program,0,addr_t(cap),reinterpret_cast<addr_t>(al.values.data()),reinterpret_cast<addr_t>(as.values.data()),reinterpret_cast<addr_t>(at.values.data()),cap?reinterpret_cast<addr_t>(actual.values.data()):0});
  Check(!Error()&&actual.values==expected.values&&as.values==es.values&&at.values==et.values&&al.values==el.values&&actual.Safe()&&as.Safe()&&at.Safe()&&al.Safe(),"active attrib0/truncated/full names and native untouched length semantics");
 }
 Guard<GLint,1>size;Guard<GLenum,1>type;Guard<GLchar,32>name;Run("mx_active",{program,0,32,0,reinterpret_cast<addr_t>(size.values.data()),reinterpret_cast<addr_t>(type.values.data()),reinterpret_cast<addr_t>(name.values.data())});Check(!Error()&&!std::strcmp(name.values.data(),"positionVector")&&name.Safe()&&size.Safe()&&type.Safe(),"active attribute optional length");auto old_name=name;auto old_size=size;auto old_type=type;Run("mx_active",{program,999,32,0,reinterpret_cast<addr_t>(size.values.data()),reinterpret_cast<addr_t>(type.values.data()),reinterpret_cast<addr_t>(name.values.data())});Check(Error()==GL_INVALID_VALUE&&name.values==old_name.values&&size.values==old_size.values&&type.values==old_type.values,"invalid index leaves all attribute outputs untouched");
 for(GLsizei cap:{0,1,7,128}){Guard<GLchar,128>a,e;Guard<GLsizei,1>al,el;d.glGetShaderSource(vertex,cap,el.values.data(),cap?e.values.data():nullptr);Check(d.glGetError()==GL_NO_ERROR,"native shader source oracle");Run("mx_source",{vertex,addr_t(cap),reinterpret_cast<addr_t>(al.values.data()),cap?reinterpret_cast<addr_t>(a.values.data()):0});Check(!Error()&&a.values==e.values&&al.values==el.values&&a.Safe()&&al.Safe(),"source zero/truncated/full exact helper behavior");}
 Guard<GLchar,16>optional_source,expected_source;d.glGetShaderSource(vertex,16,nullptr,expected_source.values.data());Check(d.glGetError()==GL_NO_ERROR,"native optional source length oracle");Run("mx_source",{vertex,16,0,reinterpret_cast<addr_t>(optional_source.values.data())});Check(!Error()&&optional_source.values==expected_source.values&&optional_source.Safe(),"source optional length preserves name output");
 Guard<GLchar,16>unchanged;auto original=unchanged;Run("mx_source",{0,16,0,reinterpret_cast<addr_t>(unchanged.values.data())});Check(Error()!=GL_NO_ERROR&&unchanged.values==original.values&&unchanged.Safe(),"bad shader does not publish source");Run("mx_source",{vertex,addr_t(-1),0,reinterpret_cast<addr_t>(unchanged.values.data())});Check(Error()==GL_INVALID_VALUE&&unchanged.values==original.values,"negative source capacity native error");
 for(GLenum shader:{GL_VERTEX_SHADER,GL_FRAGMENT_SHADER})for(GLenum precision:{GL_LOW_FLOAT,GL_MEDIUM_FLOAT,GL_HIGH_FLOAT,GL_LOW_INT,GL_MEDIUM_INT,GL_HIGH_INT}){Guard<GLint,2>ar,er;Guard<GLint,1>ap,ep;d.glGetShaderPrecisionFormat(shader,precision,er.values.data(),ep.values.data());Check(d.glGetError()==GL_NO_ERROR,"native precision oracle");Run("mx_precision",{shader,precision,reinterpret_cast<addr_t>(ar.values.data()),reinterpret_cast<addr_t>(ap.values.data())});Check(!Error()&&ar.values==er.values&&ap.values==ep.values&&ar.Safe()&&ap.Safe(),"12precision modes exact8+4 byte tracked outputs");}
 for(unsigned which=0;which<3;++which){Guard<GLint,2>range;Guard<GLint,1>precision;const auto r=range;const auto p=precision;Run("mx_precision",{GL_VERTEX_SHADER,GL_HIGH_FLOAT,which==0||which==2?0:reinterpret_cast<addr_t>(range.values.data()),which==1||which==2?0:reinterpret_cast<addr_t>(precision.values.data())});Check(Error()==GL_INVALID_VALUE&&range.values==r.values&&precision.values==p.values,"native NULL precision validation with no partial publication");}
 Check(int32_t(Run("mx_location",{program,0}))==-1&&Error()==GL_INVALID_VALUE,"NULL attrib location native-1/error");Run("mx_bind",{program,3,0});Check(Error()==GL_INVALID_VALUE,"NULL bind name native error");Run("mx_bind",{program,3,reinterpret_cast<addr_t>("gl_reserved")});Check(Error()==GL_INVALID_OPERATION,"reserved attribute name native error");
 const std::array<GLfloat,4>values{1.25f,-2.5f,3.75f,4.5f};d.glVertexAttrib4f(4,values[0],values[1],values[2],values[3]);GLint expected_values[4]{};d.glGetVertexAttribiv(4,GL_CURRENT_VERTEX_ATTRIB,expected_values);Check(d.glGetError()==GL_NO_ERROR,"native current attribute conversion oracle");
 for(const char*wrapper:{"mx_vertex4f","mx_vertex4f_indirect"}){Run(wrapper,{3},&values);Guard<GLint,6>out;Run("mx_vertex",{3,GL_CURRENT_VERTEX_ATTRIB,reinterpret_cast<addr_t>(out.values.data())});Check(!Error()&&!std::memcmp(out.values.data(),expected_values,16)&&out.values[4]==0x5a5a5a5a&&out.values[5]==0x5a5a5a5a&&out.Safe(),"S0..S3 float ABI + current attribute exact16B getter");}
 auto owned=values;Run("mx_vertex4fv",{3,reinterpret_cast<addr_t>(owned.data())});owned.fill(0);Guard<GLint,6>vector;Run("mx_vertex",{3,GL_CURRENT_VERTEX_ATTRIB,reinterpret_cast<addr_t>(vector.values.data())});Check(!Error()&&!std::memcmp(vector.values.data(),expected_values,16)&&vector.values[4]==0x5a5a5a5a&&vector.values[5]==0x5a5a5a5a&&vector.Safe(),"fv snapshots16bytes; no retained client pointer");
 for(GLenum pname:{GL_VERTEX_ATTRIB_ARRAY_BUFFER_BINDING,GL_VERTEX_ATTRIB_ARRAY_ENABLED,GL_VERTEX_ATTRIB_ARRAY_SIZE,GL_VERTEX_ATTRIB_ARRAY_STRIDE,GL_VERTEX_ATTRIB_ARRAY_TYPE,GL_VERTEX_ATTRIB_ARRAY_NORMALIZED,GL_VERTEX_ATTRIB_ARRAY_INTEGER,GL_VERTEX_ATTRIB_ARRAY_DIVISOR,GL_VERTEX_ATTRIB_BINDING,GL_VERTEX_ATTRIB_RELATIVE_OFFSET}){GLint e=0;d.glGetVertexAttribiv(3,pname,&e);Check(d.glGetError()==GL_NO_ERROR,"native scalar vertex oracle");Guard<GLint,3>out;Run("mx_vertex",{3,pname,reinterpret_cast<addr_t>(out.values.data())});Check(!Error()&&out.values[0]==e&&out.values[1]==0x5a5a5a5a&&out.values[2]==0x5a5a5a5a&&out.Safe(),"scalar vertex query writes exactly4B");}
 GLint maximum=0;d.glGetIntegerv(GL_MAX_VERTEX_ATTRIBS,&maximum);Run("mx_vertex4fv",{3,0});Check(Error()==GL_INVALID_VALUE,"native NULL fv validation");Run("mx_vertex4fv",{addr_t(maximum),reinterpret_cast<addr_t>(values.data())});Check(Error()==GL_INVALID_VALUE,"invalid vertex index native error");Guard<GLint,4>bad;auto bad_before=bad;Run("mx_vertex",{addr_t(maximum),GL_CURRENT_VERTEX_ATTRIB,reinterpret_cast<addr_t>(bad.values.data())});Check(Error()==GL_INVALID_VALUE&&bad.values==bad_before.values,"bad vertex index writes nothing");
 Run("mx_blend",{GL_FUNC_REVERSE_SUBTRACT});GLint rgb=0,alpha=0;d.glGetIntegerv(GL_BLEND_EQUATION_RGB,&rgb);d.glGetIntegerv(GL_BLEND_EQUATION_ALPHA,&alpha);Check(!Error()&&rgb==GL_FUNC_REVERSE_SUBTRACT&&alpha==rgb,"blend equation changes actual RGB and alpha state");Run("mx_blend",{0});Check(Error()==GL_INVALID_ENUM,"blend invalid enum delegated");Run("mx_stencil",{UINT64_C(0x12345678f0f0f0f0)});GLint front=0,back=0;d.glGetIntegerv(GL_STENCIL_WRITEMASK,&front);d.glGetIntegerv(GL_STENCIL_BACK_WRITEMASK,&back);Check(!Error()&&uint32_t(front)==0xf0f0f0f0&&back==front,"GLuint low32 stencil updates front/back native state");
 d.glValidateProgram(program);GLint validation=0;d.glGetProgramiv(program,GL_VALIDATE_STATUS,&validation);Check(d.glGetError()==GL_NO_ERROR,"native validation oracle");Run("mx_validate",{program});GLint actual_validation=0;d.glGetProgramiv(program,GL_VALIDATE_STATUS,&actual_validation);Check(!Error()&&actual_validation==validation,"actual program validation result, not invented success");d.glValidateProgram(0);const auto expected_error=d.glGetError();Run("mx_validate",{0});Check(Error()==expected_error,"invalid program native error");
 d.glBlendEquation(0);Guard<GLint,1>pending;Run("mx_vertex",{3,GL_VERTEX_ATTRIB_ARRAY_SIZE,reinterpret_cast<addr_t>(pending.values.data())});Check(Error()==GL_INVALID_ENUM&&!Error(),"internal query preserves pending error until consumed once");
 d.glDeleteProgram(program);d.glDeleteShader(vertex);d.glDeleteShader(fragment);Check(d.glGetError()==GL_NO_ERROR,"native oracle setup resources retired");Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglTerminate",{display}),"owned EGL resources retired");egl.ReleaseCurrentThread();std::printf("GL-MISC-PASS checks=%u calls=%u commands=11 real_ANGLE=1 synthetic_component=1\n",checks,calls);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"misc component: %s\n",e.what());return 1;}}

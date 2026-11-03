#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl31.h>
#include "gl_host.h"
#include "egl_host.h"
#include "gles_service_module.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "gl_uniform_old_commands.h"
#include <array>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <stdexcept>
using namespace bunker::windows;
namespace {
unsigned checks=0;EglHost*egl_provider;
void Check(bool b,const char*m){if(!b)throw std::runtime_error(m);++checks;}
template<class F>F Native(HMODULE m,const char*n){auto p=GetProcAddress(m,n);Check(p!=nullptr,"native symbol");F f;std::memcpy(&f,&p,sizeof(f));return f;}
template<class H>addr_t Invoke(H&h,const char*n,std::initializer_list<addr_t>a={}){State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};unsigned i=0;for(auto v:a)(s.gpr.*r[i++]).qword=v;h.Invoke(n,s);return s.gpr.x0.qword;}
void*Resolve(const char*n){Check(!std::strcmp(n,"eglGetProcAddress"),"only typed EGL resolver import");return reinterpret_cast<void*>(egl_provider->Marker(n));}
struct Guard {
 uint8_t*base=nullptr;size_t page=0,size=0;
 explicit Guard(size_t bytes):size(bytes){SYSTEM_INFO s;GetSystemInfo(&s);page=s.dwPageSize;Check(bytes<=page-32,"guard fixture span");base=static_cast<uint8_t*>(VirtualAlloc(nullptr,page*2,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));Check(base!=nullptr,"real guarded allocation");std::memset(base,0xa5,page);DWORD old=0;Check(VirtualProtect(base+page,page,PAGE_NOACCESS,&old)!=0,"real noaccess tail");}
 ~Guard(){if(base)VirtualFree(base,0,MEM_RELEASE);}Guard(const Guard&)=delete;Guard&operator=(const Guard&)=delete;
 void*data(){return base+page-size;}addr_t address(){return reinterpret_cast<addr_t>(data());}addr_t inaccessible(){return reinterpret_cast<addr_t>(base+page);}
 void prefix(){Check(std::all_of(base,base+page-size,[](uint8_t b){return b==0xa5;}),"uniform transfer did not touch prefix");}
};
const char*vs=R"(#version 300 es
precision highp float;precision highp int;
uniform float uf;uniform vec2 uf2;uniform vec3 uf3[3];uniform vec4 uf4;
uniform int ui;uniform ivec2 ui2;uniform ivec3 ui3[3];uniform ivec4 ui4;
uniform bool ub;uniform bvec2 ub2;uniform bvec3 ub3;uniform bvec4 ub4;
uniform mat2 um2;uniform mat3 um3[2];uniform mat4 um4[2];
struct S{vec3 value;};uniform S us[2];
void main(){vec3 f=uf3[0]+uf3[1]+uf3[2]+vec3(ui3[0]+ui3[1]+ui3[2])+us[0].value+us[1].value;
float b=(ub?1.0:0.0)+(any(ub2)?1.0:0.0)+(any(ub3)?1.0:0.0)+(any(ub4)?1.0:0.0);
gl_Position=vec4(f+vec3(uf+uf2.x+float(ui)+float(ui2.x)+b+um2[0][0]),1.0)+uf4+vec4(ui4)+vec4(um3[0][0]+um3[1][2],0.0)+um4[0][0]+um4[1][3];})";
const char*fs=R"(#version 300 es
precision highp float;uniform sampler2D tex[2];out vec4 color;
void main(){color=texture(tex[0],vec2(0.25))+texture(tex[1],vec2(0.75));})";
}
int main(){try{
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(90));std::_Exit(95);}).detach();
 bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;EglHost egl(windows,GL_UNIFORM_DLL_DIRECTORY);egl_provider=&egl;egl.Install(runtime);GlHost gl(egl,GL_UNIFORM_DLL_DIRECTORY);gl.Install(runtime);egl.SetProcedureResolver([&](const std::string&n){return FindTypedGlesProcedure(gl,n);});
 auto display=Invoke(egl,"eglGetDisplay",{0});Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"ANGLE initializes");const int attrs[]={0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3033,1,0x3040,0x40,0x3038};addr_t config=0;int count=0;Check(Invoke(egl,"eglChooseConfig",{display,reinterpret_cast<addr_t>(attrs),reinterpret_cast<addr_t>(&config),1,reinterpret_cast<addr_t>(&count)})&&count==1,"pbuffer config");const int ca[]={0x3098,3,0x30fb,1,0x3038},sa[]={0x3057,8,0x3056,8,0x3038};auto context=Invoke(egl,"eglCreateContext",{display,config,0,reinterpret_cast<addr_t>(ca)});auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,reinterpret_cast<addr_t>(sa)});Check(context&&surface&&Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"real current context");
 Check(std::size(kOldUniformCommands)==63&&GlHost::Commands().size()>=63,"old command catalog bound");for(size_t i=0;i<63;++i)Check(GlHost::Commands()[i]==kOldUniformCommands[i]&&gl.Marker(kOldUniformCommands[i])==gl.Marker("glGetString")+i*8,"old63 names and marker offsets exact");
 auto module=GetModuleHandleW(L"libGLESv2.dll");
#define GL_UNIFORM_COMMAND(name,type) auto name=Native<type>(module,#name);Check(FindTypedGlesProcedure(gl,#name)==gl.Marker(#name),"new typed uniform marker resolves");
#include "gl_uniform_commands.inc"
#undef GL_UNIFORM_COMMAND
 auto error=Native<PFNGLGETERRORPROC>(module,"glGetError");auto use=Native<PFNGLUSEPROGRAMPROC>(module,"glUseProgram");auto getfv=Native<PFNGLGETUNIFORMFVPROC>(module,"glGetUniformfv");auto getProgram=Native<PFNGLGETPROGRAMIVPROC>(module,"glGetProgramiv");auto create=Native<PFNGLCREATESHADERPROC>(module,"glCreateShader");auto source=Native<PFNGLSHADERSOURCEPROC>(module,"glShaderSource");auto compile=Native<PFNGLCOMPILESHADERPROC>(module,"glCompileShader");auto getShader=Native<PFNGLGETSHADERIVPROC>(module,"glGetShaderiv");auto createProgram=Native<PFNGLCREATEPROGRAMPROC>(module,"glCreateProgram");auto attach=Native<PFNGLATTACHSHADERPROC>(module,"glAttachShader");auto link=Native<PFNGLLINKPROGRAMPROC>(module,"glLinkProgram");auto deleteProgram=Native<PFNGLDELETEPROGRAMPROC>(module,"glDeleteProgram");auto deleteShader=Native<PFNGLDELETESHADERPROC>(module,"glDeleteShader");auto matrix2=Native<PFNGLUNIFORMMATRIX2FVPROC>(module,"glUniformMatrix2fv");
 auto Program=[&](){auto v=create(GL_VERTEX_SHADER),f=create(GL_FRAGMENT_SHADER);source(v,1,&vs,nullptr);source(f,1,&fs,nullptr);compile(v);compile(f);GLint ok=0;getShader(v,GL_COMPILE_STATUS,&ok);Check(ok!=0,"vertex shader compiled");getShader(f,GL_COMPILE_STATUS,&ok);Check(ok!=0,"fragment shader compiled");auto p=createProgram();attach(p,v);attach(p,f);link(p);getProgram(p,GL_LINK_STATUS,&ok);Check(ok!=0&&error()==0,"independent program linked");deleteShader(v);deleteShader(f);return p;};auto A=Program(),B=Program();
 elf_image image{};Check(!elf_load(GL_UNIFORM_IMAGE,0x5c000000,Resolve,&image),"actual NDK uniform caller");runtime.AddTraces(kTraces,std::size(kTraces));
 auto Run=[&](const char*name,std::initializer_list<addr_t>a={}){alignas(16)std::array<uint8_t,65536>stack{};State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};unsigned i=0;for(auto v:a)(s.gpr.*r[i++]).qword=v;s.gpr.x19.qword=0x123456789abcdef0ULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));auto result=runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)),token);Check(result==token&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.pc.qword==0xfeedffff&&s.gpr.x19.qword==0x123456789abcdef0ULL,"NDK token/SP/PC/callee preservation");return s.gpr.x0.qword;};
 auto Err=[&](GLenum expected){Check(Run("uniform_error")==expected&&Run("uniform_error")==GL_NO_ERROR,"native/guest error and single clear match");};
 auto Location=[&](GLuint p,const char*n){GLint native=glGetUniformLocation(p,n);Check(error()==0,"native location");auto actual=Run("uniform_location",{p,reinterpret_cast<addr_t>(n)});Check(int32_t(uint32_t(actual))==native,"signed location matches native including minus1");Err(0);return native;};
 auto Compare=[&](const char*n,unsigned components,bool floating){auto la=glGetUniformLocation(A,n),lb=glGetUniformLocation(B,n);Check(la>=0&&lb>=0,"active comparison locations");GLint expected[16]{};glGetUniformiv(B,lb,expected);Check(error()==0,"native integer uniform oracle");Guard out(components*4);Check(Run("uniform_get",{A,uint32_t(la),out.address()})==0,"NDK uniform getter");Err(0);Check(!std::memcmp(out.data(),expected,components*4),"exact one-element integer conversion/width");out.prefix();if(floating){GLfloat left[16]{},right[16]{};getfv(A,la,left);getfv(B,lb,right);Check(error()==0&&!std::memcmp(left,right,components*4),"guest update vs independent native program float bits");}};
 GLint active=0,maxname=0;getProgram(A,GL_ACTIVE_UNIFORMS,&active);getProgram(A,GL_ACTIVE_UNIFORM_MAX_LENGTH,&maxname);Check(active>0&&maxname>0&&error()==0,"active uniform metadata");
 for(GLuint index=0;index<GLuint(active);++index){char expected[256]{};GLsizei length=0;GLint size=0;GLenum type=0;glGetActiveUniform(A,index,sizeof(expected),&length,&size,&type,expected);Check(error()==0,"native active metadata");for(GLsizei cap:{0,1,5,256}){Guard name{size_t(cap)};struct{uint32_t before;GLsizei length;GLint size;GLenum type;uint32_t after;}out{0x12345678,-7,-8,0xffffffff,0x87654321};Check(Run("uniform_active",{A,index,uint32_t(cap),reinterpret_cast<addr_t>(&out.length),reinterpret_cast<addr_t>(&out.size),reinterpret_cast<addr_t>(&out.type),cap?name.address():name.inaccessible()})==0,"seven-argument NDK metadata call");Err(0);GLsizei native_length=-7;GLint native_size=-8;GLenum native_type=0xffffffff;char native_name[256];std::memset(native_name,0xa5,sizeof(native_name));glGetActiveUniform(A,index,cap,&native_length,&native_size,&native_type,native_name);Check(error()==0,"native per-capacity active oracle including zero");Check(out.before==0x12345678&&out.after==0x87654321&&out.length==native_length&&out.size==native_size&&out.type==native_type,"metadata lengths/types/canaries exact native");if(cap)Check(!std::memcmp(name.data(),native_name,size_t(cap)),"truncated active name plus NUL and untouched tail exact native");name.prefix();}Location(A,expected);}

 for(auto spec:std::array<std::pair<GLuint,GLsizei>,2>{{{GLuint(active),8},{0,-1}}}){
   Guard name(16);struct {GLsizei length;GLint size;GLenum type;} data{-7,-8,0xffffffff};auto original=data;GLsizei nl=-1;GLint ns=-1;GLenum nt=0;char scratch[16]{};glGetActiveUniform(A,spec.first,spec.second,&nl,&ns,&nt,scratch);auto expected_error=error();
   Check(Run("uniform_active",{A,spec.first,uint32_t(spec.second),reinterpret_cast<addr_t>(&data.length),reinterpret_cast<addr_t>(&data.size),reinterpret_cast<addr_t>(&data.type),name.address()})==0,"invalid active query normal bridge return");Err(expected_error);Check(!std::memcmp(&data,&original,sizeof(data))&&std::all_of(static_cast<uint8_t*>(name.data()),static_cast<uint8_t*>(name.data())+16,[](uint8_t b){return b==0xa5;}),"invalid active query publishes nothing");name.prefix();
 }
 Check(Location(A,"not_present_uniform")==-1,"inactive location minus1");
 auto unlinked=createProgram();for(GLuint program:{A,unlinked}){auto native_null=glGetUniformLocation(program,nullptr);auto expected_error=error();auto actual=Run("uniform_location",{program,0});Check(int32_t(uint32_t(actual))==native_null,"literal NULL location return matches native before program/link validation");Err(expected_error);}deleteProgram(unlinked);Check(error()==0,"unlinked probe program retired");
 const GLfloat fv[]={0.25f,-1.5f,2.75f,4.0f,5.5f,-6.25f,7.0f,8.5f,9.25f,10.0f,11.0f,12.0f};const GLint iv[]={-3,0,5,7,11,-13,17,19,23,29,31,37};
 auto Float=[&](const char*guest,const char*n,unsigned width,GLsizei c,auto fn,size_t copied){auto la=Location(A,n),lb=glGetUniformLocation(B,n);Guard input(copied*width*4);std::memcpy(input.data(),fv,copied*width*4);use(B);fn(lb,c,static_cast<const GLfloat*>(input.data()));auto expected=error();use(A);Check(Run(guest,{uint32_t(la),uint32_t(c),input.address()})==0,"NDK float upload");Err(expected);Check(!std::memcmp(input.data(),fv,copied*width*4),"float input unchanged");input.prefix();};
 Float("uniform_1fv","uf",1,1,glUniform1fv,1);Compare("uf",1,true);Float("uniform_2fv","uf2",2,1,glUniform2fv,1);Compare("uf2",2,true);Float("uniform_3fv","uf3[0]",3,3,glUniform3fv,3);Float("uniform_3fv","uf3[1]",3,3,glUniform3fv,2);for(const char*n:{"uf3[0]","uf3[1]","uf3[2]"})Compare(n,3,true);Float("uniform_4fv","uf4",4,1,glUniform4fv,1);Compare("uf4",4,true);
 auto Int=[&](const char*guest,const char*n,unsigned width,GLsizei c,auto fn,size_t copied,const GLint*values){auto la=Location(A,n),lb=glGetUniformLocation(B,n);Guard input(copied*width*4);std::memcpy(input.data(),values,copied*width*4);use(B);fn(lb,c,static_cast<const GLint*>(input.data()));auto expected=error();use(A);Check(Run(guest,{uint32_t(la),uint32_t(c),input.address()})==0,"NDK integer upload");Err(expected);Check(!std::memcmp(input.data(),values,copied*width*4),"integer input unchanged");input.prefix();};
 Int("uniform_1iv","ui",1,1,glUniform1iv,1,iv);Compare("ui",1,false);Int("uniform_2iv","ui2",2,1,glUniform2iv,1,iv);Compare("ui2",2,false);Int("uniform_3iv","ui3[0]",3,3,glUniform3iv,3,iv);Int("uniform_3iv","ui3[1]",3,3,glUniform3iv,2,iv);for(const char*n:{"ui3[0]","ui3[1]","ui3[2]"})Compare(n,3,false);Int("uniform_4iv","ui4",4,1,glUniform4iv,1,iv);Compare("ui4",4,false);
 Int("uniform_1iv","ub",1,1,glUniform1iv,1,iv);Compare("ub",1,false);Float("uniform_2fv","ub2",2,1,glUniform2fv,1);Compare("ub2",2,false);Int("uniform_3iv","ub3",3,1,glUniform3iv,1,iv);Compare("ub3",3,false);Float("uniform_4fv","ub4",4,1,glUniform4fv,1);Compare("ub4",4,false);
 auto la=Location(A,"ui"),lb=glGetUniformLocation(B,"ui");use(B);glUniform1i(lb,-123);Check(error()==0,"native scalar integer");use(A);Check(Run("uniform_scalar",{uint32_t(la),uint32_t(-123)})==0,"NDK signed scalar upload");Err(0);Compare("ui",1,false);
 const GLint samplers[]={0,1,2};Int("uniform_1iv","tex[0]",1,2,glUniform1iv,2,samplers);Int("uniform_1iv","tex[1]",1,3,glUniform1iv,3,samplers);Compare("tex[0]",1,false);Compare("tex[1]",1,false);const GLint badsamplers[]={1,0x7fffffff};Int("uniform_1iv","tex[1]",1,2,glUniform1iv,2,badsamplers);Compare("tex[1]",1,false);
 GLfloat matrices[32];for(unsigned i=0;i<32;++i)matrices[i]=float(int(i)-8)*0.25f;
 auto Matrix=[&](const char*guest,const char*n,unsigned dim,GLboolean transpose,auto fn){auto a=Location(A,n),b=glGetUniformLocation(B,n);Guard input(dim*dim*4);std::memcpy(input.data(),matrices,dim*dim*4);use(B);fn(b,3,transpose,static_cast<const GLfloat*>(input.data()));auto expected=error();use(A);Check(Run(guest,{uint32_t(a),3,transpose,input.address()})==0,"NDK clipped matrix array");Err(expected);Compare(n,dim*dim,true);};Matrix("uniform_matrix3","um3[1]",3,GL_FALSE,glUniformMatrix3fv);Matrix("uniform_matrix3","um3[1]",3,GL_TRUE,glUniformMatrix3fv);Matrix("uniform_matrix4","um4[1]",4,GL_FALSE,glUniformMatrix4fv);Matrix("uniform_matrix4","um4[1]",4,GL_TRUE,glUniformMatrix4fv);
 use(B);matrix2(glGetUniformLocation(B,"um2"),1,GL_FALSE,matrices);use(A);matrix2(glGetUniformLocation(A,"um2"),1,GL_FALSE,matrices);Check(error()==0,"native-only mat2 setup for getter width");Compare("um2",4,true);Compare("us[0].value",3,true);Compare("us[1].value",3,true);

 for(const char*guest:{"uniform_4fv","uniform_2iv"}){auto loc=glGetUniformLocation(A,!std::strcmp(guest,"uniform_4fv")?"uf4":"ui2");use(A);if(!std::strcmp(guest,"uniform_4fv"))glUniform4fv(loc,1,nullptr);else glUniform2iv(loc,1,nullptr);auto expected_error=error();Check(Run(guest,{uint32_t(loc),1,0})==0,"safe native NULL vector validation");Err(expected_error);}
 Guard no_read(4);for(GLsizei c:{-1,0,3}){use(B);glUniform4fv(-1,c,static_cast<const GLfloat*>(reinterpret_cast<void*>(no_read.inaccessible())));auto expected=error();use(A);Check(Run("uniform_4fv",{uint32_t(-1),uint32_t(c),no_read.inaccessible()})==0,"ignored location has no guest read");Err(expected);}
 auto FloatError=[&](GLint loc,GLsizei c,const char*name,GLuint program){use(program);glUniform4fv(loc,c,static_cast<const GLfloat*>(reinterpret_cast<void*>(no_read.inaccessible())));auto expected=error();use(program);Check(Run(name,{uint32_t(loc),uint32_t(c),no_read.inaccessible()})==0,"uniform error path has no guest read");Err(expected);};FloatError(glGetUniformLocation(A,"uf4"),0,"uniform_4fv",A);FloatError(glGetUniformLocation(A,"uf4"),-1,"uniform_4fv",A);FloatError(0x7fffffff,1,"uniform_4fv",A);FloatError(glGetUniformLocation(A,"ui4"),1,"uniform_4fv",A);FloatError(glGetUniformLocation(A,"uf4"),2,"uniform_4fv",A);FloatError(0,1,"uniform_4fv",0);use(A);
 Guard no_write(16);uint8_t saved[16];std::memcpy(saved,no_write.data(),16);for(GLint loc:{-1,0x7fffffff}){GLint scratch[16]{};glGetUniformiv(A,loc,scratch);auto expected=error();Check(Run("uniform_get",{A,uint32_t(loc),no_write.address()})==0,"invalid getter return");Err(expected);Check(!std::memcmp(saved,no_write.data(),16),"invalid getter leaves output unchanged");}
 // A successful relink resets values; subsequent introspection must use fresh metadata.
 link(B);Check(error()==0,"native reference relink");Invoke(gl,"glLinkProgram",{A});Err(0);Compare("uf3[1]",3,true);Compare("um4[1]",16,true);Compare("ui",1,false);
 use(0);deleteProgram(A);deleteProgram(B);Check(error()==0,"program retirement");Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglTerminate",{display}),"context retirement");egl.ReleaseCurrentThread();egl.SetProcedureResolver({});std::printf("GL-UNIFORM-PASS checks=%u commands=14 old_prefix=63 real_ANGLE=1\n",checks);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"uniform test: %s\n",e.what());return 1;}}

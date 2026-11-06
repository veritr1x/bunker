#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl32.h>
#include <EGL/egl.h>
#include "gl_host.h"
#include "egl_host.h"
#include "gles_service_module.h"
#include "gl_base_vertex_old_commands.h"
#include <algorithm>
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace bunker::windows;
namespace {
unsigned checks=0,draws=0,comparisons=0,nonuniform=0,guard_rejections=0;
constexpr int W=32,H=32;
using Pixels=std::array<uint8_t,W*H*4>;
void Check(bool value,const char*why){if(!value)throw std::runtime_error(why);++checks;}
addr_t Address(const void*p){return reinterpret_cast<addr_t>(p);}
addr_t Word(uint32_t v){return UINT64_C(0xa5b6c7d800000000)|v;}
template<class Hst>addr_t Invoke(Hst&h,const char*n,std::initializer_list<addr_t>a={}){
 State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t i=0;
 for(auto v:a){(s.gpr.*r[i++]).qword=v;}
 h.Invoke(n,s);return s.gpr.x0.qword;
}
template<class F>F Native(HMODULE m,const char*n){auto p=GetProcAddress(m,n);Check(p!=nullptr,n);F f;static_assert(sizeof(f)==sizeof(p));std::memcpy(&f,&p,sizeof(f));return f;}
struct Driver{
#define F(n,t) t n;
 F(error,PFNGLGETERRORPROC) F(viewport,PFNGLVIEWPORTPROC) F(clearColor,PFNGLCLEARCOLORPROC) F(clear,PFNGLCLEARPROC)
 F(read,PFNGLREADPIXELSPROC) F(pixelStore,PFNGLPIXELSTOREIPROC) F(disable,PFNGLDISABLEPROC)
 F(createShader,PFNGLCREATESHADERPROC) F(shaderSource,PFNGLSHADERSOURCEPROC) F(compileShader,PFNGLCOMPILESHADERPROC)
 F(getShader,PFNGLGETSHADERIVPROC) F(deleteShader,PFNGLDELETESHADERPROC) F(createProgram,PFNGLCREATEPROGRAMPROC)
 F(attach,PFNGLATTACHSHADERPROC) F(link,PFNGLLINKPROGRAMPROC) F(getProgram,PFNGLGETPROGRAMIVPROC) F(use,PFNGLUSEPROGRAMPROC) F(deleteProgram,PFNGLDELETEPROGRAMPROC)
 F(genVAO,PFNGLGENVERTEXARRAYSPROC) F(bindVAO,PFNGLBINDVERTEXARRAYPROC) F(deleteVAO,PFNGLDELETEVERTEXARRAYSPROC)
 F(genBuffer,PFNGLGENBUFFERSPROC) F(bindBuffer,PFNGLBINDBUFFERPROC) F(bufferData,PFNGLBUFFERDATAPROC) F(deleteBuffer,PFNGLDELETEBUFFERSPROC)
 F(attrib,PFNGLVERTEXATTRIBPOINTERPROC) F(enableAttrib,PFNGLENABLEVERTEXATTRIBARRAYPROC) F(disableAttrib,PFNGLDISABLEVERTEXATTRIBARRAYPROC)
#undef F
 explicit Driver(HMODULE m):error(Native<PFNGLGETERRORPROC>(m,"glGetError")),viewport(Native<PFNGLVIEWPORTPROC>(m,"glViewport")),clearColor(Native<PFNGLCLEARCOLORPROC>(m,"glClearColor")),clear(Native<PFNGLCLEARPROC>(m,"glClear")),read(Native<PFNGLREADPIXELSPROC>(m,"glReadPixels")),pixelStore(Native<PFNGLPIXELSTOREIPROC>(m,"glPixelStorei")),disable(Native<PFNGLDISABLEPROC>(m,"glDisable")),createShader(Native<PFNGLCREATESHADERPROC>(m,"glCreateShader")),shaderSource(Native<PFNGLSHADERSOURCEPROC>(m,"glShaderSource")),compileShader(Native<PFNGLCOMPILESHADERPROC>(m,"glCompileShader")),getShader(Native<PFNGLGETSHADERIVPROC>(m,"glGetShaderiv")),deleteShader(Native<PFNGLDELETESHADERPROC>(m,"glDeleteShader")),createProgram(Native<PFNGLCREATEPROGRAMPROC>(m,"glCreateProgram")),attach(Native<PFNGLATTACHSHADERPROC>(m,"glAttachShader")),link(Native<PFNGLLINKPROGRAMPROC>(m,"glLinkProgram")),getProgram(Native<PFNGLGETPROGRAMIVPROC>(m,"glGetProgramiv")),use(Native<PFNGLUSEPROGRAMPROC>(m,"glUseProgram")),deleteProgram(Native<PFNGLDELETEPROGRAMPROC>(m,"glDeleteProgram")),genVAO(Native<PFNGLGENVERTEXARRAYSPROC>(m,"glGenVertexArrays")),bindVAO(Native<PFNGLBINDVERTEXARRAYPROC>(m,"glBindVertexArray")),deleteVAO(Native<PFNGLDELETEVERTEXARRAYSPROC>(m,"glDeleteVertexArrays")),genBuffer(Native<PFNGLGENBUFFERSPROC>(m,"glGenBuffers")),bindBuffer(Native<PFNGLBINDBUFFERPROC>(m,"glBindBuffer")),bufferData(Native<PFNGLBUFFERDATAPROC>(m,"glBufferData")),deleteBuffer(Native<PFNGLDELETEBUFFERSPROC>(m,"glDeleteBuffers")),attrib(Native<PFNGLVERTEXATTRIBPOINTERPROC>(m,"glVertexAttribPointer")),enableAttrib(Native<PFNGLENABLEVERTEXATTRIBARRAYPROC>(m,"glEnableVertexAttribArray")),disableAttrib(Native<PFNGLDISABLEVERTEXATTRIBARRAYPROC>(m,"glDisableVertexAttribArray")){}
 Pixels Read(){Pixels p{};read(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,p.data());Check(error()==GL_NO_ERROR,"native pixel readback");return p;}
 void Clear(){clearColor(0,0,0,1);clear(GL_COLOR_BUFFER_BIT);Check(error()==GL_NO_ERROR,"native clear");}
};
enum Kind{Instanced,Base,InstancedBase,Range};
struct Api{const char*name;Kind kind;};
const Api apis[]={{"glDrawElementsInstanced",Instanced},{"glDrawElementsBaseVertex",Base},{"glDrawElementsBaseVertexOES",Base},{"glDrawElementsBaseVertexEXT",Base},{"glDrawElementsInstancedBaseVertex",InstancedBase},{"glDrawElementsInstancedBaseVertexOES",InstancedBase},{"glDrawElementsInstancedBaseVertexEXT",InstancedBase},{"glDrawRangeElementsBaseVertex",Range},{"glDrawRangeElementsBaseVertexOES",Range},{"glDrawRangeElementsBaseVertexEXT",Range}};
struct Case{GLenum mode=GL_TRIANGLES;GLsizei count=3;GLenum type=GL_UNSIGNED_SHORT;addr_t offset=24;GLsizei instances=1;GLint base=0;GLuint start=2,end=4;};
void Raw(HMODULE module,const Api&a,const Case&c){const void*p=reinterpret_cast<const void*>(c.offset);
 switch(a.kind){case Instanced:Native<PFNGLDRAWELEMENTSINSTANCEDPROC>(module,a.name)(c.mode,c.count,c.type,p,c.instances);break;
 case Base:Native<PFNGLDRAWELEMENTSBASEVERTEXPROC>(module,a.name)(c.mode,c.count,c.type,p,c.base);break;
 case InstancedBase:Native<PFNGLDRAWELEMENTSINSTANCEDBASEVERTEXPROC>(module,a.name)(c.mode,c.count,c.type,p,c.instances,c.base);break;
 case Range:Native<PFNGLDRAWRANGEELEMENTSBASEVERTEXPROC>(module,a.name)(c.mode,c.start,c.end,c.count,c.type,p,c.base);break;}
}
std::vector<addr_t> Args(const Api&a,const Case&c){
 if(a.kind==Range)return{Word(c.mode),Word(c.start),Word(c.end),Word(uint32_t(c.count)),Word(c.type),c.offset,Word(uint32_t(c.base))};
 std::vector<addr_t>v={Word(c.mode),Word(uint32_t(c.count)),Word(c.type),c.offset};
 if(a.kind==Instanced||a.kind==InstancedBase)v.push_back(Word(uint32_t(c.instances)));
 if(a.kind==Base||a.kind==InstancedBase){v.push_back(Word(uint32_t(c.base)));}
 return v;
}
State DrawState(const Api&a,const Case&c){State s{};std::memset(&s.simd,0x5a,sizeof(s.simd));s.gpr.x19.qword=UINT64_C(0x123456789abcdef0);s.gpr.x30.qword=0xfeedffff;s.sr.ioc=1;
 Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};auto v=Args(a,c);for(size_t i=0;i<v.size();++i)(s.gpr.*regs[i]).qword=v[i];return s;}
void Bridge(recomp::Runtime&r,GlHost&gl,const Api&a,const Case&c){alignas(16)std::array<uint8_t,512>stack{};State s=DrawState(a,c);s.gpr.sp.qword=Address(stack.data()+stack.size());s.gpr.pc.qword=gl.Marker(a.name);State expected=s;expected.gpr.pc.qword=s.gpr.x30.qword;auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));Check(r.Run(s,gl.Marker(a.name),token)==token,"typed marker preserves Memory64");Check(std::memcmp(&s,&expected,sizeof(s))==0,"void marker dispatch preserves full State except normal PC return");++draws;}
void Upload(Driver&d,GLuint ebo,const Case&c){std::array<uint8_t,128>bytes{};const uint32_t first=c.base>0?0:c.base<0?4:2;for(unsigned i=0;i<3;++i){uint32_t n=first+i;if(c.type==GL_UNSIGNED_INT)std::memcpy(bytes.data()+24+4*i,&n,4);else{auto h=uint16_t(n);std::memcpy(bytes.data()+24+2*i,&h,2);}}
 auto memory=static_cast<uint8_t*>(VirtualAlloc(nullptr,8192,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));Check(memory!=nullptr,"guarded GPU upload allocation");DWORD old;Check(VirtualProtect(memory+4096,4096,PAGE_NOACCESS,&old)!=0,"upload guard page");auto p=memory+4096-bytes.size();std::memcpy(p,bytes.data(),bytes.size());d.bindBuffer(GL_ELEMENT_ARRAY_BUFFER,ebo);d.bufferData(GL_ELEMENT_ARRAY_BUFFER,bytes.size(),p,GL_STATIC_DRAW);Check(d.error()==GL_NO_ERROR,"real EBO upload");Check(VirtualProtect(memory,4096,PAGE_NOACCESS,&old)!=0,"retire EBO CPU bytes before draws");VirtualFree(memory,0,MEM_RELEASE);
}
bool Colored(const Pixels&p){
 bool colored=false,different=false;
 for(size_t i=0;i<p.size();i+=4){
  colored=colored||p[i]!=0||p[i+1]!=0||p[i+2]!=0;
  different=different||std::memcmp(p.data(),p.data()+i,4)!=0;
 }
 return colored&&different;
}
}
int main(){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(addr_t)==8);
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
 bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;EglHost egl(windows,GL_BASE_VERTEX_DLL_DIRECTORY);egl.Install(runtime);GlHost gl(egl,GL_BASE_VERTEX_DLL_DIRECTORY);gl.Install(runtime);egl.SetProcedureResolver([&](const std::string&n){return FindTypedGlesProcedure(gl,n);});
 auto display=Invoke(egl,"eglGetDisplay",{0});Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"actual ANGLE display");
 const int configArgs[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,0x40,EGL_NONE};addr_t config=0;int count=0;Check(Invoke(egl,"eglChooseConfig",{display,Address(configArgs),Address(&config),1,Address(&count)})&&count==1,"RGBA8 GPU pbuffer config");
 const int contextArgs[]={EGL_CONTEXT_CLIENT_VERSION,3,0x30fb,1,EGL_NONE},surfaceArgs[]={EGL_WIDTH,W,EGL_HEIGHT,H,EGL_NONE};auto context=Invoke(egl,"eglCreateContext",{display,config,0,Address(contextArgs)});auto surface=Invoke(egl,"eglCreatePbufferSurface",{display,config,Address(surfaceArgs)});Check(context&&surface&&Invoke(egl,"eglMakeCurrent",{display,surface,surface,context}),"actual GLES3.1 context current");
 auto module=GetModuleHandleW(L"libGLESv2.dll");Check(module!=nullptr,"actual pinned ANGLE GLES module");Driver d(module);d.viewport(0,0,W,H);d.disable(GL_DITHER);d.disable(GL_DEPTH_TEST);d.disable(GL_BLEND);d.pixelStore(GL_PACK_ALIGNMENT,1);
 Check(GlHost::Commands().size()==std::size(kOldBaseVertexCommands)+std::size(apis),"exact append-only ten command additions");
 for(size_t i=0;i<std::size(kOldBaseVertexCommands);++i)Check(GlHost::Commands()[i]==kOldBaseVertexCommands[i]&&gl.Marker(kOldBaseVertexCommands[i])==0x7ff450000000ULL+i*8,"all old command ordinals preserved");
 for(size_t i=0;i<std::size(apis);++i){auto&a=apis[i];auto native=GetProcAddress(module,a.name);Check(native!=nullptr,"actual corresponding ANGLE export exists");Check(gl.Marker(a.name)==0x7ff450000000ULL+(std::size(kOldBaseVertexCommands)+i)*8,"new command ordinal exact");Check(Invoke(egl,"eglGetProcAddress",{Address(a.name)})==gl.Marker(a.name)&&gl.Marker(a.name)!=reinterpret_cast<addr_t>(native),"procedure lookup returns typed marker rather than native address");}
 Check(Invoke(egl,"eglGetProcAddress",{Address("glDrawElementsBaseVertexUnimplemented")})==0,"unknown optional procedure remains unavailable");
 auto shader=[&](GLenum type,const char*source){GLuint s=d.createShader(type);d.shaderSource(s,1,&source,nullptr);d.compileShader(s);GLint ok=0;d.getShader(s,GL_COMPILE_STATUS,&ok);Check(ok==1,"real GPU shader compile");return s;};
 const char*vs="#version 300 es\nlayout(location=0)in vec2 p;out vec3 tint;void main(){float id=float(gl_InstanceID);gl_Position=vec4(p+vec2(id*.9,0),0,1);tint=vec3(1.-id*.55,.2+id*.6,.15);}";
 const char*fs="#version 300 es\nprecision highp float;in vec3 tint;out vec4 color;void main(){color=vec4(tint,1);}";GLuint v=shader(GL_VERTEX_SHADER,vs),f=shader(GL_FRAGMENT_SHADER,fs),program=d.createProgram();d.attach(program,v);d.attach(program,f);d.link(program);GLint linked=0;d.getProgram(program,GL_LINK_STATUS,&linked);Check(linked==1,"actual GPU program link");d.use(program);d.deleteShader(v);d.deleteShader(f);
 GLuint vao=0,buffers[2]{};d.genVAO(1,&vao);d.bindVAO(vao);d.genBuffer(2,buffers);d.bindBuffer(GL_ARRAY_BUFFER,buffers[0]);const float vertices[]={-.95f,-.95f,-.9f,-.95f,-.75f,-.6f,-.15f,-.6f,-.45f,.15f,.65f,.6f,.9f,.9f,.7f,.6f,.8f,.7f};d.bufferData(GL_ARRAY_BUFFER,sizeof(vertices),vertices,GL_STATIC_DRAW);d.attrib(0,2,GL_FLOAT,GL_FALSE,0,nullptr);d.enableAttrib(0);Check(d.error()==0,"actual VBO/VAO setup");
 gl.EnableFrameDiagnostics(GL_BASE_VERTEX_DIAGNOSTIC_PATH);Pixels single{},twice{};bool haveSingle=false,haveTwice=false;
 auto Compare=[&](const Api&a,Case c,bool mustDraw){Upload(d,buffers[1],c);Check(Invoke(gl,"glGetError")==0,"start with clean native/provider error queue");d.Clear();Raw(module,a,c);GLenum referenceError=d.error();auto reference=d.Read();d.Clear();Bridge(runtime,gl,a,c);GLenum actualError=GLenum(Invoke(gl,"glGetError"));auto actual=d.Read();Check(referenceError==actualError,"typed ABI forwards exact native GL error");Check(reference==actual,"typed indexed draw pixels exactly match genuine corresponding ANGLE API");++comparisons;
  if(mustDraw){Check(referenceError==0&&Colored(actual),"actual nonuniform colored indexed rendering");++nonuniform;}
  if(a.kind==Instanced&&c.count==3&&c.mode==GL_TRIANGLES&&c.type==GL_UNSIGNED_SHORT){if(c.instances==1){single=actual;haveSingle=true;}if(c.instances==2){twice=actual;haveTwice=true;}}
 };
 for(const auto&a:apis){
  for(GLenum type:{GLenum(GL_UNSIGNED_SHORT),GLenum(GL_UNSIGNED_INT)})for(GLint base:{0,2,-2}){
   if(a.kind==Instanced&&base!=0){continue;}
   Case c;c.type=type;c.base=base;c.start=base>0?0:base<0?4:2;c.end=c.start+2;c.instances=(a.kind==Instanced||a.kind==InstancedBase)?2:1;Compare(a,c,true);
  }
  if(a.kind==Instanced||a.kind==InstancedBase){Case c;c.instances=0;Compare(a,c,false);c.instances=1;Compare(a,c,true);c.instances=-1;Compare(a,c,false);}
  Case c;c.count=0;Compare(a,c,false);c.count=-1;Compare(a,c,false);c.count=3;c.mode=0xffffffffU;Compare(a,c,false);
  if(a.kind==Range){c=Case{};c.start=5;c.end=4;Compare(a,c,false);}
  c=Case{};Upload(d,buffers[1],c);d.bindBuffer(GL_ELEMENT_ARRAY_BUFFER,0);State s=DrawState(a,c);bool rejected=false;try{gl.Invoke(a.name,s);}catch(const std::runtime_error&e){rejected=std::strstr(e.what(),"GPU EBO")!=nullptr;}Check(rejected&&d.error()==0,"missing GPU EBO rejected without native call");++guard_rejections;d.bindBuffer(GL_ELEMENT_ARRAY_BUFFER,buffers[1]);
  d.enableAttrib(7);s=DrawState(a,c);rejected=false;try{gl.Invoke(a.name,s);}catch(const std::runtime_error&e){rejected=std::strstr(e.what(),"CPU client vertex arrays")!=nullptr;}Check(rejected&&d.error()==0,"client vertex source rejected without native call");++guard_rejections;d.disableAttrib(7);
 }
 Check(haveSingle&&haveTwice&&single!=twice,"instance count changes actual GPU coverage/color");
 auto diagnostics=gl.DescribeFrameDiagnostics();Check(diagnostics.draw_submissions==draws&&!diagnostics.first_present_png&&!diagnostics.frame_png,"new draws counted without a false original/presented frame");
 d.use(0);d.deleteProgram(program);d.deleteBuffer(2,buffers);d.deleteVAO(1,&vao);Check(d.error()==0&&Invoke(gl,"glGetError")==0,"clean final native errors");
 Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&Invoke(egl,"eglDestroyContext",{display,context})&&Invoke(egl,"eglDestroySurface",{display,surface})&&Invoke(egl,"eglTerminate",{display}),"actual GPU resources retired");egl.ReleaseCurrentThread();egl.SetProcedureResolver({});
 char text[256];std::snprintf(text,sizeof(text),"GL-BASE-VERTEX-PASS checks=%u APIs=10 comparisons=%u nonuniform=%u marker_draws=%u guard_rejections=%u State=1200 Memory64=1 offset=24\n",checks,comparisons,nonuniform,draws,guard_rejections);std::fputs(text,stdout);std::ofstream(GL_BASE_VERTEX_RESULT_PATH)<<text;return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"GL base vertex failure: %s\n",e.what());return 1;}}

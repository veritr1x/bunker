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
#include "gl_draw_old_commands.h"
#include <array>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <thread>
#include <vector>
using namespace bunker::windows;
static unsigned checks;
static HMODULE driver;
static EglHost *egl_provider;
static GlHost *gl_provider;
static void Check(bool good,const char *why){if(!good)throw std::runtime_error(why);++checks;}
template<class T>static T NativeSymbol(const char *name){auto p=GetProcAddress(driver,name);if(!p)throw std::runtime_error(name);T result;std::memcpy(&result,&p,sizeof result);return result;}
#define GL_NATIVE_REFERENCE
#define gl_draw_upload native_upload
#define gl_draw_compile native_compile
#define gl_draw_render native_render
#define gl_draw_read native_read
#define gl_draw_bad_shader native_bad_shader
#define gl_draw_query native_query
#define gl_draw_cleanup native_cleanup
#define gl_draw_delete_program native_delete_program
#include "gl_draw_guest.c"
#undef gl_draw_upload
#undef gl_draw_compile
#undef gl_draw_render
#undef gl_draw_read
#undef gl_draw_bad_shader
#undef gl_draw_query
#undef gl_draw_cleanup
#undef gl_draw_delete_program
#undef GL_NATIVE_REFERENCE
template<class T>static addr_t Invoke(T &host,const char *name,std::initializer_list<addr_t> args={}){
 State state{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t at=0;
 for(auto value:args)(state.gpr.*regs[at++]).qword=value;
 host.Invoke(name,state);return state.gpr.x0.qword;
}
static void *Resolve(const char *name){return reinterpret_cast<void*>(!std::strcmp(name,"eglGetProcAddress")?egl_provider->Marker(name):gl_provider->Marker(name));}
static addr_t Address(const void *p){return reinterpret_cast<addr_t>(p);}
// Every input occupies its own guarded allocation. Protecting it immediately
// after upload proves neither ANGLE nor our bridge retains a guest CPU pointer.
struct Inputs{
 std::vector<void*> pages;DrawInput input{};
 void *Copy(const void *source,size_t bytes,bool page_end=false){
  auto p=static_cast<uint8_t*>(VirtualAlloc(nullptr,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(p!=nullptr,"guarded guest input allocation");
  DWORD old;Check(VirtualProtect(p+4096,4096,PAGE_NOACCESS,&old)!=0,"input guard page");pages.push_back(p);
  auto destination=page_end?p+4096-bytes:p;std::memcpy(destination,source,bytes);return destination;
 }
 Inputs(){
  const char version[]="#version 300 es\n";
  const char vertex[]="layout(location=0) in vec2 position;void main(){gl_Position=vec4(position,0,1);}";
  const char fragment[]="precision highp float;out vec4 color;void main(){color=vec4(1,0,0,1);}";
  const void *vs[]={Copy(version,sizeof(version)-1,true),Copy(vertex,sizeof vertex,true)};
  const void *fs[]={Copy(version,sizeof(version)-1,true),Copy(fragment,sizeof fragment,true)};
  const int lengths[]={int(sizeof(version)-1),-1};
  input.vs=Address(Copy(vs,sizeof vs));input.fs=Address(Copy(fs,sizeof fs));
  input.vlengths=Address(Copy(lengths,sizeof lengths));input.flengths=Address(Copy(lengths,sizeof lengths));input.vcount=input.fcount=2;
  const float vertices[]={0,0,0,0,-.8f,-.8f,.8f,-.8f,0,.8f};const uint16_t indices[]={0xffff,0xffff,0,1,2};
  input.vertices=Address(Copy(vertices,sizeof vertices));input.indices=Address(Copy(indices,sizeof indices));input.vertex_bytes=sizeof vertices;input.index_bytes=sizeof indices;
 }
 void Hide(){for(auto p:pages){DWORD old;Check(VirtualProtect(p,4096,PAGE_NOACCESS,&old)!=0,"uploaded input retired from CPU access");}}
 ~Inputs(){for(auto p:pages)VirtualFree(p,0,MEM_RELEASE);}
};
int main(){try{
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
 bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);recomp::Runtime runtime;
 EglHost egl(windows,GL_DRAW_DLL_DIRECTORY);egl_provider=&egl;egl.Install(runtime);
 GlHost gl(egl,GL_DRAW_DLL_DIRECTORY);gl_provider=&gl;gl.Install(runtime);egl.SetProcedureResolver([&](const std::string &name){return gl.Marker(name);});
 driver=GetModuleHandleW(L"libGLESv2.dll");Check(driver!=nullptr,"pinned GLES module loaded");
 auto display=Invoke(egl,"eglGetDisplay",{0});Check(display&&Invoke(egl,"eglInitialize",{display,0,0}),"real Vulkan display initialized");
 const int attrs[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_DEPTH_SIZE,24,EGL_STENCIL_SIZE,8,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,0x40,EGL_NONE};addr_t config=0;int count=0;
 Check(Invoke(egl,"eglChooseConfig",{display,Address(attrs),Address(&config),1,Address(&count)})&&count==1,"real RGBA8 pbuffer config");
 const int ca[]={EGL_CONTEXT_CLIENT_VERSION,3,0x30fb,1,EGL_NONE},sa[]={EGL_WIDTH,8,EGL_HEIGHT,8,EGL_NONE};
 auto Create=[&](addr_t share){auto c=Invoke(egl,"eglCreateContext",{display,config,share,Address(ca)});Check(c!=0,"real context created");return c;};
 auto Surface=[&]{auto s=Invoke(egl,"eglCreatePbufferSurface",{display,config,Address(sa)});Check(s!=0,"real immutable 8x8 read pbuffer created");return s;};
 auto Bind=[&](addr_t c,addr_t s){Check(Invoke(egl,"eglMakeCurrent",{display,s,s,c})!=0,"bind owned context and pbuffer");};
 const auto reference_context=Create(0),reference_surface=Surface();Bind(reference_context,reference_surface);
 Inputs reference_inputs;DrawObjects reference_objects{};native_upload(&reference_inputs.input,&reference_objects);reference_inputs.Hide();
 DrawStatus reference_status{};native_compile(&reference_objects,&reference_status);Check(reference_status.vertex&&reference_status.fragment&&reference_status.linked&&reference_status.shader_deleted,"raw native reference shader compilation/link/deletion");
 std::array<uint8_t,256> reference_pixels{};native_render(&reference_objects,0,reference_pixels.data());
 Check(NativeSymbol<PFNGLGETERRORPROC>("glGetError")()==GL_NO_ERROR,"raw native reference error-free");
 const auto context=Create(0),surface=Surface();Bind(context,surface);
 auto extent=egl.CurrentReadPbufferExtent();Check(extent&&extent->context==context&&extent->surface==surface&&extent->width==8&&extent->height==8,"read-pbuffer extent from actual logical surface");
 elf_image image{};Check(!elf_load(GL_DRAW_LIBRARY,0x5b000000,Resolve,&image),"strict Android NDK library loads");runtime.AddTraces(kTraces,std::size(kTraces));
 auto Guest=[&](const char *name,std::initializer_list<addr_t> args={}){
  alignas(16)std::array<uint8_t,65536> stack{};State state{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t at=0;
  for(auto value:args)(state.gpr.*regs[at++]).qword=value;
  state.gpr.sp.qword=Address(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;
  auto entry=elf_symbol(&image,name);Check(entry!=nullptr,"NDK exported function exists");runtime.Run(state,Address(entry));
  Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==Address(stack.data()+stack.size()),"NDK PC/SP preserved");return state.gpr.x0.qword;
 };
 struct Names{uint64_t before=0x1122334455667788ULL,names[29]{},after=0x8877665544332211ULL;} names;
 Guest("gl_draw_resolve",{Address(names.names)});unsigned index=0;
#define GL_DRAW(n,t) Check(names.names[index++]==gl.Marker(#n),"NDK resolver returns typed guest marker, never native pointer");
#include "gl_draw_commands.inc"
#undef GL_DRAW
 Check(names.before==0x1122334455667788ULL&&names.after==0x8877665544332211ULL,"resolver output exact eight-byte entries");
 Check(gl.Marker("glGetString")==0x7ff450000000ULL&&gl.Marker("glGetError")==0x7ff450000028ULL,"old GL marker identities unchanged");
 Check(std::size(kOldDrawCommands)==121&&GlHost::Commands().size()==122,"exact old121 plus single VAO predicate");
 for(size_t i=0;i<121;++i)Check(GlHost::Commands()[i]==kOldDrawCommands[i]&&gl.Marker(kOldDrawCommands[i])==gl.Marker(kOldDrawCommands[0])+i*8,"every previous command name and marker retained");
 const auto object_marker=gl.Marker("glIsVertexArray");
 Check(GlHost::Commands()[121]=="glIsVertexArray"&&object_marker==gl.Marker(kOldDrawCommands[0])+121*8,"VAO predicate appended last");
 Check(Guest("gl_draw_object_resolve")==object_marker&&object_marker!=reinterpret_cast<addr_t>(GetProcAddress(driver,"glIsVertexArray")),"actual NDK procedure lookup returns typed marker, never native pointer");
 struct Guard{uint64_t before=0x123456789abcdef0ULL;DrawObjects objects{};uint64_t after=0xfedcba9876543210ULL;} guard;
 Inputs inputs;Guest("gl_draw_upload",{Address(&inputs.input),Address(&guard.objects)});inputs.Hide();
 Check(guard.before==0x123456789abcdef0ULL&&guard.after==0xfedcba9876543210ULL,"GLuint generation writes exact four-byte outputs");
 const auto &o=guard.objects;Check(o.vs&&o.fs&&o.program&&o.buffers[0]&&o.buffers[1]&&o.vao,"native shader/program/buffer/VAO object names");
 DrawStatus status{};Guest("gl_draw_compile",{Address(&o),Address(&status)});
 Check(!std::memcmp(&status,&reference_status,sizeof status),"NDK shader status and deferred deletion match independent native reference");
 static_assert(sizeof(GLboolean)==1);
 unsigned object_calls=0,object_records=0;
 const auto native_is_vao=NativeSymbol<PFNGLISVERTEXARRAYPROC>("glIsVertexArray");
 auto ObjectQuery=[&](GLuint name,GLboolean expected){
  const auto actual_native=native_is_vao(name);Check(actual_native==expected,"independent native VAO lifecycle state");
  Check(Guest("gl_draw_is_vertex_array_direct",{UINT64_C(0x1234567800000000)|name})==uint64_t(actual_native),"NDK direct import returns exact native boolean");++object_calls;
  Check(Guest("gl_draw_is_vertex_array_pointer",{object_marker,UINT64_C(0xa5a5a5a500000000)|name})==uint64_t(actual_native),"NDK function pointer returns exact native boolean");++object_calls;
  Check(Guest("gl_draw_is_vertex_array_procedure",{name})==uint64_t(actual_native),"NDK procedure lookup/call returns exact native boolean");++object_calls;
  State abi{};abi.gpr.x0.qword=UINT64_C(0xfedcba9800000000)|name;gl.Invoke("glIsVertexArray",abi);
  Check(abi.gpr.x0.qword==uint64_t(actual_native),"GLboolean bridge clears stale high return bits and consumes GLuint low32");
  Check(Invoke(gl,"glGetError")==0,"VAO predicate creates no native error");++object_records;
 };
 GLuint reserved_vao=0;Invoke(gl,"glGenVertexArrays",{1,Address(&reserved_vao)});Check(reserved_vao!=0,"actual native VAO name reserved");
 ObjectQuery(0,GL_FALSE);ObjectQuery(reserved_vao,GL_FALSE);ObjectQuery(0xffffffffU,GL_FALSE);ObjectQuery(o.vao,GL_TRUE);
 Invoke(gl,"glBindVertexArray",{reserved_vao});ObjectQuery(reserved_vao,GL_TRUE);
 Invoke(gl,"glBindVertexArray",{0});ObjectQuery(reserved_vao,GL_TRUE);
 Invoke(gl,"glBindVertexArray",{reserved_vao});Invoke(gl,"glDeleteVertexArrays",{1,Address(&reserved_vao)});ObjectQuery(reserved_vao,GL_FALSE);
 GLint bound_vao=-1;NativeSymbol<PFNGLGETINTEGERVPROC>("glGetIntegerv")(GL_VERTEX_ARRAY_BINDING,&bound_vao);Check(bound_vao==0,"deleting bound VAO really unbinds it");
 NativeSymbol<PFNGLENABLEPROC>("glEnable")(0xffffffffU);
 for(const char *wrapper:{"gl_draw_is_vertex_array_direct","gl_draw_is_vertex_array_procedure"}){Check(Guest(wrapper,{o.vao})==GL_TRUE,"valid boolean query succeeds with pending native error");++object_calls;}
 Check(Guest("gl_draw_is_vertex_array_pointer",{object_marker,o.vao})==GL_TRUE,"pointer boolean query preserves pending native error");++object_calls;
 Check(Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==0,"VAO query preserves existing error exactly once");
 Invoke(gl,"glBindVertexArray",{o.vao});
 struct Image{uint64_t before=0xaabbccdd12345678ULL;std::array<uint8_t,256> pixels{};uint64_t after=0x87654321ddccbbaaULL;} actual;
 for(unsigned indexed=0;indexed<2;++indexed){Guest("gl_draw_render",{Address(&o),indexed,Address(actual.pixels.data())});
  Check(actual.pixels==reference_pixels,"all actual NDK triangle RGBA pixels match raw native reference");
  Check(actual.before==0xaabbccdd12345678ULL&&actual.after==0x87654321ddccbbaaULL,"readback canaries intact");
  for(unsigned c=0;c<4;++c){Check(actual.pixels[(3*8+3)*4+c]==(c==0||c==3?255:0),"independent red triangle interior");Check(actual.pixels[c]==(c==3?255:0),"independent opaque black triangle exterior");}
 }
 Check(Invoke(gl,"glGetError")==0,"all NDK triangle calls driver-error-free");
 // Driver pack rows can overlap when rowLength < width. Compare the entire
 // canary-filled allocation against independent native writes, not just pixels.
 const DrawRead reads[]={{0,0,3,3,8,0,1,2},{1,1,4,3,4,2,1,1},{0,0,8,8,1,0,0,0},{2,2,1,2,8,5,2,3},{0,0,0,4,4,0,0,0},{0,0,4,0,4,0,0,0}};
 for(const auto &r:reads){std::array<uint8_t,1024> expected,got;expected.fill(0xa5);got.fill(0xa5);
  Bind(reference_context,reference_surface);native_read(&r,expected.data());Check(NativeSymbol<PFNGLGETERRORPROC>("glGetError")()==0,"native pack reference success");
  Bind(context,surface);Guest("gl_draw_read",{Address(&r),Address(got.data())});Check(got==expected,"exact pack overlap/stride/skips and untouched padding agree");
 }
 DrawRead reset{0,0,8,8,4,0,0,0};Guest("gl_draw_read",{Address(&reset),Address(actual.pixels.data())});
 NativeSymbol<PFNGLENABLEPROC>("glEnable")(0xffffffffU);int linked=0;
 Guest("gl_draw_query",{o.program,GL_LINK_STATUS,Address(&linked)});Check(linked==1,"pending native error does not suppress valid tracked query output");
 Check(Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==0,"native error queue preserved across internal queries");
 NativeSymbol<PFNGLENABLEPROC>("glEnable")(0xffffffffU);actual.pixels.fill(0xa5);Guest("gl_draw_read",{Address(&reset),Address(actual.pixels.data())});
 Check(actual.pixels==reference_pixels&&Invoke(gl,"glGetError")==GL_INVALID_ENUM&&Invoke(gl,"glGetError")==0,"readback publication survives preexisting native GL error");
 const char *bad="#version 300 es\nthis is invalid GLSL";int bad_status=7,written=7;std::array<char,1024> log;log.fill(char(0x55));
 Guest("gl_draw_bad_shader",{Address(&bad),0,log.size(),Address(&bad_status),Address(&written),Address(log.data())});
 Check(!bad_status&&written>0&&written<int(log.size())&&log[written]==0&&log[written+1]==char(0x55),"invalid GLSL reports real compile status and exact log/NUL footprint");
 Check(Invoke(gl,"glGetError")==0,"compile failure is status, not synthetic GL error");
 int native_bad_status=7,native_written=7;std::array<char,1024> native_log;native_log.fill(char(0x55));
 Bind(reference_context,reference_surface);native_bad_shader(&bad,nullptr,native_log.size(),&native_bad_status,&native_written,native_log.data());Bind(context,surface);
 Check(native_bad_status==bad_status&&native_written==written&&native_log==log,"NDK invalid shader full log and untouched suffix equal raw native reference");
 log.fill(char(0x55));written=7;Guest("gl_draw_bad_shader",{Address(&bad),0,1,Address(&bad_status),Address(&written),Address(log.data())});
 Check(!bad_status&&written==0&&log[0]==0&&log[1]==char(0x55),"one-byte log truncation writes only terminator");
 written=7;Guest("gl_draw_bad_shader",{Address(&bad),0,0,Address(&bad_status),Address(&written),0});Check(written==0,"zero-capacity log only writes length");
 int unchanged=0x12345678;Guest("gl_draw_query",{0x7fffffff,GL_LINK_STATUS,Address(&unchanged)});
 Check(unchanged==0x12345678&&Invoke(gl,"glGetError")!=0,"invalid native object produces error without guessed output publication");
 auto Reject=[&](const std::function<void()> &call,const char *why){bool rejected=false;try{call();}catch(const std::exception&){rejected=true;}Check(rejected,why);};
 Reject([&]{Invoke(gl,"glGetProgramiv",{o.program,0xffffffffU,1});},"unknown object query width explicit before output access");
 Reject([&]{gl.Marker("glMapBufferRange");},"unknown mapped signature remains explicit");
 Reject([&]{Invoke(gl,"glCreateShader",{GL_COMPUTE_SHADER});},"compute shader stage outside typed scope");
 Invoke(gl,"glBindBuffer",{GL_ARRAY_BUFFER,0});Reject([&]{Invoke(gl,"glVertexAttribPointer",{0,2,GL_FLOAT,0,8,1});},"CPU client vertex pointer rejected");Invoke(gl,"glBindBuffer",{GL_ARRAY_BUFFER,o.buffers[0]});
 Invoke(gl,"glBindBuffer",{GL_ELEMENT_ARRAY_BUFFER,0});Reject([&]{Invoke(gl,"glDrawElements",{GL_TRIANGLES,3,GL_UNSIGNED_SHORT,1});},"CPU client index pointer rejected");Invoke(gl,"glBindBuffer",{GL_ELEMENT_ARRAY_BUFFER,o.buffers[1]});
 Reject([&]{Invoke(gl,"glReadPixels",{0,0,9,8,GL_RGBA,GL_UNSIGNED_BYTE,1});},"clipped read footprint rejected");
 Reject([&]{Invoke(gl,"glReadPixels",{0,0,1,1,GL_RGB,GL_UNSIGNED_BYTE,1});},"unimplemented pixel format footprint explicit");
 Invoke(gl,"glPixelStorei",{GL_PACK_ROW_LENGTH,0x7fffffffU});Invoke(gl,"glPixelStorei",{GL_PACK_SKIP_ROWS,0x7fffffffU});
 Reject([&]{Invoke(gl,"glReadPixels",{0,0,1,1,GL_RGBA,GL_UNSIGNED_BYTE,1});},"pack multiplication overflow/oversize rejected before guest access");
 Guest("gl_draw_read",{Address(&reset),Address(actual.pixels.data())});
 GLuint pack_buffer=0;Invoke(gl,"glGenBuffers",{1,Address(&pack_buffer)});Invoke(gl,"glBindBuffer",{GL_PIXEL_PACK_BUFFER,pack_buffer});
 Reject([&]{Invoke(gl,"glReadPixels",{0,0,1,1,GL_RGBA,GL_UNSIGNED_BYTE,1});},"PBO readback remains explicit outside host-copy scope");
 Invoke(gl,"glBindBuffer",{GL_PIXEL_PACK_BUFFER,0});Invoke(gl,"glDeleteBuffers",{1,Address(&pack_buffer)});
 GLuint fbo=0;NativeSymbol<PFNGLGENFRAMEBUFFERSPROC>("glGenFramebuffers")(1,&fbo);NativeSymbol<PFNGLBINDFRAMEBUFFERPROC>("glBindFramebuffer")(GL_READ_FRAMEBUFFER,fbo);
 Reject([&]{Invoke(gl,"glReadPixels",{0,0,1,1,GL_RGBA,GL_UNSIGNED_BYTE,1});},"nondefault read FBO remains explicit outside copy footprint scope");
 NativeSymbol<PFNGLBINDFRAMEBUFFERPROC>("glBindFramebuffer")(GL_READ_FRAMEBUFFER,0);NativeSymbol<PFNGLDELETEFRAMEBUFFERSPROC>("glDeleteFramebuffers")(1,&fbo);
 Invoke(gl,"glViewport",{0,0,1,1});Check(egl.CurrentReadPbufferExtent()->width==8,"read extent is native read surface, never viewport dimensions");
 Invoke(gl,"glGenBuffers",{0,1});Invoke(gl,"glDeleteBuffers",{0,1});Invoke(gl,"glGenVertexArrays",{0,1});Invoke(gl,"glDeleteVertexArrays",{0,1});
 Invoke(gl,"glBufferSubData",{GL_ARRAY_BUFFER,0,0,1});Check(Invoke(gl,"glGetError")==0,"zero-count and zero-byte calls do not read guest input");
 Invoke(gl,"glGenBuffers",{uint32_t(-1),1});Check(Invoke(gl,"glGetError")==GL_INVALID_VALUE,"negative count native validation without unsafe output access");
 Invoke(gl,"glBufferData",{GL_ARRAY_BUFFER,uint64_t(-1),1,GL_STATIC_DRAW});Check(Invoke(gl,"glGetError")==GL_INVALID_VALUE,"negative signed64 buffer size native validation");
 GLuint edge_shader=static_cast<GLuint>(Invoke(gl,"glCreateShader",{GL_VERTEX_SHADER}));
 Invoke(gl,"glShaderSource",{edge_shader,uint32_t(-1),1,1});Check(Invoke(gl,"glGetError")==GL_INVALID_VALUE,"negative shader string count never reads pointer/length arrays");
 Invoke(gl,"glShaderSource",{edge_shader,0,1,1});Check(Invoke(gl,"glGetError")==0,"zero string count never reads guest arrays");
 Invoke(gl,"glGetShaderInfoLog",{edge_shader,uint32_t(-1),1,1});Check(Invoke(gl,"glGetError")==GL_INVALID_VALUE,"negative info-log capacity never publishes length/data");
 Invoke(gl,"glDeleteShader",{edge_shader});
 std::array<uint8_t,8> unaligned;unaligned.fill(0xa5);Invoke(gl,"glGenBuffers",{1,Address(unaligned.data()+1)});
 GLuint unaligned_name=0;std::memcpy(&unaligned_name,unaligned.data()+1,4);Check(unaligned_name&&unaligned[0]==0xa5&&unaligned[5]==0xa5,"unaligned name output writes exact four bytes through staging");Invoke(gl,"glDeleteBuffers",{1,Address(unaligned.data()+1)});
 // Three-component query width is exercised with a native-only compiled
 // compute program, without exposing a guest compute-stage or dispatch API.
 GLuint cs=NativeSymbol<PFNGLCREATESHADERPROC>("glCreateShader")(GL_COMPUTE_SHADER),cp=NativeSymbol<PFNGLCREATEPROGRAMPROC>("glCreateProgram")();
 const char *compute="#version 310 es\nlayout(local_size_x=2,local_size_y=3,local_size_z=1) in;void main(){}";
 NativeSymbol<PFNGLSHADERSOURCEPROC>("glShaderSource")(cs,1,&compute,nullptr);NativeSymbol<PFNGLCOMPILESHADERPROC>("glCompileShader")(cs);NativeSymbol<PFNGLATTACHSHADERPROC>("glAttachShader")(cp,cs);NativeSymbol<PFNGLLINKPROGRAMPROC>("glLinkProgram")(cp);
 std::array<int32_t,5> workgroup={0x12345678,0,0,0,0x76543210};Guest("gl_draw_query",{cp,GL_COMPUTE_WORK_GROUP_SIZE,Address(workgroup.data()+1)});
 Check(workgroup==std::array<int32_t,5>{0x12345678,2,3,1,0x76543210},"three-component program query publishes exact 12-byte output");NativeSymbol<PFNGLDELETEPROGRAMPROC>("glDeleteProgram")(cp);NativeSymbol<PFNGLDELETESHADERPROC>("glDeleteShader")(cs);
 Check(Invoke(gl,"glGetError")==0,"bounded shape/negative/unaligned cases leave no native errors");
 // Native EGL errors are moved into the public cache, never fabricated back
 // into the native driver. Both existing cached and native-pending errors survive.
 int untouched=1;Check(!Invoke(egl,"eglQuerySurface",{display,surface,0xffffffffU,Address(&untouched)}),"cached EGL_BAD_ATTRIBUTE prerequisite");
 Check(egl.CurrentReadPbufferExtent().has_value()&&Invoke(egl,"eglGetError")==EGL_BAD_ATTRIBUTE,"extent observation preserves public EGL error");
 auto egl_module=GetModuleHandleW(L"libEGL.dll");auto raw_query=GetProcAddress(egl_module,"eglQuerySurface");PFNEGLQUERYSURFACEPROC native_query;std::memcpy(&native_query,&raw_query,sizeof native_query);
 native_query(EGL_NO_DISPLAY,EGL_NO_SURFACE,EGL_WIDTH,&untouched);
 Check(egl.CurrentReadPbufferExtent().has_value()&&Invoke(egl,"eglGetError")==EGL_BAD_DISPLAY,"extent observation preserves pending native EGL error");
 Check(!Invoke(egl,"eglQuerySurface",{display,surface,0xffffffffU,Address(&untouched)}),"cached EGL error before combined native pending error");
 native_query(EGL_NO_DISPLAY,EGL_NO_SURFACE,EGL_WIDTH,&untouched);
 Check(egl.CurrentReadPbufferExtent().has_value()&&Invoke(egl,"eglGetError")==EGL_BAD_DISPLAY&&Invoke(egl,"eglGetError")==EGL_SUCCESS,"observer follows existing singular EGL native-pending precedence exactly once");
 // Shared GL names are driver-owned; VAOs are context local. No global shadow
 // ownership table rejects valid cross-context buffer/program usage.
 const auto shared=Create(context),shared_surface=Surface();Bind(shared,shared_surface);
 Check(NativeSymbol<PFNGLISPROGRAMPROC>("glIsProgram")(o.program)==GL_TRUE&&NativeSymbol<PFNGLISBUFFERPROC>("glIsBuffer")(o.buffers[0])==GL_TRUE,"programs/buffers shared by actual ANGLE group");
 Check(NativeSymbol<PFNGLISVERTEXARRAYPROC>("glIsVertexArray")(o.vao)==GL_FALSE,"VAO namespace genuinely context-local");
 ObjectQuery(o.vao,GL_FALSE);
 GLuint shared_vao=0;Invoke(gl,"glGenVertexArrays",{1,Address(&shared_vao)});Invoke(gl,"glBindVertexArray",{shared_vao});Invoke(gl,"glBindBuffer",{GL_ARRAY_BUFFER,o.buffers[0]});
 ObjectQuery(shared_vao,GL_TRUE);
 Invoke(gl,"glVertexAttribPointer",{0,2,GL_FLOAT,0,8,16});Invoke(gl,"glEnableVertexAttribArray",{0});Invoke(gl,"glBindBuffer",{GL_ELEMENT_ARRAY_BUFFER,o.buffers[1]});
 DrawObjects shared_objects=o;shared_objects.vao=shared_vao;Guest("gl_draw_render",{Address(&shared_objects),1,Address(actual.pixels.data())});Check(actual.pixels==reference_pixels,"NDK draw through shared program/VBO and local VAO");
 Invoke(gl,"glUseProgram",{0});Invoke(gl,"glDeleteVertexArrays",{1,Address(&shared_vao)});
 Bind(context,surface);Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"release context for cross-thread same-value tracked output");
 auto reservation=bunker::test::ReserveAcrossOperation(Address(&linked),4,[&]{Bind(context,surface);Guest("gl_draw_query",{o.program,GL_LINK_STATUS,Address(&linked)});egl.ReleaseCurrentThread();});
 Check(reservation.loaded==1&&reservation.status==1&&linked==1,"same-value GL query output invalidates cross-thread guest reservation");Bind(context,surface);
 alignas(64)std::array<uint8_t,512> packed;packed.fill(0xa5);const DrawRead gap{0,0,3,2,8,64,0,0};
 Guest("gl_draw_read",{Address(&gap),Address(packed.data())});Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"release read context for padding reservation");
 auto read_worker=[&]{Bind(context,surface);Guest("gl_draw_read",{Address(&gap),Address(packed.data())});egl.ReleaseCurrentThread();};
 auto padding=bunker::test::ReserveAcrossOperation(Address(packed.data()+64),4,read_worker);
 Check(padding.status==0,"pack row padding causes no tracked guest write");
 auto pixel=bunker::test::ReserveAcrossOperation(Address(packed.data()),4,read_worker);
 Check(pixel.status==1,"same-value readback pixels are real tracked guest writes");
 Bind(context,surface);GLuint temporary=0;Invoke(gl,"glGenBuffers",{1,Address(&temporary)});uint32_t source_word=0x3f800000;
 Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"release upload context for input reservation");
 auto input_reservation=bunker::test::ReserveAcrossOperation(Address(&source_word),4,[&]{Bind(context,surface);Invoke(gl,"glBindBuffer",{GL_ARRAY_BUFFER,temporary});Invoke(gl,"glBufferData",{GL_ARRAY_BUFFER,4,Address(&source_word),GL_STATIC_DRAW});egl.ReleaseCurrentThread();});
 Check(input_reservation.status==0&&source_word==0x3f800000,"buffer upload snapshots input without invalidating read-only guest reservation");
 Bind(context,surface);Invoke(gl,"glDeleteBuffers",{1,Address(&temporary)});Invoke(gl,"glBindBuffer",{GL_ARRAY_BUFFER,o.buffers[0]});
 const auto unshared=Create(0),unshared_surface=Surface();Bind(unshared,unshared_surface);Invoke(gl,"glUseProgram",{o.program});Check(Invoke(gl,"glGetError")==GL_INVALID_VALUE,"unshared GLuint validity comes from native context");
 ObjectQuery(o.vao,GL_FALSE);
 Bind(context,surface);Guest("gl_draw_delete_program",{o.program});Check(NativeSymbol<PFNGLISPROGRAMPROC>("glIsProgram")(o.program)==GL_TRUE,"delete current program remains driver-live until unbound");
 DrawObjects retired=o;retired.program=0;Guest("gl_draw_cleanup",{Address(&retired)});Check(NativeSymbol<PFNGLISPROGRAMPROC>("glIsProgram")(o.program)==GL_FALSE,"program retired when final current binding removed");
 Check(Invoke(egl,"eglDestroySurface",{display,surface}),"deleting current read pbuffer deferred");Check(egl.CurrentReadPbufferExtent().has_value(),"deferred-deleted current read pbuffer retains live extent");
 Guest("gl_draw_read",{Address(&reset),Address(actual.pixels.data())});Check(Invoke(gl,"glGetError")==0,"deferred-deleted live read pbuffer remains readable");
 Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0})&&!egl.CurrentReadPbufferExtent(),"unbound retired read pbuffer no longer exposed");
 Bind(reference_context,reference_surface);native_cleanup(&reference_objects);Check(Invoke(egl,"eglMakeCurrent",{display,0,0,0}),"final native context unbound");
 for(auto c:{reference_context,context,shared,unshared})Check(Invoke(egl,"eglDestroyContext",{display,c}),"context retired");
 for(auto s:{reference_surface,shared_surface,unshared_surface})Check(Invoke(egl,"eglDestroySurface",{display,s}),"pbuffer retired");
 Check(Invoke(egl,"eglTerminate",{display}),"real EGL display terminated");egl.ReleaseCurrentThread();egl.SetProcedureResolver({});
 std::printf("GL VAO predicate: %u NDK calls, %u lifecycle records; direct/pointer/procedure/native boolean ABI and context-local lifetime\n",object_calls,object_records);
 std::printf("GL typed draw: %u checks passed; 29 existing strict NDK signatures plus one GLboolean object query, shader/VBO/VAO indexed+array triangles, exact packed readback, real native lifetime/errors\n",checks);return 0;
 }catch(const std::exception &e){std::fprintf(stderr,"GL typed draw failure: %s\n",e.what());return 1;}}

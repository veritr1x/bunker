#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl32.h>
#include <GLES2/gl2ext.h>
#include "gl_host.h"
#include "egl_host.h"
#include "frame_png.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cerrno>
#include <cfenv>
#include <cstring>
#include <map>
#include <limits>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>

namespace bunker::windows {
namespace {
struct GlNativeEnvironment {
  DWORD error=GetLastError();int saved_errno=errno;std::fenv_t floating{};
  GlNativeEnvironment(){std::feholdexcept(&floating);}
  ~GlNativeEnvironment(){std::fesetenv(&floating);errno=saved_errno;SetLastError(error);}
};
#define GL_DRAW_API(X) \
 X(glCreateShader,PFNGLCREATESHADERPROC) X(glShaderSource,PFNGLSHADERSOURCEPROC) \
 X(glCompileShader,PFNGLCOMPILESHADERPROC) X(glGetShaderiv,PFNGLGETSHADERIVPROC) \
 X(glGetShaderInfoLog,PFNGLGETSHADERINFOLOGPROC) X(glDeleteShader,PFNGLDELETESHADERPROC) \
 X(glCreateProgram,PFNGLCREATEPROGRAMPROC) X(glAttachShader,PFNGLATTACHSHADERPROC) \
 X(glDetachShader,PFNGLDETACHSHADERPROC) X(glLinkProgram,PFNGLLINKPROGRAMPROC) \
 X(glGetProgramiv,PFNGLGETPROGRAMIVPROC) X(glGetProgramInfoLog,PFNGLGETPROGRAMINFOLOGPROC) \
 X(glUseProgram,PFNGLUSEPROGRAMPROC) X(glDeleteProgram,PFNGLDELETEPROGRAMPROC) \
 X(glGenBuffers,PFNGLGENBUFFERSPROC) X(glBindBuffer,PFNGLBINDBUFFERPROC) \
 X(glBufferData,PFNGLBUFFERDATAPROC) X(glBufferSubData,PFNGLBUFFERSUBDATAPROC) \
 X(glDeleteBuffers,PFNGLDELETEBUFFERSPROC) X(glGenVertexArrays,PFNGLGENVERTEXARRAYSPROC) \
 X(glBindVertexArray,PFNGLBINDVERTEXARRAYPROC) X(glDeleteVertexArrays,PFNGLDELETEVERTEXARRAYSPROC) \
 X(glEnableVertexAttribArray,PFNGLENABLEVERTEXATTRIBARRAYPROC) X(glDisableVertexAttribArray,PFNGLDISABLEVERTEXATTRIBARRAYPROC) \
 X(glVertexAttribPointer,PFNGLVERTEXATTRIBPOINTERPROC) X(glDrawArrays,PFNGLDRAWARRAYSPROC) \
 X(glDrawElements,PFNGLDRAWELEMENTSPROC) X(glReadPixels,PFNGLREADPIXELSPROC) X(glPixelStorei,PFNGLPIXELSTOREIPROC)
// Types and enum names: Khronos GLES registry-generated GLES3/gl32.h (MIT).
// Counts: GLES3.2 state tables and the pinned ANGLE GetQueryParameterInfo.
// This table deliberately excludes indexed queries and pointer-valued state.
const std::vector<GlHost::Query> queries={
  {GL_MAJOR_VERSION,1},{GL_MINOR_VERSION,1},{GL_NUM_EXTENSIONS,1},
  {GL_MAX_TEXTURE_SIZE,1},{GL_MAX_CUBE_MAP_TEXTURE_SIZE,1},{GL_MAX_3D_TEXTURE_SIZE,1},
  {GL_MAX_ARRAY_TEXTURE_LAYERS,1},{GL_MAX_RENDERBUFFER_SIZE,1},{GL_MAX_COLOR_ATTACHMENTS,1},
  {GL_MAX_DRAW_BUFFERS,1},{GL_MAX_SAMPLES,1},{GL_MAX_VERTEX_ATTRIBS,1},
  {GL_MAX_VERTEX_UNIFORM_VECTORS,1},{GL_MAX_FRAGMENT_UNIFORM_VECTORS,1},{GL_MAX_VARYING_VECTORS,1},
  {GL_MAX_VERTEX_UNIFORM_COMPONENTS,1},{GL_MAX_FRAGMENT_UNIFORM_COMPONENTS,1},
  {GL_MAX_VARYING_COMPONENTS,1},{GL_MAX_VERTEX_OUTPUT_COMPONENTS,1},{GL_MAX_FRAGMENT_INPUT_COMPONENTS,1},
  {GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS,1},{GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS,1},{GL_MAX_TEXTURE_IMAGE_UNITS,1},
  {GL_MAX_VERTEX_UNIFORM_BLOCKS,1},{GL_MAX_FRAGMENT_UNIFORM_BLOCKS,1},{GL_MAX_COMBINED_UNIFORM_BLOCKS,1},
  {GL_MAX_UNIFORM_BUFFER_BINDINGS,1},{GL_MAX_UNIFORM_BLOCK_SIZE,1},{GL_UNIFORM_BUFFER_OFFSET_ALIGNMENT,1},
  {GL_MAX_COMBINED_VERTEX_UNIFORM_COMPONENTS,1},{GL_MAX_COMBINED_FRAGMENT_UNIFORM_COMPONENTS,1},
  {GL_MAX_TRANSFORM_FEEDBACK_INTERLEAVED_COMPONENTS,1},{GL_MAX_TRANSFORM_FEEDBACK_SEPARATE_ATTRIBS,1},
  {GL_MAX_TRANSFORM_FEEDBACK_SEPARATE_COMPONENTS,1},{GL_MIN_PROGRAM_TEXEL_OFFSET,1},{GL_MAX_PROGRAM_TEXEL_OFFSET,1},
  {GL_MAX_ELEMENT_INDEX,1},{GL_MAX_ELEMENTS_INDICES,1},{GL_MAX_ELEMENTS_VERTICES,1},{GL_MAX_SERVER_WAIT_TIMEOUT,1},
  {GL_MAX_FRAMEBUFFER_WIDTH,1},{GL_MAX_FRAMEBUFFER_HEIGHT,1},{GL_MAX_FRAMEBUFFER_SAMPLES,1},
  {GL_MAX_VERTEX_ATTRIB_RELATIVE_OFFSET,1},{GL_MAX_VERTEX_ATTRIB_BINDINGS,1},{GL_MAX_VERTEX_ATTRIB_STRIDE,1},
  {GL_MAX_VERTEX_ATOMIC_COUNTER_BUFFERS,1},{GL_MAX_VERTEX_ATOMIC_COUNTERS,1},
  {GL_MAX_VERTEX_IMAGE_UNIFORMS,1},{GL_MAX_VERTEX_SHADER_STORAGE_BLOCKS,1},
  {GL_MAX_FRAGMENT_ATOMIC_COUNTER_BUFFERS,1},{GL_MAX_FRAGMENT_ATOMIC_COUNTERS,1},
  {GL_MAX_FRAGMENT_IMAGE_UNIFORMS,1},{GL_MAX_FRAGMENT_SHADER_STORAGE_BLOCKS,1},
  {GL_MIN_PROGRAM_TEXTURE_GATHER_OFFSET,1},{GL_MAX_PROGRAM_TEXTURE_GATHER_OFFSET,1},
  {GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS,1},{GL_MAX_COMPUTE_UNIFORM_BLOCKS,1},
  {GL_MAX_COMPUTE_TEXTURE_IMAGE_UNITS,1},{GL_MAX_COMPUTE_SHARED_MEMORY_SIZE,1},{GL_MAX_COMPUTE_UNIFORM_COMPONENTS,1},
  {GL_MAX_COMPUTE_ATOMIC_COUNTER_BUFFERS,1},{GL_MAX_COMPUTE_ATOMIC_COUNTERS,1},
  {GL_MAX_COMPUTE_IMAGE_UNIFORMS,1},{GL_MAX_COMBINED_COMPUTE_UNIFORM_COMPONENTS,1},
  {GL_MAX_COMPUTE_SHADER_STORAGE_BLOCKS,1},{GL_MAX_COMBINED_SHADER_OUTPUT_RESOURCES,1},{GL_MAX_UNIFORM_LOCATIONS,1},
  {GL_MAX_ATOMIC_COUNTER_BUFFER_BINDINGS,1},{GL_MAX_ATOMIC_COUNTER_BUFFER_SIZE,1},
  {GL_MAX_COMBINED_ATOMIC_COUNTER_BUFFERS,1},{GL_MAX_COMBINED_ATOMIC_COUNTERS,1},
  {GL_MAX_IMAGE_UNITS,1},{GL_MAX_COMBINED_IMAGE_UNIFORMS,1},
  {GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS,1},{GL_MAX_COMBINED_SHADER_STORAGE_BLOCKS,1},
  {GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT,1},{GL_MAX_SHADER_STORAGE_BLOCK_SIZE,1},
  {GL_MAX_SAMPLE_MASK_WORDS,1},{GL_MAX_COLOR_TEXTURE_SAMPLES,1},{GL_MAX_DEPTH_TEXTURE_SAMPLES,1},{GL_MAX_INTEGER_SAMPLES,1},
  {GL_NUM_COMPRESSED_TEXTURE_FORMATS,1},{GL_NUM_SHADER_BINARY_FORMATS,1},{GL_NUM_PROGRAM_BINARY_FORMATS,1},
  {GL_SHADER_COMPILER,1},{GL_IMPLEMENTATION_COLOR_READ_TYPE,1},{GL_IMPLEMENTATION_COLOR_READ_FORMAT,1},
  {GL_SUBPIXEL_BITS,1},{GL_SAMPLE_BUFFERS,1},{GL_SAMPLES,1},
  {GL_PACK_ALIGNMENT,1},{GL_UNPACK_ALIGNMENT,1},{GL_PACK_ROW_LENGTH,1},{GL_PACK_SKIP_ROWS,1},{GL_PACK_SKIP_PIXELS,1},
  {GL_UNPACK_ROW_LENGTH,1},{GL_UNPACK_IMAGE_HEIGHT,1},{GL_UNPACK_SKIP_ROWS,1},{GL_UNPACK_SKIP_PIXELS,1},{GL_UNPACK_SKIP_IMAGES,1},
  {GL_CURRENT_PROGRAM,1},{GL_ACTIVE_TEXTURE,1},{GL_VERTEX_ARRAY_BINDING,1},
  {GL_ARRAY_BUFFER_BINDING,1},{GL_ELEMENT_ARRAY_BUFFER_BINDING,1},{GL_PIXEL_PACK_BUFFER_BINDING,1},{GL_PIXEL_UNPACK_BUFFER_BINDING,1},
  {GL_FRAMEBUFFER_BINDING,1},{GL_READ_FRAMEBUFFER_BINDING,1},{GL_RENDERBUFFER_BINDING,1},
  {GL_BLEND,1},{GL_DEPTH_TEST,1},{GL_STENCIL_TEST,1},{GL_SCISSOR_TEST,1},{GL_CULL_FACE,1},{GL_DITHER,1},
  {GL_RASTERIZER_DISCARD,1},{GL_DEPTH_WRITEMASK,1},{GL_DEPTH_CLEAR_VALUE,1},{GL_LINE_WIDTH,1},
  {GL_MAX_VIEWPORT_DIMS,2},{GL_ALIASED_LINE_WIDTH_RANGE,2},{GL_ALIASED_POINT_SIZE_RANGE,2},{GL_DEPTH_RANGE,2},
  {GL_VIEWPORT,4},{GL_SCISSOR_BOX,4},{GL_COLOR_CLEAR_VALUE,4},{GL_BLEND_COLOR,4},{GL_COLOR_WRITEMASK,4},
  {GL_COMPRESSED_TEXTURE_FORMATS,0,GL_NUM_COMPRESSED_TEXTURE_FORMATS},
  {GL_SHADER_BINARY_FORMATS,0,GL_NUM_SHADER_BINARY_FORMATS},
  {GL_PROGRAM_BINARY_FORMATS,0,GL_NUM_PROGRAM_BINARY_FORMATS},
  {GL_MAX_GEOMETRY_SHADER_STORAGE_BLOCKS,1},
  {GL_MAX_TESS_CONTROL_SHADER_STORAGE_BLOCKS,1},
  {GL_MAX_TESS_EVALUATION_SHADER_STORAGE_BLOCKS,1},
  {0x84ff,1}, // GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT, GLES2/gl2ext.h.
  {GL_RED_BITS,1},
  {GL_GREEN_BITS,1},
  {GL_BLUE_BITS,1},
  {GL_ALPHA_BITS,1},
  {GL_DEPTH_BITS,1},
  {GL_STENCIL_BITS,1},
};
const char *const names[]={"glGetString","glGetStringi","glGetIntegerv","glGetFloatv","glGetBooleanv","glGetError",
#define GL_SCALAR(name, native_type, signature) #name,
#include "gl_scalar_commands.inc"
#undef GL_SCALAR
#define DRAW_NAME(name,type) #name,
GL_DRAW_API(DRAW_NAME)
#undef DRAW_NAME
#define GL_TEXTURE_COMMAND(name,type) #name,
#include "gl_texture_commands.inc"
#undef GL_TEXTURE_COMMAND
#define GL_UNIFORM_COMMAND(name,type) #name,
#include "gl_uniform_commands.inc"
#undef GL_UNIFORM_COMMAND
#define GL_FRAMEBUFFER_COMMAND(name,type) #name,
#include "gl_framebuffer_commands.inc"
#undef GL_FRAMEBUFFER_COMMAND
#define GL_MISC_COMMAND(name,type) #name,
#include "gl_misc_commands.inc"
#undef GL_MISC_COMMAND
#define GL_INDEXED_COMMAND(name,type) #name,
#include "gl_indexed_commands.inc"
#undef GL_INDEXED_COMMAND
#define GL_INTERNALFORMAT_COMMAND(name,type) #name,
#include "gl_internalformat_commands.inc"
#undef GL_INTERNALFORMAT_COMMAND
#define GL_SAMPLER_COMMAND(name,type) #name,
#include "gl_sampler_commands.inc"
#undef GL_SAMPLER_COMMAND
#define GL_BUFFER_INDEXED_COMMAND(name,type) #name,
#include "gl_buffer_indexed_commands.inc"
#undef GL_BUFFER_INDEXED_COMMAND
#define GL_OBJECT_COMMAND(name,native_type,signature) #name,
#include "gl_object_commands.inc"
#undef GL_OBJECT_COMMAND
#define GL_STORAGE_COMMAND(name,native_type,signature) #name,
#include "gl_storage_commands.inc"
#undef GL_STORAGE_COMMAND
#define GL_LABEL_COMMAND(name,type) #name,
#include "gl_label_commands.inc"
#undef GL_LABEL_COMMAND
#define GL_TEXTURE3D_COMMAND(name,type) #name,
#include "gl_texture3d_commands.inc"
#undef GL_TEXTURE3D_COMMAND
#define GL_UNIFORM_BLOCK_COMMAND(name,type) #name,
#include "gl_uniform_block_commands.inc"
#undef GL_UNIFORM_BLOCK_COMMAND
#define GL_PROGRAM_RESOURCE_COMMAND(name,type) #name,
#include "gl_program_resource_commands.inc"
#undef GL_PROGRAM_RESOURCE_COMMAND
#define GL_MAPPING_COMMAND(name,type) #name,
#include "gl_mapping_commands.inc"
#undef GL_MAPPING_COMMAND
"glDrawBuffers",
"glGetObjectLabel",
"glGetObjectLabelEXT",
"glInvalidateFramebuffer",
"glDiscardFramebufferEXT",
"glProgramParameteri",
"glGetProgramBinary",
"glProgramBinary",
"glFenceSync",
"glClientWaitSync",
"glDeleteSync",
};
std::string Hex(GLenum value){std::ostringstream out;out<<"0x"<<std::hex<<value;return out.str();}
template<class T>T Symbol(HMODULE module,const char *name){
  const auto native=GetProcAddress(module,name);if(!native)throw std::runtime_error(std::string("Missing ANGLE GL symbol: ")+name);
  T typed;static_assert(sizeof(typed)==sizeof(native));std::memcpy(&typed,&native,sizeof(typed));return typed;
}
}
struct GlHost::Impl {
  EglHost &egl;
  PFNGLDRAWBUFFERSPROC drawBuffers=nullptr;
  addr_t current_context=0;
  addr_t current_share_group=0;
  struct MappedRange {addr_t address;size_t length;};
  using MappedKey=std::pair<addr_t,GLuint>;
  std::map<MappedKey,MappedRange> mapped_ranges;
  std::map<addr_t,std::set<GLenum>> pending_errors;
  HMODULE module=nullptr;addr_t marker;bool installed=false;
  std::mutex mutex;
  PFNGLGETSTRINGPROC getString=nullptr;PFNGLGETSTRINGIPROC getStringi=nullptr;
  PFNGLGETINTEGERVPROC getInteger=nullptr;PFNGLGETFLOATVPROC getFloat=nullptr;
  PFNGLGETBOOLEANVPROC getBoolean=nullptr;PFNGLGETERRORPROC getError=nullptr;
  PFNGLGETVERTEXATTRIBIVPROC getVertexAttrib=nullptr;
#define DRAW_FIELD(name,type) type draw_##name=nullptr;
  GL_DRAW_API(DRAW_FIELD)
#undef DRAW_FIELD
#define GL_TEXTURE_COMMAND(name,type) type texture_##name=nullptr;
#include "gl_texture_commands.inc"
#undef GL_TEXTURE_COMMAND
#define GL_UNIFORM_COMMAND(name,type) type uniform_##name=nullptr;
#include "gl_uniform_commands.inc"
#undef GL_UNIFORM_COMMAND
#define GL_FRAMEBUFFER_COMMAND(name,type) type framebuffer_##name=nullptr;
#include "gl_framebuffer_commands.inc"
#undef GL_FRAMEBUFFER_COMMAND
#define GL_MISC_COMMAND(name,type) type misc_##name=nullptr;
#include "gl_misc_commands.inc"
#undef GL_MISC_COMMAND
#define GL_INDEXED_COMMAND(name,type) type indexed_##name=nullptr;
#include "gl_indexed_commands.inc"
#undef GL_INDEXED_COMMAND
#define GL_INTERNALFORMAT_COMMAND(name,type) type internalformat_##name=nullptr;
#include "gl_internalformat_commands.inc"
#undef GL_INTERNALFORMAT_COMMAND
#define GL_SAMPLER_COMMAND(name,type) type sampler_##name=nullptr;
#include "gl_sampler_commands.inc"
#undef GL_SAMPLER_COMMAND
#define GL_BUFFER_INDEXED_COMMAND(name,type) type buffer_indexed_##name=nullptr;
#include "gl_buffer_indexed_commands.inc"
#undef GL_BUFFER_INDEXED_COMMAND
#define GL_UNIFORM_BLOCK_COMMAND(name,type) type uniform_block_##name=nullptr;
#include "gl_uniform_block_commands.inc"
#undef GL_UNIFORM_BLOCK_COMMAND
#define GL_PROGRAM_RESOURCE_COMMAND(name,type) type program_resource_##name=nullptr;
#include "gl_program_resource_commands.inc"
#undef GL_PROGRAM_RESOURCE_COMMAND
#define GL_MAPPING_COMMAND(name,type) type mapping_##name=nullptr;
#include "gl_mapping_commands.inc"
#undef GL_MAPPING_COMMAND
  std::map<std::string,std::unique_ptr<char[]>> strings;
  std::map<std::string,std::function<void(State&)>> bridges;
  std::wstring diagnostic_png;
  FrameDiagnostics diagnostic;
  struct PendingPresent {
    uint64_t serial=0;DWORD thread=0;addr_t display=0,surface=0,context=0;
    int32_t width=0,height=0;bool nonuniform=false,candidate=false;
    uint64_t draws=0,clears=0;std::vector<uint8_t> pixels;
  };
  uint64_t next_present_serial=0;
  std::map<uint64_t,PendingPresent> pending_presents;
  Impl(EglHost &egl,const std::wstring &directory,addr_t marker):egl(egl),marker(marker){
    static_assert(sizeof(GLboolean)==1&&sizeof(GLint)==4&&sizeof(GLfloat)==4);
    static_assert(sizeof(GLenum)==4&&sizeof(GLuint)==4&&sizeof(GLsizei)==4&&sizeof(GLchar)==1&&sizeof(GLsizeiptr)==8&&sizeof(GLintptr)==8);
    if((marker&7)||marker>UINT64_MAX-std::size(names)*8)throw std::invalid_argument("GL marker range/alignment");
    if(directory.size()<3||directory[1]!=L':'||!(directory[2]==L'\\'||directory[2]==L'/'))throw std::invalid_argument("ANGLE GL DLL directory must be absolute");
    module=LoadLibraryExW((directory+L"\\libGLESv2.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!module)throw std::runtime_error("Cannot load pinned ANGLE GLES DLL");
    try{
      if(!egl.UsesGlesModule(module))throw std::invalid_argument("GL and EGL must use the same native GLES module");
      getString=Symbol<PFNGLGETSTRINGPROC>(module,"glGetString");getStringi=Symbol<PFNGLGETSTRINGIPROC>(module,"glGetStringi");
      getInteger=Symbol<PFNGLGETINTEGERVPROC>(module,"glGetIntegerv");getFloat=Symbol<PFNGLGETFLOATVPROC>(module,"glGetFloatv");
      getBoolean=Symbol<PFNGLGETBOOLEANVPROC>(module,"glGetBooleanv");getError=Symbol<PFNGLGETERRORPROC>(module,"glGetError");
      getVertexAttrib=Symbol<PFNGLGETVERTEXATTRIBIVPROC>(module,"glGetVertexAttribiv");
#define DRAW_LOAD(name,type) draw_##name=Symbol<type>(module,#name);
      GL_DRAW_API(DRAW_LOAD)
#undef DRAW_LOAD
#define GL_TEXTURE_COMMAND(name,type) texture_##name=Symbol<type>(module,#name);
#include "gl_texture_commands.inc"
#undef GL_TEXTURE_COMMAND
#define GL_UNIFORM_COMMAND(name,type) uniform_##name=Symbol<type>(module,#name);
#include "gl_uniform_commands.inc"
#undef GL_UNIFORM_COMMAND
#define GL_FRAMEBUFFER_COMMAND(name,type) framebuffer_##name=Symbol<type>(module,#name);
#include "gl_framebuffer_commands.inc"
#undef GL_FRAMEBUFFER_COMMAND
#define GL_MISC_COMMAND(name,type) misc_##name=Symbol<type>(module,#name);
#include "gl_misc_commands.inc"
#undef GL_MISC_COMMAND
#define GL_INDEXED_COMMAND(name,type) indexed_##name=Symbol<type>(module,#name);
#include "gl_indexed_commands.inc"
#undef GL_INDEXED_COMMAND
#define GL_INTERNALFORMAT_COMMAND(name,type) internalformat_##name=Symbol<type>(module,#name);
#include "gl_internalformat_commands.inc"
#undef GL_INTERNALFORMAT_COMMAND
#define GL_SAMPLER_COMMAND(name,type) sampler_##name=Symbol<type>(module,#name);
#include "gl_sampler_commands.inc"
#undef GL_SAMPLER_COMMAND
#define GL_BUFFER_INDEXED_COMMAND(name,type) buffer_indexed_##name=Symbol<type>(module,#name);
#include "gl_buffer_indexed_commands.inc"
#undef GL_BUFFER_INDEXED_COMMAND
#define GL_UNIFORM_BLOCK_COMMAND(name,type) uniform_block_##name=Symbol<type>(module,#name);
#include "gl_uniform_block_commands.inc"
#undef GL_UNIFORM_BLOCK_COMMAND
#define GL_PROGRAM_RESOURCE_COMMAND(name,type) program_resource_##name=Symbol<type>(module,#name);
#include "gl_program_resource_commands.inc"
#undef GL_PROGRAM_RESOURCE_COMMAND
#define GL_MAPPING_COMMAND(name,type) mapping_##name=Symbol<type>(module,#name);
#include "gl_mapping_commands.inc"
#undef GL_MAPPING_COMMAND
      drawBuffers=Symbol<PFNGLDRAWBUFFERSPROC>(module,"glDrawBuffers");
      Bindings();
      egl.SetStorageRetirementObserver([this]{GlNativeEnvironment environment;std::lock_guard lock(mutex);InvalidateMappings(true);});
    }catch(...){FreeLibrary(module);throw;}
  }
  ~Impl(){egl.SetStorageRetirementObserver({});InvalidateMappings(false);for(const auto &[text,value]:strings)recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(value.get()),text.size()+1);FreeLibrary(module);}
  void SelectContext(){
    // Provider tokens stay unique even if ANGLE recycles a native pointer.
    // Stored flags follow a context when it migrates between native threads.
    current_context=egl.CurrentContextToken();
    if(!current_context)throw std::runtime_error("GL requires an owned current EGL context");
    current_share_group=egl.CurrentShareGroupToken();
    if(!current_share_group)throw std::runtime_error("GL current context has no owned share group");
    PruneMappings();
    for(auto at=pending_errors.begin();at!=pending_errors.end();)
      if(!egl.ContextAlive(at->first))at=pending_errors.erase(at);else ++at;
  }
  bool CollectErrors(){
    bool any=false;for(unsigned n=0;n<32;++n){GLenum value=getError();if(value==GL_NO_ERROR)return any;
      pending_errors[current_context].insert(value);any=true;}
    throw std::runtime_error("Native GL error flags did not drain within32 reads");
  }
  std::optional<size_t> Components(GLenum name){
    auto found=std::find_if(queries.begin(),queries.end(),[&](const Query &q){return q.name==name;});
    if(found==queries.end())throw std::runtime_error("Unsupported GL query output width: "+Hex(name));
    if(!found->count_query)return found->count;
    GLint count=-1;CollectErrors();getInteger(found->count_query,&count);if(CollectErrors())return std::nullopt;
    if(count<0||count>1048576)throw std::runtime_error("Native GL array query count out of bounded range: "+Hex(name));
    return size_t(count);
  }
  addr_t String(const GLubyte *native){
    if(!native)return 0;
    std::string text(reinterpret_cast<const char*>(native));
    auto found=strings.find(text);if(found!=strings.end())return reinterpret_cast<addr_t>(found->second.get());
    auto copy=std::make_unique<char[]>(text.size()+1);const auto address=reinterpret_cast<addr_t>(copy.get());
    recomp::WriteGuestMemory(address,text.c_str(),text.size()+1);strings.emplace(text,std::move(copy));return address;
  }
  template<class T,class F>void QueryValues(GLenum name,addr_t output,F native){
    if(!output)throw std::invalid_argument("Null GL query output");
    auto count=Components(name);if(!count)return;
    std::vector<T> values(std::max<size_t>(1,*count));CollectErrors();native(name,values.data());
    if(!CollectErrors()&&*count)recomp::WriteGuestMemory(output,values.data(),*count*sizeof(T));
  }
  template<class S,class F>void Bind(const char *name,F function){bridges.emplace(name,recomp::MakeBridge<S>(std::move(function)));}
  static constexpr size_t TransferLimit=64*1024*1024;
  static void Range(addr_t address,size_t size){
    if(size&&(!address||size>UINT64_MAX-address))throw std::invalid_argument("Invalid guest GL transfer range");
  }
  static std::vector<uint8_t> Snapshot(addr_t address,size_t size){
    if(size>TransferLimit)throw std::runtime_error("GL copied transfer exceeds64MiB scope");
    Range(address,size);std::vector<uint8_t> bytes(size);
    if(size)recomp::ReadGuestMemory(bytes.data(),address,size);
    return bytes;
  }
  template<class F>bool Call(F function){CollectErrors();function();return !CollectErrors();}
  uint64_t CaptureWindow(addr_t display,addr_t surface){
    const auto thread=GetCurrentThreadId();
    // There can be only one outstanding original swap on each native thread.
    // A new ENTER abandons any unmatched previous ticket on that thread.
    for(auto at=pending_presents.begin();at!=pending_presents.end();)
      if(at->second.thread==thread)at=pending_presents.erase(at);else ++at;
    if(diagnostic_png.empty()||diagnostic.frame_png)return 0;
    auto extent=egl.CurrentDrawWindowExtent();if(!extent||extent->surface!=surface)return 0;
    SelectContext();if(extent->context!=current_context)throw std::runtime_error("Capture context changed");
    if(uint64_t(extent->width)*uint64_t(extent->height)*4>TransferLimit)throw std::runtime_error("Capture exceeds64MiB");
    if(diagnostic.first_present_png&&!diagnostic.draw_submissions)return 0;
    if(next_present_serial==UINT64_MAX)throw std::overflow_error("Capture serial exhausted");
    const auto serial=++next_present_serial;
    ++diagnostic.capture_attempts;
    CollectErrors();const auto saved_errors=pending_errors[current_context];
    struct ErrorRestore {Impl &host;std::set<GLenum> saved;~ErrorRestore(){
      for(unsigned i=0;i<32&&host.getError()!=GL_NO_ERROR;++i){}
      if(saved.empty())host.pending_errors.erase(host.current_context);else host.pending_errors[host.current_context]=saved;
    }} errors{*this,saved_errors};
    auto check=[&](const char *operation){const auto error=getError();if(error!=GL_NO_ERROR)throw std::runtime_error(std::string(operation)+" GL error="+Hex(error));};
    const auto *version=getString(GL_VERSION);check("capture version");
    const bool es3=version&&std::strstr(reinterpret_cast<const char*>(version),"OpenGL ES 3");
    const auto *vendor=getString(GL_VENDOR),*renderer=getString(GL_RENDERER);check("capture renderer");
    std::fprintf(stderr,"First frame: readback context=%#llx surface=%#llx %dx%d vendor=%s renderer=%s version=%s\n",(unsigned long long)extent->context,(unsigned long long)extent->surface,extent->width,extent->height,vendor?reinterpret_cast<const char*>(vendor):"",renderer?reinterpret_cast<const char*>(renderer):"",version?reinterpret_cast<const char*>(version):"");
    auto bindFramebuffer=Symbol<PFNGLBINDFRAMEBUFFERPROC>(module,"glBindFramebuffer");
    PFNGLREADBUFFERPROC readBuffer=es3?Symbol<PFNGLREADBUFFERPROC>(module,"glReadBuffer"):nullptr;
    GLint framebuffer=0,pack=4,pbo=0,row=0,skiprows=0,skippixels=0,default_read=GL_BACK;
    getInteger(es3?GL_READ_FRAMEBUFFER_BINDING:GL_FRAMEBUFFER_BINDING,&framebuffer);getInteger(GL_PACK_ALIGNMENT,&pack);
    if(es3){getInteger(GL_PIXEL_PACK_BUFFER_BINDING,&pbo);getInteger(GL_PACK_ROW_LENGTH,&row);getInteger(GL_PACK_SKIP_ROWS,&skiprows);getInteger(GL_PACK_SKIP_PIXELS,&skippixels);}check("capture saved state");
    struct StateRestore {
      Impl &host;PFNGLBINDFRAMEBUFFERPROC bind;PFNGLREADBUFFERPROC read;bool es3;GLint framebuffer,pack,pbo,row,skiprows,skippixels,default_read=GL_BACK;bool bound=false;
      ~StateRestore(){
        if(bound){if(es3)read(GLenum(default_read));bind(es3?GL_READ_FRAMEBUFFER:GL_FRAMEBUFFER,GLuint(framebuffer));}
        host.draw_glPixelStorei(GL_PACK_ALIGNMENT,pack);
        if(es3){host.draw_glPixelStorei(GL_PACK_ROW_LENGTH,row);host.draw_glPixelStorei(GL_PACK_SKIP_ROWS,skiprows);host.draw_glPixelStorei(GL_PACK_SKIP_PIXELS,skippixels);host.draw_glBindBuffer(GL_PIXEL_PACK_BUFFER,GLuint(pbo));}
      }
    } restore{*this,bindFramebuffer,readBuffer,es3,framebuffer,pack,pbo,row,skiprows,skippixels};
    bindFramebuffer(es3?GL_READ_FRAMEBUFFER:GL_FRAMEBUFFER,0);check("capture default framebuffer");restore.bound=true;
    if(es3){getInteger(GL_READ_BUFFER,&default_read);check("capture default read state");restore.default_read=default_read;readBuffer(GL_BACK);draw_glBindBuffer(GL_PIXEL_PACK_BUFFER,0);draw_glPixelStorei(GL_PACK_ROW_LENGTH,0);draw_glPixelStorei(GL_PACK_SKIP_ROWS,0);draw_glPixelStorei(GL_PACK_SKIP_PIXELS,0);}
    draw_glPixelStorei(GL_PACK_ALIGNMENT,1);check("capture pack state");
    std::vector<uint8_t> pixels(size_t(extent->width)*size_t(extent->height)*4);
    draw_glReadPixels(0,0,extent->width,extent->height,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());check("capture read pixels");
    bool nonuniform=false;for(size_t i=4;i<pixels.size();i+=4)if(std::memcmp(pixels.data(),pixels.data()+i,4)){nonuniform=true;break;}
    PendingPresent pending;pending.serial=serial;pending.thread=thread;pending.display=display;
    pending.surface=surface;pending.context=extent->context;pending.width=extent->width;pending.height=extent->height;
    pending.nonuniform=nonuniform;pending.candidate=nonuniform&&diagnostic.draw_submissions;
    pending.draws=diagnostic.draw_submissions;pending.clears=diagnostic.clear_submissions;
    if(pending.candidate||!diagnostic.first_present_png)pending.pixels=std::move(pixels);
    pending_presents.emplace(serial,std::move(pending));
    std::fprintf(stderr,"First frame: capture ticket=%llu native_tid=%lu display=%#llx context=%#llx surface=%#llx nonuniform=%d candidate=%d; awaiting same original swap outcome\n",(unsigned long long)serial,thread,(unsigned long long)display,(unsigned long long)extent->context,(unsigned long long)surface,int(nonuniform),int(nonuniform&&diagnostic.draw_submissions));
    return serial;
  }
  void FinishPresent(uint64_t serial,addr_t display,addr_t surface,uint32_t actual_result){
    if(!serial)return;
    auto at=pending_presents.find(serial);if(at==pending_presents.end())return;
    auto pending=std::move(at->second);pending_presents.erase(at); // consume even a failed/mismatched return
    const auto thread=GetCurrentThreadId();bool matched=pending.thread==thread&&pending.display==display&&pending.surface==surface;
    if(matched){auto extent=egl.CurrentDrawWindowExtent();matched=extent&&extent->context==pending.context&&extent->surface==pending.surface&&extent->width==pending.width&&extent->height==pending.height;}
    std::fprintf(stderr,"First frame: capture outcome ticket=%llu native_tid=%lu display=%#llx context=%#llx surface=%#llx EGLresult=%u matched=%d candidate=%d\n",(unsigned long long)serial,thread,(unsigned long long)display,(unsigned long long)pending.context,(unsigned long long)surface,actual_result,int(matched),int(pending.candidate));
    if(!matched||actual_result!=1||pending.pixels.empty()||diagnostic.frame_png)return;
    std::filesystem::path path(diagnostic_png);
    if(!pending.candidate){if(diagnostic.first_present_png)return;path=path.parent_path()/L"first-present.png";}
    WriteFramePng(path,uint32_t(pending.width),uint32_t(pending.height),pending.pixels);
    diagnostic.first_present_png=true;diagnostic.width=pending.width;diagnostic.height=pending.height;
    diagnostic.nonuniform=pending.nonuniform;diagnostic.failure.clear();
    if(pending.candidate){diagnostic.frame_png=true;diagnostic.presented_capture_serial=serial;
      diagnostic.presented_native_thread=thread;diagnostic.presented_display=display;
      diagnostic.presented_context=pending.context;diagnostic.presented_surface=surface;}
    std::fprintf(stderr,"First frame: PNG=%s ticket=%llu native_tid=%lu display=%#llx context=%#llx surface=%#llx draws=%llu clears=%llu nonuniform=%d candidate=%d same_original_swap_EGL_TRUE=1\n",path.u8string().c_str(),(unsigned long long)serial,thread,(unsigned long long)display,(unsigned long long)pending.context,(unsigned long long)surface,(unsigned long long)pending.draws,(unsigned long long)pending.clears,int(pending.nonuniform),int(pending.candidate));
  }

  GLint Integer(GLenum name){
    GLint value=0;if(!Call([&]{getInteger(name,&value);}))throw std::runtime_error("Internal GL state query failed: "+Hex(name));return value;
  }
  void ShaderSource(GLuint shader,GLsizei count,addr_t strings,addr_t lengths){
    if(count<=0){draw_glShaderSource(shader,count,nullptr,nullptr);return;}
    if(count>4096)throw std::runtime_error("GL shader source exceeds4096 strings");
    std::vector<addr_t> pointers(count);std::vector<GLint> sizes(count,-1);
    Range(strings,size_t(count)*8);recomp::ReadGuestMemory(pointers.data(),strings,size_t(count)*8);
    if(lengths){Range(lengths,size_t(count)*4);recomp::ReadGuestMemory(sizes.data(),lengths,size_t(count)*4);}
    std::vector<std::vector<GLchar>> owned(count);std::vector<const GLchar*> native(count);size_t total=0;
    for(GLsizei i=0;i<count;++i){
      if(sizes[i]>=0){
        if(size_t(sizes[i])>TransferLimit-total)throw std::runtime_error("GL shader source exceeds64MiB");
        auto bytes=Snapshot(pointers[i],size_t(sizes[i]));owned[i].assign(bytes.begin(),bytes.end());total+=bytes.size();
      }else{
        for(;;){
          if(total==TransferLimit)throw std::runtime_error("Unterminated/oversized GL shader source");
          Range(pointers[i],owned[i].size()+1);GLchar c;recomp::ReadGuestMemory(&c,pointers[i]+owned[i].size(),1);
          if(!c)break;
          owned[i].push_back(c);++total;
        }
        sizes[i]=static_cast<GLint>(owned[i].size());
      }
      owned[i].push_back(0);native[i]=owned[i].data();
    }
    draw_glShaderSource(shader,count,native.data(),sizes.data());
  }
  static size_t ObjectComponents(bool program,GLenum pname){
    if(!program){switch(pname){case GL_SHADER_TYPE:case GL_DELETE_STATUS:case GL_COMPILE_STATUS:case GL_INFO_LOG_LENGTH:case GL_SHADER_SOURCE_LENGTH:return 1;}}
    else{switch(pname){
      case GL_COMPUTE_WORK_GROUP_SIZE:return 3;
      case GL_DELETE_STATUS:case GL_LINK_STATUS:case GL_VALIDATE_STATUS:case GL_INFO_LOG_LENGTH:case GL_ATTACHED_SHADERS:
      case GL_ACTIVE_ATTRIBUTES:case GL_ACTIVE_ATTRIBUTE_MAX_LENGTH:case GL_ACTIVE_UNIFORMS:case GL_ACTIVE_UNIFORM_MAX_LENGTH:
      case GL_PROGRAM_BINARY_RETRIEVABLE_HINT:case GL_PROGRAM_BINARY_LENGTH:case GL_ACTIVE_UNIFORM_BLOCKS:case GL_ACTIVE_UNIFORM_BLOCK_MAX_NAME_LENGTH:
      case GL_TRANSFORM_FEEDBACK_BUFFER_MODE:case GL_TRANSFORM_FEEDBACK_VARYINGS:case GL_TRANSFORM_FEEDBACK_VARYING_MAX_LENGTH:return 1;
    }}
    throw std::runtime_error("Unsupported GL object query output width: "+Hex(pname));
  }
  template<class F>void ObjectQuery(GLuint object,GLenum pname,addr_t output,bool program,F native){
    const auto count=ObjectComponents(program,pname);Range(output,count*4);GLint values[3]{};
    if(Call([&]{native(object,pname,values);}))recomp::WriteGuestMemory(output,values,count*4);
  }
  template<class F>void InfoLog(GLuint object,GLsizei capacity,addr_t length,addr_t output,F native){
    if(capacity<0){GLsizei dummy=0;GLchar byte=0;native(object,capacity,&dummy,&byte);return;}
    if(size_t(capacity)>TransferLimit)throw std::runtime_error("GL info log exceeds64MiB");
    if(length)Range(length,4);
    if(capacity)Range(output,capacity);
    std::vector<GLchar> bytes(std::max<GLsizei>(capacity,1));GLsizei written=-1;
    if(!Call([&]{native(object,capacity,&written,bytes.data());}))return;
    if(written<0||(capacity?written>=capacity:written!=0))throw std::runtime_error("Invalid native GL info log length");
    if(capacity)recomp::WriteGuestMemory(output,bytes.data(),size_t(written)+1);
    if(length)recomp::WriteGuestMemory(length,&written,4);
  }
  template<class F>void Generate(GLsizei count,addr_t output,F native){
    if(count<=0){GLuint dummy=0;native(count,&dummy);return;}
    if(size_t(count)>TransferLimit/4)throw std::runtime_error("GL name output exceeds64MiB");
    Range(output,size_t(count)*4);std::vector<GLuint> values(count);
    if(Call([&]{native(count,values.data());}))recomp::WriteGuestMemory(output,values.data(),size_t(count)*4);
  }
  template<class F>void DeleteNames(GLsizei count,addr_t input,F native){
    if(count<=0){GLuint dummy=0;native(count,&dummy);return;}
    auto bytes=Snapshot(input,size_t(count)*4);std::vector<GLuint> names(count);std::memcpy(names.data(),bytes.data(),bytes.size());native(count,names.data());
  }
  void Upload(GLenum target,int64_t size,addr_t data,GLenum usage){
    std::vector<uint8_t> bytes;if(size>0&&data)bytes=Snapshot(data,static_cast<uint64_t>(size));
    const auto key=BoundMappedKey(target);
    if(Call([&]{draw_glBufferData(target,size,bytes.empty()?nullptr:bytes.data(),usage);})&&key)RetireMapping(*key);
  }
  void SubUpload(GLenum target,int64_t offset,int64_t size,addr_t data){
    if(offset<0||size<=0){draw_glBufferSubData(target,offset,size,nullptr);return;}
    auto bytes=Snapshot(data,static_cast<uint64_t>(size));draw_glBufferSubData(target,offset,size,bytes.data());
  }
  void DrawBuffers(GLsizei count,addr_t input){
    // ANGLE validates negative/over-limit counts and nonzero null pointers
    // before reading the array. Zero also belongs to native FBO validation.
    if(count<=0||!input){drawBuffers(count,nullptr);return;}
    const GLint maximum=Integer(GL_MAX_DRAW_BUFFERS);
    if(maximum<=0)throw std::runtime_error("Invalid native maximum draw-buffer count");
    if(count>maximum){drawBuffers(count,nullptr);return;}
    auto bytes=Snapshot(input,static_cast<size_t>(count)*sizeof(GLenum));
    std::vector<GLenum> values(static_cast<size_t>(count));
    std::memcpy(values.data(),bytes.data(),bytes.size());
    drawBuffers(count,values.data());
  }
  void ProgramBinary(GLuint program,GLenum format,addr_t input,GLsizei length,PFNGLPROGRAMBINARYPROC native){
    // The pinned driver converts a negative length to size_t without validating
    // it. Such a span cannot be copied under the checked guest-memory contract.
    if(length<0)throw std::runtime_error("Negative program-binary input length is outside checked transfer scope");
    if(!length){native(program,format,nullptr,0);return;}
    auto bytes=Snapshot(input,static_cast<size_t>(length));
    native(program,format,bytes.data(),length);
  }
  void GetProgramBinary(GLuint program,GLsizei capacity,addr_t length,addr_t format,addr_t output,PFNGLGETPROGRAMBINARYPROC native){
    // ANGLE's serializer writes format first, binary bytes second, length last.
    // Insufficient capacity writes format and length=0 even while raising an error.
    std::vector<uint8_t> bytes;
    if(capacity>0&&output){
      if(static_cast<size_t>(capacity)>TransferLimit)throw std::runtime_error("Program-binary output exceeds64MiB scope");
      bytes.resize(static_cast<size_t>(capacity));
    }
    // Neither sentinel can be a result from the pinned ANGLE serializer:
    // its sole format is GL_PROGRAM_BINARY_ANGLE (0x93a6), lengths are nonnegative.
    GLenum native_format=GL_NONE;GLsizei written=-1;
    const bool okay=Call([&]{native(program,capacity,&written,&native_format,bytes.empty()?nullptr:bytes.data());});
    if(okay&&(native_format==GL_NONE||written<0))throw std::runtime_error("Invalid native program-binary outputs");
    if(written>0&&!bytes.empty()&&static_cast<size_t>(written)>bytes.size())throw std::runtime_error("Native program-binary length exceeds staging capacity");
    if(native_format!=GL_NONE&&format)Range(format,sizeof(GLenum));
    if(written>0&&!bytes.empty())Range(output,static_cast<size_t>(written));
    if(written>=0&&length)Range(length,sizeof(GLsizei));
    if(native_format!=GL_NONE&&format)recomp::WriteGuestMemory(format,&native_format,sizeof(native_format));
    if(written>0&&!bytes.empty())recomp::WriteGuestMemory(output,bytes.data(),static_cast<size_t>(written));
    if(written>=0&&length)recomp::WriteGuestMemory(length,&written,sizeof(written));
  }
  template<class Native>void FramebufferHint(GLenum target,GLsizei count,addr_t input,bool core,Native native){
    // Native target/count validation precedes all attachment-array reads.
    // Repeated attachments are valid; the API has no maximum list count.
    const bool valid_target=target==GL_FRAMEBUFFER||(core&&(target==GL_READ_FRAMEBUFFER||target==GL_DRAW_FRAMEBUFFER));
    if(!valid_target||count<=0){native(target,count,nullptr);return;}
    auto bytes=Snapshot(input,static_cast<size_t>(count)*sizeof(GLenum));
    std::vector<GLenum> attachments(static_cast<size_t>(count));
    std::memcpy(attachments.data(),bytes.data(),bytes.size());
    native(target,count,attachments.data());
  }
  void VertexBuffers(){
    const GLint count=Integer(GL_MAX_VERTEX_ATTRIBS);if(count<0||count>4096)throw std::runtime_error("GL vertex attribute count outside scope");
    for(GLint i=0;i<count;++i){GLint enabled=0,buffer=0;
      if(!Call([&]{getVertexAttrib(i,GL_VERTEX_ATTRIB_ARRAY_ENABLED,&enabled);}))throw std::runtime_error("Cannot inspect native vertex array");
      if(enabled){if(!Call([&]{getVertexAttrib(i,GL_VERTEX_ATTRIB_ARRAY_BUFFER_BINDING,&buffer);}))throw std::runtime_error("Cannot inspect vertex buffer ownership");
        if(!buffer)throw std::runtime_error("CPU client vertex arrays are outside typed GL scope");}
    }
  }
  void Pixels(GLint x,GLint y,GLsizei width,GLsizei height,GLenum format,GLenum type,addr_t output){
    if(format!=GL_RGBA||type!=GL_UNSIGNED_BYTE)throw std::runtime_error("Only typed RGBA/UNSIGNED_BYTE readback is implemented");
    if(Integer(GL_READ_FRAMEBUFFER_BINDING)||Integer(GL_PIXEL_PACK_BUFFER_BINDING))throw std::runtime_error("GL readback requires default read framebuffer and no PBO");
    auto surface=egl.CurrentReadPbufferExtent();if(!surface||surface->context!=current_context)throw std::runtime_error("GL readback requires a live owned read pbuffer");
    if(width<=0||height<=0){uint8_t byte=0;Call([&]{draw_glReadPixels(x,y,width,height,format,type,&byte);});return;}
    if(x<0||y<0||int64_t(x)+width>surface->width||int64_t(y)+height>surface->height)throw std::runtime_error("Clipped/out-of-bounds GL readback footprint is unsupported");
    const GLint alignment=Integer(GL_PACK_ALIGNMENT),row_length=Integer(GL_PACK_ROW_LENGTH),skip_rows=Integer(GL_PACK_SKIP_ROWS),skip_pixels=Integer(GL_PACK_SKIP_PIXELS);
    if((alignment!=1&&alignment!=2&&alignment!=4&&alignment!=8)||row_length<0||skip_rows<0||skip_pixels<0)throw std::runtime_error("Invalid native GL pack state");
    const uint64_t row_bytes=uint64_t(width)*4;
    const uint64_t stride=(uint64_t(row_length?row_length:width)*4+alignment-1)&~uint64_t(alignment-1);
    auto add=[](uint64_t a,uint64_t b){if(a>TransferLimit||b>TransferLimit-a)throw std::runtime_error("GL pixel pack footprint exceeds64MiB");return a+b;};
    auto rows=[&](uint64_t count){if(count&&stride>TransferLimit/count)throw std::runtime_error("GL pixel pack row span exceeds64MiB");return count*stride;};
    const uint64_t prefix=add(rows(skip_rows),uint64_t(skip_pixels)*4);
    const uint64_t span=add(add(prefix,rows(height-1)),row_bytes);
    Range(output,static_cast<size_t>(span));std::vector<uint8_t> pixels(span);
    if(!Call([&]{draw_glReadPixels(x,y,width,height,format,type,pixels.data());}))return;
    if(stride<=row_bytes)recomp::WriteGuestMemory(output+prefix,pixels.data()+prefix,size_t(span-prefix));
    else for(GLsizei row=0;row<height;++row){const auto offset=prefix+uint64_t(row)*stride;recomp::WriteGuestMemory(output+offset,pixels.data()+offset,size_t(row_bytes));}
  }
#include "gl_texture_impl.inc"
#include "gl_uniform_impl.inc"
#include "gl_framebuffer_impl.inc"
#include "gl_misc_impl.inc"
#include "gl_indexed_impl.inc"
#include "gl_internalformat_impl.inc"
#include "gl_sampler_impl.inc"
#include "gl_buffer_indexed_impl.inc"
#include "gl_label_impl.inc"
#include "gl_texture3d_impl.inc"
#include "gl_uniform_block_impl.inc"
#include "gl_program_resource_impl.inc"
#include "gl_mapping_impl.inc"
  void Bindings(){
    // Scalar commands delegate validation/error flags to the same current
    // ANGLE context. They neither drain errors nor expose driver pointers.
#define GL_SCALAR(name, native_type, signature) {using GuestSignature=signature;static_assert(std::is_same_v<native_type,GuestSignature*>);Bind<signature>(#name,Symbol<native_type>(module,#name));}
#include "gl_scalar_commands.inc"
#undef GL_SCALAR
    Bind<GLuint(GLenum)>("glCreateShader",draw_glCreateShader);
    Bind<void(GLuint,GLsizei,addr_t,addr_t)>("glShaderSource",[this](auto s,auto n,auto strings,auto lengths){ShaderSource(s,n,strings,lengths);});
    Bind<void(GLuint)>("glCompileShader",draw_glCompileShader);Bind<void(GLuint)>("glDeleteShader",draw_glDeleteShader);
    Bind<void(GLuint,GLenum,addr_t)>("glGetShaderiv",[this](auto s,auto p,auto out){ObjectQuery(s,p,out,false,draw_glGetShaderiv);});
    Bind<void(GLuint,GLsizei,addr_t,addr_t)>("glGetShaderInfoLog",[this](auto s,auto n,auto length,auto out){InfoLog(s,n,length,out,draw_glGetShaderInfoLog);});
    Bind<GLuint()>("glCreateProgram",draw_glCreateProgram);Bind<void(GLuint,GLuint)>("glAttachShader",draw_glAttachShader);Bind<void(GLuint,GLuint)>("glDetachShader",draw_glDetachShader);
    Bind<void(GLuint)>("glLinkProgram",draw_glLinkProgram);Bind<void(GLuint)>("glUseProgram",draw_glUseProgram);Bind<void(GLuint)>("glDeleteProgram",draw_glDeleteProgram);
    Bind<void(GLuint,GLenum,addr_t)>("glGetProgramiv",[this](auto s,auto p,auto out){ObjectQuery(s,p,out,true,draw_glGetProgramiv);});
    Bind<void(GLuint,GLsizei,addr_t,addr_t)>("glGetProgramInfoLog",[this](auto s,auto n,auto length,auto out){InfoLog(s,n,length,out,draw_glGetProgramInfoLog);});
    Bind<void(GLsizei,addr_t)>("glGenBuffers",[this](auto n,auto out){Generate(n,out,draw_glGenBuffers);});
    Bind<void(GLsizei,addr_t)>("glDeleteBuffers",[this](auto n,auto in){DeleteMappedBuffers(n,in);});
    Bind<void(GLenum,GLuint)>("glBindBuffer",draw_glBindBuffer);
    Bind<void(GLenum,int64_t,addr_t,GLenum)>("glBufferData",[this](auto t,auto n,auto in,auto u){Upload(t,n,in,u);});
    Bind<void(GLenum,int64_t,int64_t,addr_t)>("glBufferSubData",[this](auto t,auto o,auto n,auto in){SubUpload(t,o,n,in);});
    Bind<void(GLsizei,addr_t)>("glGenVertexArrays",[this](auto n,auto out){Generate(n,out,draw_glGenVertexArrays);});
    Bind<void(GLsizei,addr_t)>("glDeleteVertexArrays",[this](auto n,auto in){DeleteNames(n,in,draw_glDeleteVertexArrays);});
    Bind<void(GLuint)>("glBindVertexArray",draw_glBindVertexArray);Bind<void(GLuint)>("glEnableVertexAttribArray",draw_glEnableVertexAttribArray);Bind<void(GLuint)>("glDisableVertexAttribArray",draw_glDisableVertexAttribArray);
    Bind<void(GLuint,GLint,GLenum,GLboolean,GLsizei,addr_t)>("glVertexAttribPointer",[this](auto i,auto n,auto t,auto normal,auto stride,auto offset){
      if(!Integer(GL_ARRAY_BUFFER_BINDING))throw std::runtime_error("VertexAttribPointer requires a GPU VBO; CPU client pointers unsupported");
      draw_glVertexAttribPointer(i,n,t,normal,stride,reinterpret_cast<const void*>(offset));});
    Bind<void(GLenum,GLint,GLsizei)>("glDrawArrays",[this](auto mode,auto first,auto count){VertexBuffers();draw_glDrawArrays(mode,first,count);});
    Bind<void(GLenum,GLsizei,GLenum,addr_t)>("glDrawElements",[this](auto mode,auto count,auto type,auto offset){VertexBuffers();
      if(!Integer(GL_ELEMENT_ARRAY_BUFFER_BINDING))throw std::runtime_error("DrawElements requires a GPU EBO; CPU index pointers unsupported");
      draw_glDrawElements(mode,count,type,reinterpret_cast<const void*>(offset));});
    Bind<void(GLint,GLint,GLsizei,GLsizei,GLenum,GLenum,addr_t)>("glReadPixels",[this](auto x,auto y,auto w,auto h,auto f,auto t,auto out){Pixels(x,y,w,h,f,t,out);});
    Bind<void(GLenum,GLint)>("glPixelStorei",draw_glPixelStorei);
    Bind<addr_t(uint32_t)>("glGetString",[this](GLenum name){CollectErrors();const auto native=getString(name);CollectErrors();return String(native);});
    Bind<addr_t(uint32_t,uint32_t)>("glGetStringi",[this](GLenum name,GLuint index){CollectErrors();const auto native=getStringi(name,index);CollectErrors();return String(native);});
    Bind<void(uint32_t,addr_t)>("glGetIntegerv",[this](GLenum name,addr_t out){QueryValues<GLint>(name,out,getInteger);});
    Bind<void(uint32_t,addr_t)>("glGetFloatv",[this](GLenum name,addr_t out){QueryValues<GLfloat>(name,out,getFloat);});
    Bind<void(uint32_t,addr_t)>("glGetBooleanv",[this](GLenum name,addr_t out){QueryValues<GLboolean>(name,out,getBoolean);});
    Bind<uint32_t()>("glGetError",[this]{CollectErrors();auto at=pending_errors.find(current_context);if(at==pending_errors.end())return GLenum(GL_NO_ERROR);
      const GLenum value=*at->second.begin();at->second.erase(at->second.begin());if(at->second.empty())pending_errors.erase(at);return value;});
    BindTextureCommands();
    BindUniformCommands();
    BindFramebufferCommands();
    BindMiscCommands();
    BindIndexedCommands();
    BindInternalFormatCommands();
    BindSamplerCommands();
    BindIndexedBufferCommands();
#define GL_OBJECT_COMMAND(name,native_type,signature) {using GuestSignature=signature;static_assert(std::is_same_v<native_type,GuestSignature*>);Bind<signature>(#name,Symbol<native_type>(module,#name));}
#include "gl_object_commands.inc"
#undef GL_OBJECT_COMMAND
#define GL_STORAGE_COMMAND(name,native_type,signature) {using GuestSignature=signature;static_assert(std::is_same_v<native_type,GuestSignature*>);Bind<signature>(#name,Symbol<native_type>(module,#name));}
#include "gl_storage_commands.inc"
#undef GL_STORAGE_COMMAND
    BindLabelCommands();
    BindTexture3DCommands();
    BindUniformBlockCommands();
    BindProgramResourceCommands();
    BindMappingCommands();
    Bind<void(GLsizei,addr_t)>("glDrawBuffers",[this](GLsizei n,addr_t input){DrawBuffers(n,input);});
    static_assert(sizeof(GLsync)==sizeof(addr_t)&&sizeof(GLuint64)==8);
    const auto fenceSync=Symbol<PFNGLFENCESYNCPROC>(module,"glFenceSync");
    Bind<addr_t(GLenum,GLbitfield)>("glFenceSync",[fenceSync](GLenum condition,GLbitfield flags){return reinterpret_cast<addr_t>(fenceSync(condition,flags));});
    const auto clientWaitSync=Symbol<PFNGLCLIENTWAITSYNCPROC>(module,"glClientWaitSync");
    Bind<GLenum(addr_t,GLbitfield,GLuint64)>("glClientWaitSync",[clientWaitSync](addr_t sync,GLbitfield flags,GLuint64 timeout){return clientWaitSync(reinterpret_cast<GLsync>(sync),flags,timeout);});
    const auto deleteSync=Symbol<PFNGLDELETESYNCPROC>(module,"glDeleteSync");
    Bind<void(addr_t)>("glDeleteSync",[deleteSync](addr_t sync){deleteSync(reinterpret_cast<GLsync>(sync));});
    Bind<void(GLuint,GLenum,GLint)>("glProgramParameteri",Symbol<PFNGLPROGRAMPARAMETERIPROC>(module,"glProgramParameteri"));
    const auto getBinary=Symbol<PFNGLGETPROGRAMBINARYPROC>(module,"glGetProgramBinary");
    Bind<void(GLuint,GLsizei,addr_t,addr_t,addr_t)>("glGetProgramBinary",[this,getBinary](GLuint p,GLsizei n,addr_t length,addr_t format,addr_t output){GetProgramBinary(p,n,length,format,output,getBinary);});
    const auto setBinary=Symbol<PFNGLPROGRAMBINARYPROC>(module,"glProgramBinary");
    Bind<void(GLuint,GLenum,addr_t,GLsizei)>("glProgramBinary",[this,setBinary](GLuint p,GLenum format,addr_t input,GLsizei n){ProgramBinary(p,format,input,n,setBinary);});
    const auto invalidate=Symbol<PFNGLINVALIDATEFRAMEBUFFERPROC>(module,"glInvalidateFramebuffer");
    Bind<void(GLenum,GLsizei,addr_t)>("glInvalidateFramebuffer",[this,invalidate](GLenum target,GLsizei n,addr_t input){FramebufferHint(target,n,input,true,invalidate);});
    const auto discard=Symbol<PFNGLDISCARDFRAMEBUFFEREXTPROC>(module,"glDiscardFramebufferEXT");
    Bind<void(GLenum,GLsizei,addr_t)>("glDiscardFramebufferEXT",[this,discard](GLenum target,GLsizei n,addr_t input){FramebufferHint(target,n,input,false,discard);});
  }
};
GlHost::GlHost(EglHost &egl,const std::wstring &directory,addr_t marker):impl_(std::make_unique<Impl>(egl,directory,marker)){}
GlHost::~GlHost()=default;
const std::vector<GlHost::Query> &GlHost::Queries(){return queries;}
const std::vector<std::string> &GlHost::Commands(){static const std::vector<std::string> commands(std::begin(names),std::end(names));return commands;}
size_t GlHost::QueryComponents(uint32_t name){std::lock_guard lock(impl_->mutex);auto dpi=impl_->egl.CurrentWindowDpiScope();impl_->SelectContext();auto count=impl_->Components(name);if(!count)throw std::runtime_error("Native GL query-size error");return *count;}
addr_t GlHost::Marker(const std::string &name)const{for(size_t i=0;i<std::size(names);++i)if(name==names[i])return impl_->marker+i*8;throw std::runtime_error("Unsupported typed GL resolver signature: "+name);}
void GlHost::Invoke(const std::string &name,State &state){GlNativeEnvironment environment;std::unique_lock lock(impl_->mutex);auto dpi=impl_->egl.CurrentWindowDpiScope();auto found=impl_->bridges.find(name);if(found==impl_->bridges.end())throw std::invalid_argument("Unsupported GL import: "+name);impl_->SelectContext();
  if(!impl_->diagnostic_png.empty()){++impl_->diagnostic.calls;if(impl_->diagnostic.calls<=24||impl_->diagnostic.calls%1000==0)std::fprintf(stderr,"First frame: GL call=%llu %s context=%#llx\n",(unsigned long long)impl_->diagnostic.calls,name.c_str(),(unsigned long long)impl_->current_context);}
  // A native client wait may block; its immutable bridge uses only the current
  // thread's native context. Leave other contexts free to make progress.
  // Native ANGLE retains its own share-group synchronization and object lifetime.
  if(name=="glClientWaitSync"){auto call=found->second;lock.unlock();call(state);return;}
  found->second(state);
  if(!impl_->diagnostic_png.empty()){if(name=="glDrawArrays"||name=="glDrawElements")++impl_->diagnostic.draw_submissions;if(name=="glClear")++impl_->diagnostic.clear_submissions;}}
void GlHost::EnableFrameDiagnostics(const std::wstring &path){std::lock_guard lock(impl_->mutex);if(path.empty()||!std::filesystem::path(path).is_absolute())throw std::invalid_argument("Absolute frame PNG path required");impl_->diagnostic_png=path;}
GlHost::FrameDiagnostics GlHost::DescribeFrameDiagnostics(){std::lock_guard lock(impl_->mutex);return impl_->diagnostic;}
uint64_t GlHost::BeginWindowPresent(addr_t display,addr_t surface){std::lock_guard lock(impl_->mutex);
  const int saved_errno=errno;const DWORD saved_error=GetLastError();std::fenv_t environment;std::feholdexcept(&environment);
  struct Restore{int error;DWORD native_error;std::fenv_t environment;~Restore(){std::fesetenv(&environment);errno=error;SetLastError(native_error);}} restore{saved_errno,saved_error,environment};
  auto dpi=impl_->egl.CurrentWindowDpiScope();
  try{return impl_->CaptureWindow(display,surface);}catch(const std::exception &e){impl_->diagnostic.failure=e.what();std::fprintf(stderr,"First frame: capture failed: %s\n",e.what());return 0;}}
void GlHost::FinishWindowPresent(uint64_t ticket,addr_t display,addr_t surface,uint32_t actual_result){std::lock_guard lock(impl_->mutex);
  const int saved_errno=errno;const DWORD saved_error=GetLastError();std::fenv_t environment;std::feholdexcept(&environment);
  struct Restore{int error;DWORD native_error;std::fenv_t environment;~Restore(){std::fesetenv(&environment);errno=error;SetLastError(native_error);}} restore{saved_errno,saved_error,environment};
  auto dpi=impl_->egl.CurrentWindowDpiScope();
  try{impl_->FinishPresent(ticket,display,surface,actual_result);}catch(const std::exception &e){impl_->diagnostic.failure=e.what();std::fprintf(stderr,"First frame: capture completion failed: %s\n",e.what());}}

void GlHost::Install(recomp::Runtime &runtime){if(impl_->installed)throw std::logic_error("GL imports already installed");for(const auto *name:names)runtime.AddImport(Marker(name),[this,name](State &state){try{Invoke(name,state);}catch(const std::exception &e){std::fprintf(stderr,"GL %s: %s\n",name,e.what());std::abort();}});impl_->installed=true;}
}  // namespace bunker::windows
#undef GL_DRAW_API

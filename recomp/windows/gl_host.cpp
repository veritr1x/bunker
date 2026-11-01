#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define GL_GLES_PROTOTYPES 0
#include <GLES3/gl32.h>
#include "gl_host.h"
#include "../whole/bridge.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>

namespace bunker::windows {
namespace {
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
};
const char *const names[]={"glGetString","glGetStringi","glGetIntegerv","glGetFloatv","glGetBooleanv","glGetError",
#define GL_SCALAR(name, native_type, signature) #name,
#include "gl_scalar_commands.inc"
#undef GL_SCALAR
};
std::atomic<uint64_t> next_owner{1};
thread_local std::map<uint64_t,std::set<GLenum>> pending_errors;
std::string Hex(GLenum value){std::ostringstream out;out<<"0x"<<std::hex<<value;return out.str();}
template<class T>T Symbol(HMODULE module,const char *name){
  const auto native=GetProcAddress(module,name);if(!native)throw std::runtime_error(std::string("Missing ANGLE GL symbol: ")+name);
  T typed;static_assert(sizeof(typed)==sizeof(native));std::memcpy(&typed,&native,sizeof(typed));return typed;
}
}
struct GlHost::Impl {
  const uint64_t owner=next_owner++;
  HMODULE module=nullptr;addr_t marker;bool installed=false;
  std::mutex mutex;
  PFNGLGETSTRINGPROC getString=nullptr;PFNGLGETSTRINGIPROC getStringi=nullptr;
  PFNGLGETINTEGERVPROC getInteger=nullptr;PFNGLGETFLOATVPROC getFloat=nullptr;
  PFNGLGETBOOLEANVPROC getBoolean=nullptr;PFNGLGETERRORPROC getError=nullptr;
  std::map<std::string,std::unique_ptr<char[]>> strings;
  std::map<std::string,std::function<void(State&)>> bridges;
  Impl(const std::wstring &directory,addr_t marker):marker(marker){
    static_assert(sizeof(GLboolean)==1&&sizeof(GLint)==4&&sizeof(GLfloat)==4);
    if((marker&7)||marker>UINT64_MAX-std::size(names)*8)throw std::invalid_argument("GL marker range/alignment");
    if(directory.size()<3||directory[1]!=L':'||!(directory[2]==L'\\'||directory[2]==L'/'))throw std::invalid_argument("ANGLE GL DLL directory must be absolute");
    module=LoadLibraryExW((directory+L"\\libGLESv2.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!module)throw std::runtime_error("Cannot load pinned ANGLE GLES DLL");
    try{
      getString=Symbol<PFNGLGETSTRINGPROC>(module,"glGetString");getStringi=Symbol<PFNGLGETSTRINGIPROC>(module,"glGetStringi");
      getInteger=Symbol<PFNGLGETINTEGERVPROC>(module,"glGetIntegerv");getFloat=Symbol<PFNGLGETFLOATVPROC>(module,"glGetFloatv");
      getBoolean=Symbol<PFNGLGETBOOLEANVPROC>(module,"glGetBooleanv");getError=Symbol<PFNGLGETERRORPROC>(module,"glGetError");
      Bindings();
    }catch(...){FreeLibrary(module);throw;}
  }
  ~Impl(){for(const auto &[text,value]:strings)recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(value.get()),text.size()+1);FreeLibrary(module);pending_errors.erase(owner);}
  bool CollectErrors(){
    bool any=false;for(unsigned n=0;n<32;++n){GLenum value=getError();if(value==GL_NO_ERROR)return any;
      pending_errors[owner].insert(value);any=true;}
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
  void Bindings(){
    // Scalar commands delegate validation/error flags to the same current
    // ANGLE context. They neither drain errors nor expose driver pointers.
#define GL_SCALAR(name, native_type, signature) {using GuestSignature=signature;static_assert(std::is_same_v<native_type,GuestSignature*>);Bind<signature>(#name,Symbol<native_type>(module,#name));}
#include "gl_scalar_commands.inc"
#undef GL_SCALAR
    Bind<addr_t(uint32_t)>("glGetString",[this](GLenum name){CollectErrors();const auto native=getString(name);CollectErrors();return String(native);});
    Bind<addr_t(uint32_t,uint32_t)>("glGetStringi",[this](GLenum name,GLuint index){CollectErrors();const auto native=getStringi(name,index);CollectErrors();return String(native);});
    Bind<void(uint32_t,addr_t)>("glGetIntegerv",[this](GLenum name,addr_t out){QueryValues<GLint>(name,out,getInteger);});
    Bind<void(uint32_t,addr_t)>("glGetFloatv",[this](GLenum name,addr_t out){QueryValues<GLfloat>(name,out,getFloat);});
    Bind<void(uint32_t,addr_t)>("glGetBooleanv",[this](GLenum name,addr_t out){QueryValues<GLboolean>(name,out,getBoolean);});
    Bind<uint32_t()>("glGetError",[this]{CollectErrors();auto &errors=pending_errors[owner];if(errors.empty())return GLenum(GL_NO_ERROR);
      const GLenum value=*errors.begin();errors.erase(errors.begin());return value;});
  }
};
GlHost::GlHost(const std::wstring &directory,addr_t marker):impl_(std::make_unique<Impl>(directory,marker)){}
GlHost::~GlHost()=default;
const std::vector<GlHost::Query> &GlHost::Queries(){return queries;}
size_t GlHost::QueryComponents(uint32_t name){std::lock_guard lock(impl_->mutex);auto count=impl_->Components(name);if(!count)throw std::runtime_error("Native GL query-size error");return *count;}
addr_t GlHost::Marker(const std::string &name)const{for(size_t i=0;i<std::size(names);++i)if(name==names[i])return impl_->marker+i*8;throw std::runtime_error("Unsupported typed GL resolver signature: "+name);}
void GlHost::Invoke(const std::string &name,State &state){std::lock_guard lock(impl_->mutex);auto found=impl_->bridges.find(name);if(found==impl_->bridges.end())throw std::invalid_argument("Unsupported GL import: "+name);found->second(state);}
void GlHost::Install(recomp::Runtime &runtime){if(impl_->installed)throw std::logic_error("GL imports already installed");for(const auto *name:names)runtime.AddImport(Marker(name),[this,name](State &state){try{Invoke(name,state);}catch(const std::exception &e){std::fprintf(stderr,"GL %s: %s\n",name,e.what());std::abort();}});impl_->installed=true;}
}  // namespace bunker::windows

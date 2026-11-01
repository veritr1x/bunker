#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "egl_host.h"
#include "../whole/bridge.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <map>
#include <mutex>
#include <sstream>
#include <set>
#include <stdexcept>
#include <thread>
#include <vector>

namespace bunker::windows {
namespace {
using I=int32_t;using U=uint32_t;using E=void*;
constexpr I Success=0x3000,BadAccess=0x3002,BadAttribute=0x3004,BadConfig=0x3005,
  BadContext=0x3006,BadDisplay=0x3008,BadMatch=0x3009,BadWindow=0x300b,
  BadParameter=0x300c,BadSurface=0x300d,None=0x3038;
const char *const names[]={"eglQuerySurface","eglChooseConfig","eglSwapBuffers",
  "eglGetCurrentContext","eglTerminate","eglCreateWindowSurface","eglQueryString",
  "eglCreateContext","eglGetDisplay","eglGetProcAddress","eglMakeCurrent",
  "eglGetConfigAttrib","eglDestroyContext","eglGetError","eglSwapInterval",
  "eglCreatePbufferSurface","eglDestroySurface","eglGetCurrentSurface","eglInitialize"};
std::atomic<addr_t> next_handle{0x7ff430000000ULL};
std::atomic<uint64_t> next_owner{1};
thread_local std::map<uint64_t,I> errors;
addr_t Token(){auto token=next_handle.load();do{
  if(token>UINT64_MAX-8)throw std::overflow_error("EGL token exhausted");
}while(!next_handle.compare_exchange_weak(token,token+8));return token;}
template<class T>T Read(addr_t p){T value;recomp::ReadGuestMemory(&value,p,sizeof(value));return value;}
template<class T>void Write(addr_t p,const T &v){recomp::WriteGuestMemory(p,&v,sizeof(v));}
std::vector<I> Attributes(addr_t address){
  std::vector<I> result;if(!address)return result;
  for(unsigned i=0;i<128;++i){const I key=Read<I>(address);result.push_back(key);address+=4;
    if(key==None)return result;
    result.push_back(Read<I>(address));address+=4;}
  throw std::invalid_argument("EGL attribute list exceeds bounded128 pairs");
}
std::string CString(addr_t p){
  if(!p)throw std::invalid_argument("null EGL procedure name");
  std::string text;
  for(unsigned i=0;i<256;++i){const char c=Read<char>(p+i);if(!c)return text;text+=c;}
  throw std::invalid_argument("EGL procedure name exceeds255 bytes");
}
template<class T>T Symbol(HMODULE module,const char *name){
  auto raw=GetProcAddress(module,name);if(!raw)throw std::runtime_error(std::string("ANGLE missing native symbol ")+name);
  T typed;static_assert(sizeof(typed)==sizeof(raw));std::memcpy(&typed,&raw,sizeof(raw));return typed;
}
#define EGL_API(X) \
 X(U,eglQuerySurface,(E,E,I,I*)) \
 X(U,eglChooseConfig,(E,const I*,E*,I,I*)) \
 X(U,eglSwapBuffers,(E,E)) \
 X(E,eglGetCurrentContext,()) \
 X(U,eglTerminate,(E)) \
 X(E,eglCreateWindowSurface,(E,E,HWND,const I*)) \
 X(const char*,eglQueryString,(E,I)) \
 X(E,eglCreateContext,(E,E,E,const I*)) \
 X(U,eglMakeCurrent,(E,E,E,E)) \
 X(U,eglGetConfigAttrib,(E,E,I,I*)) \
 X(U,eglDestroyContext,(E,E)) \
 X(I,eglGetError,()) \
 X(U,eglSwapInterval,(E,I)) \
 X(E,eglCreatePbufferSurface,(E,E,const I*)) \
 X(U,eglDestroySurface,(E,E)) \
 X(E,eglGetCurrentSurface,(I)) \
 X(U,eglInitialize,(E,I*,I*)) \
 X(U,eglBindAPI,(U)) \
 X(U,eglReleaseThread,())
}
struct EglHost::Impl {
  NativeWindows &windows;const uint64_t owner=next_owner++;
  addr_t marker;HMODULE egl=nullptr,gles=nullptr;bool installed=false;
  // No guest callbacks or guest-memory lock span native EGL operations.
  std::mutex mutex;
  enum Kind{Display,Config,Context,Surface};
  struct Object {Kind kind;E native;addr_t display=0,window=0;bool deleted=false,native_destroyed=false;I format=0;};
  struct Current {addr_t context=0,draw=0,read=0;};
  struct GeometryLife {std::mutex mutex;Impl *owner=nullptr;};
  std::shared_ptr<GeometryLife> geometry_life=std::make_shared<GeometryLife>();
  std::map<addr_t,std::set<I>> display_window_formats;
  std::map<addr_t,I> approved_formats;
  std::map<addr_t,Object> objects;
  std::map<std::thread::id,Current> currents;
  std::map<std::string,std::unique_ptr<char[]>> strings;
  std::map<std::string,std::function<void(State&)>> bridges;
  std::function<addr_t(const std::string&)> procedure_resolver;
#define DECL(ret,name,args) using name##T=ret(WINAPI*)args;name##T name=nullptr;
  EGL_API(DECL)
#undef DECL
  using GetProc=void*(WINAPI*)(const char*);GetProc getProc=nullptr;
  using GetPlatform=E(WINAPI*)(U,E,const I*);GetPlatform getPlatform=nullptr;
  Impl(NativeWindows &windows,const std::wstring &directory,addr_t marker):windows(windows),marker(marker){
    if((marker&7)||marker>UINT64_MAX-std::size(names)*8)throw std::invalid_argument("EGL marker range/alignment");
    if(directory.size()<3||directory[1]!=L':'||!(directory[2]==L'\\'||directory[2]==L'/'))throw std::invalid_argument("ANGLE DLL directory must be absolute");
    try{
      egl=LoadLibraryExW((directory+L"\\libEGL.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
      if(!egl)throw std::runtime_error("Cannot load pinned ANGLE libEGL.dll");
      gles=LoadLibraryExW((directory+L"\\libGLESv2.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
      if(!gles)throw std::runtime_error("Cannot load pinned ANGLE libGLESv2.dll");
#define LOAD(ret,name,args) name=Symbol<name##T>(egl,#name);
      EGL_API(LOAD)
#undef LOAD
      getProc=Symbol<GetProc>(egl,"eglGetProcAddress");
      auto address=getProc("eglGetPlatformDisplayEXT");std::memcpy(&getPlatform,&address,sizeof(address));
      if(!getPlatform)throw std::runtime_error("ANGLE Vulkan platform entry missing");
      Bindings();
      geometry_life->owner=this;
      windows.SetGeometryBackend([life=geometry_life](addr_t token,const NativeWindows::Geometry &geometry){
        std::lock_guard lease(life->mutex);if(!life->owner)return -19;
        std::lock_guard lock(life->owner->mutex);return life->owner->ApplyFormat(token,geometry);
      });
    }catch(...){if(gles)FreeLibrary(gles);if(egl)FreeLibrary(egl);throw;}
  }
  ~Impl(){
    windows.SetGeometryBackend({});
    {std::lock_guard lease(geometry_life->mutex);geometry_life->owner=nullptr;}
    ReleaseThread();
    if(!currents.empty()){std::fputs("EGL owner destroyed before worker current contexts retired\n",stderr);std::abort();}
    for(auto &[token,o]:objects){(void)token;if(o.deleted)continue;
      if(o.kind==Surface)eglDestroySurface(Native(o.display,Display),o.native);
      else if(o.kind==Context)eglDestroyContext(Native(o.display,Display),o.native);}
    for(auto &[token,o]:objects){(void)token;if(o.kind==Display)eglTerminate(o.native);if(o.window)windows.Release(o.window);}
    for(const auto &[key,value]:strings)recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(value.get()),key.size()+1);
    if(gles)FreeLibrary(gles);
    if(egl)FreeLibrary(egl);
    errors.erase(owner);
  }
  void Error(I error){if(error!=Success)errors[owner]=error;}
  void Capture(){Error(eglGetError());}
  E Native(addr_t token,Kind kind,addr_t display=0,bool allow_deleted=false){
    auto it=objects.find(token);
    if(it==objects.end()||it->second.kind!=kind||(!allow_deleted&&it->second.deleted)||(display&&it->second.display!=display)){
      Error(kind==Display?BadDisplay:kind==Config?BadConfig:kind==Context?BadContext:BadSurface);return nullptr;}
    return it->second.native;
  }
  addr_t Add(Kind kind,E native,addr_t display=0,addr_t window=0,I format=0){
    for(const auto &[token,o]:objects)if(!o.deleted&&o.kind==kind&&o.native==native&&o.display==display)return token;
    const auto token=Token();objects.emplace(token,Object{kind,native,display,window,false,false,format});return token;
  }
  addr_t Find(E native,Kind kind){if(!native)return 0;for(const auto &[token,o]:objects)if(o.kind==kind&&o.native==native)return token;
    throw std::runtime_error("Native current EGL object is outside provider ownership");}
  bool Held(addr_t token)const{
    for(const auto &[thread,c]:currents){(void)thread;if(c.context==token||c.draw==token||c.read==token)return true;}
    return false;
  }
  void DestroyNative(Object &object){
    if(object.native_destroyed)return;
    E display=Native(object.display,Display);
    U ok=object.kind==Surface?eglDestroySurface(display,object.native):object.kind==Context?eglDestroyContext(display,object.native):1;
    Capture();if(!ok)throw std::runtime_error("Deferred native EGL object retirement failed");
    object.native_destroyed=true;
  }
  void Prune(){
    for(auto it=objects.begin();it!=objects.end();){
      if(it->second.deleted&&!Held(it->first)){
        DestroyNative(it->second);
        if(it->second.window)windows.Release(it->second.window);
        it=objects.erase(it);
      }else ++it;
    }
  }
  void *DpiWindow(const std::string &name,const State *state=nullptr){
    addr_t window=0,surface=0;
    if(state&&name=="eglCreateWindowSurface")window=state->gpr.x2.qword;
    else if(state&&(name=="eglQuerySurface"||name=="eglSwapBuffers"||name=="eglDestroySurface"))surface=state->gpr.x1.qword;
    else if(state&&name=="eglMakeCurrent")surface=state->gpr.x1.qword;
    if(!window&&surface){auto it=objects.find(surface);if(it!=objects.end()&&it->second.kind==Surface)window=it->second.window;}
    if(!window){auto current=currents.find(std::this_thread::get_id());if(current!=currents.end()){
      auto it=objects.find(current->second.draw);if(it!=objects.end())window=it->second.window;}}
    if(!window)return nullptr;
    try{return windows.NativeHandle(window);}catch(const std::invalid_argument&){return nullptr;}
  }
  void ReleaseThread(){
    if(!eglReleaseThread)return;
    std::unique_ptr<WindowDpiScope> dpi;if(auto window=DpiWindow(""))dpi=std::make_unique<WindowDpiScope>(window);
    eglReleaseThread();Capture();currents.erase(std::this_thread::get_id());Prune();
  }
  addr_t String(const std::string &value){auto found=strings.find(value);if(found!=strings.end())return reinterpret_cast<addr_t>(found->second.get());
    auto copy=std::make_unique<char[]>(value.size()+1);const auto address=reinterpret_cast<addr_t>(copy.get());
    recomp::WriteGuestMemory(address,value.c_str(),value.size()+1);strings.emplace(value,std::move(copy));return address;}
  I Visual(E display,E config){I r=0,g=0,b=0,a=0;
    for(auto pair:{std::pair<I,I*>{0x3024,&r},{0x3023,&g},{0x3022,&b},{0x3021,&a}})if(!eglGetConfigAttrib(display,config,pair.first,pair.second)){Capture();return 0;}
    // Android logical buffer format; Windows nativeVisualID is always zero.
    if(r==8&&g==8&&b==8)return a==8?1:a==0?2:0;
    if(r==5&&g==6&&b==5&&a==0)return 4;
    if(r==10&&g==10&&b==10&&a==2)return 43;
    if(r==16&&g==16&&b==16&&a==16)return 22;
    Error(BadMatch);return 0;
  }
  std::set<I> WindowFormats(E display){
    // Internal capability queries must not change the guest EGL error flag.
    Capture();const I saved=errors[owner];
    struct Restore {Impl &host;I saved;~Restore(){host.eglGetError();errors[host.owner]=saved;}} restore{*this,saved};
    const I attrs[]={0x3033,4,None};I count=0;
    if(!eglChooseConfig(display,attrs,nullptr,0,&count)||count<0||count>4096)return {};
    std::vector<E> configs(count);
    if(count&&!eglChooseConfig(display,attrs,configs.data(),count,&count))return {};
    std::set<I> supported;
    for(I i=0;i<count;++i){const I format=Visual(display,configs[i]);
      // RGB565 remains unsupported unless a real presentable config and draw
      // gate demonstrate it. This backend enables only validated RGBA/RGBX.
      if(format==1||format==2)supported.insert(format);
    }
    return supported;
  }
  int ApplyFormat(addr_t window,const NativeWindows::Geometry &geometry){
    if(geometry.fixed_size||geometry.width!=geometry.client_width||geometry.height!=geometry.client_height)return -38;
    if(geometry.format!=1&&geometry.format!=2)return -38;
    bool supported=false;for(const auto &[display,formats]:display_window_formats){(void)display;supported|=formats.count(geometry.format)!=0;}
    if(!supported)return -38;
    for(const auto &[token,object]:objects){
      if(object.kind==Surface&&object.window==window&&(!object.native_destroyed||Held(token))&&object.format!=geometry.format)return -16;
    }
    // Record before NativeWindows commits its descriptor. A concurrent create
    // must match both this approval and the published descriptor, so it fails
    // conservatively during the callback-to-commit interval.
    approved_formats[window]=geometry.format;
    return 0;
  }
  template<class S,class F>void Bind(const char *name,F function){bridges.emplace(name,recomp::MakeBridge<S>(std::move(function)));}
  void Bindings(){
    Bind<addr_t(addr_t)>("eglGetDisplay",[this](addr_t native){
      if(native){Error(BadParameter);return addr_t(0);}const I attrs[]={0x3203,0x3450,0x3209,0x320a,None};
      E display=getPlatform(0x3202,nullptr,attrs);Capture();return display?Add(Display,display):0;});
    Bind<U(addr_t,addr_t,addr_t)>("eglInitialize",[this](addr_t d,addr_t major,addr_t minor){
      E display=Native(d,Display);if(!display)return U(0);I a=0,b=0;U ok=eglInitialize(display,major?&a:nullptr,minor?&b:nullptr);Capture();
      if(ok){display_window_formats[d]=WindowFormats(display);if(major)Write(major,a);if(minor)Write(minor,b);}return ok;});
    Bind<U(addr_t,addr_t,addr_t,I,addr_t)>("eglChooseConfig",[this](addr_t d,addr_t attrs,addr_t configs,I size,addr_t count){
      E display=Native(d,Display);if(!display)return U(0);if(!count||size<0||size>4096){Error(BadParameter);return U(0);}
      auto list=Attributes(attrs);I wanted=-1;for(size_t i=0;i+1<list.size();i+=2)if(list[i]==0x302e){wanted=list[i+1];list.erase(list.begin()+i,list.begin()+i+2);break;}
      I total=0;if(!eglChooseConfig(display,list.empty()?nullptr:list.data(),nullptr,0,&total)){Capture();return U(0);}Capture();
      if(total<0||total>4096)throw std::runtime_error("ANGLE config count exceeds4096");
      std::vector<E> native(total);
      if(total&&!eglChooseConfig(display,list.empty()?nullptr:list.data(),native.data(),total,&total)){Capture();return U(0);}Capture();native.resize(total);
      if(wanted!=-1)native.erase(std::remove_if(native.begin(),native.end(),[&](E c){return Visual(display,c)!=wanted;}),native.end());
      I n=configs?std::min<I>(size,I(native.size())):I(native.size());
      if(configs){std::vector<addr_t> tokens;for(I i=0;i<n;++i)tokens.push_back(Add(Config,native[i],d));if(n)recomp::WriteGuestMemory(configs,tokens.data(),tokens.size()*sizeof(addr_t));}
      Write(count,n);return U(1);});
    Bind<U(addr_t,addr_t,I,addr_t)>("eglGetConfigAttrib",[this](addr_t d,addr_t c,I attr,addr_t out){
      E display=Native(d,Display),config=Native(c,Config,d);if(!display||!config)return U(0);if(!out){Error(BadParameter);return U(0);}
      I value=0;U ok=1;if(attr==0x302e){value=Visual(display,config);ok=value!=0;}else{ok=eglGetConfigAttrib(display,config,attr,&value);Capture();}
      if(ok)Write(out,value);
      return ok;});
    Bind<addr_t(addr_t,addr_t,addr_t,addr_t)>("eglCreateContext",[this](addr_t d,addr_t c,addr_t share,addr_t attrs){
      E display=Native(d,Display),config=Native(c,Config,d),shared=share?Native(share,Context,d):nullptr;if(!display||!config||(share&&!shared))return addr_t(0);
      auto list=Attributes(attrs);if(!eglBindAPI(0x30a0)){Capture();return addr_t(0);}E context=eglCreateContext(display,config,shared,list.empty()?nullptr:list.data());Capture();return context?Add(Context,context,d):0;});
    Bind<addr_t(addr_t,addr_t,addr_t)>("eglCreatePbufferSurface",[this](addr_t d,addr_t c,addr_t attrs){
      E display=Native(d,Display),config=Native(c,Config,d);if(!display||!config)return addr_t(0);auto list=Attributes(attrs);
      E surface=eglCreatePbufferSurface(display,config,list.empty()?nullptr:list.data());Capture();return surface?Add(Surface,surface,d):0;});
    Bind<addr_t(addr_t,addr_t,addr_t,addr_t)>("eglCreateWindowSurface",[this](addr_t d,addr_t c,addr_t window,addr_t attrs){
      E display=Native(d,Display),config=Native(c,Config,d);if(!display||!config)return addr_t(0);auto list=Attributes(attrs);
      try{auto geometry=windows.Describe(window);auto hwnd=static_cast<HWND>(windows.NativeHandle(window));
        if(!hwnd){Error(BadWindow);return addr_t(0);}if(geometry.fixed_size){Error(BadMatch);return addr_t(0);}
        const I format=Visual(display,config);auto approved=approved_formats.find(window);
        if(geometry.format!=format||(approved!=approved_formats.end()&&approved->second!=geometry.format)){Error(BadMatch);return addr_t(0);}
        windows.Acquire(window);E surface=eglCreateWindowSurface(display,config,hwnd,list.empty()?nullptr:list.data());Capture();
        if(!surface){windows.Release(window);return addr_t(0);}return Add(Surface,surface,d,window,format);
      }catch(const std::invalid_argument&){Error(BadWindow);return addr_t(0);}});
    Bind<U(addr_t,addr_t,addr_t,addr_t)>("eglMakeCurrent",[this](addr_t d,addr_t draw,addr_t read,addr_t ctx){
      E display=Native(d,Display),context=ctx?Native(ctx,Context,d):nullptr,ds=draw?Native(draw,Surface,d):nullptr,rs=read?Native(read,Surface,d):nullptr;
      if(!display||(ctx&&!context)||(draw&&!ds)||(read&&!rs))return U(0);
      U ok=eglMakeCurrent(display,ds,rs,context);Capture();
      if(ok){if(ctx)currents[std::this_thread::get_id()]={ctx,draw,read};else currents.erase(std::this_thread::get_id());Prune();}return ok;});
    Bind<addr_t()>("eglGetCurrentContext",[this]{return Find(eglGetCurrentContext(),Context);});
    Bind<addr_t(I)>("eglGetCurrentSurface",[this](I which){E surface=eglGetCurrentSurface(which);Capture();return Find(surface,Surface);});
    Bind<U(addr_t,addr_t,I,addr_t)>("eglQuerySurface",[this](addr_t d,addr_t s,I attr,addr_t out){
      E display=Native(d,Display),surface=Native(s,Surface,d);if(!display||!surface)return U(0);if(!out){Error(BadParameter);return U(0);}
      I value=0;U ok=eglQuerySurface(display,surface,attr,&value);Capture();if(ok)Write(out,value);
      return ok;});
    Bind<U(addr_t,addr_t)>("eglSwapBuffers",[this](addr_t d,addr_t s){E display=Native(d,Display),surface=Native(s,Surface,d);if(!display||!surface)return U(0);U ok=eglSwapBuffers(display,surface);Capture();return ok;});
    Bind<U(addr_t,I)>("eglSwapInterval",[this](addr_t d,I interval){E display=Native(d,Display);if(!display)return U(0);U ok=eglSwapInterval(display,interval);Capture();return ok;});
    Bind<U(addr_t,addr_t)>("eglDestroySurface",[this](addr_t d,addr_t s){E display=Native(d,Display),surface=Native(s,Surface,d);if(!display||!surface)return U(0);
      // ANGLE's default Vulkan workaround eagerly unbinds a current surface.
      // Defer the actual host destruction to preserve EGL current-object rules.
      auto &object=objects.at(s);if(!Held(s)){DestroyNative(object);}
      object.deleted=true;Prune();return U(1);});
    Bind<U(addr_t,addr_t)>("eglDestroyContext",[this](addr_t d,addr_t c){E display=Native(d,Display),context=Native(c,Context,d);if(!display||!context)return U(0);
      auto &object=objects.at(c);if(!Held(c)){DestroyNative(object);}
      object.deleted=true;Prune();return U(1);});
    Bind<U(addr_t)>("eglTerminate",[this](addr_t d){E display=Native(d,Display);if(!display)return U(0);U ok=eglTerminate(display);Capture();
      if(ok){display_window_formats.erase(d);for(auto &[token,o]:objects){(void)token;if(o.display==d){o.deleted=true;o.native_destroyed=true;}}Prune();}return ok;});
    Bind<I()>("eglGetError",[this]{auto &error=errors[owner];I value=error?error:Success;error=Success;return value;});
    Bind<addr_t(addr_t,I)>("eglQueryString",[this](addr_t d,I name){E display=d?Native(d,Display):nullptr;if(d&&!display)return addr_t(0);
      const char *native=eglQueryString(display,name);Capture();if(!native)return addr_t(0);std::string value=native;
      if(name==0x3055){std::istringstream input(value);std::string extension;value.clear();while(input>>extension){
        if(extension=="EGL_KHR_create_context"||extension=="EGL_KHR_surfaceless_context"||extension=="EGL_KHR_create_context_no_error"||extension=="EGL_KHR_gl_colorspace"||extension=="EGL_EXT_client_extensions"){
          if(!value.empty())value+=' ';
          value+=extension;}}}return String(value);});
    Bind<addr_t(addr_t)>("eglGetProcAddress",[this](addr_t name){const auto text=CString(name);auto it=bridges.find(text);
      if(it==bridges.end()){
        if(procedure_resolver)return procedure_resolver(text);
        throw std::runtime_error("Unsupported typed graphics resolver signature: "+text);
      }
      for(size_t i=0;i<std::size(names);++i)if(text==names[i])return marker+i*8;
      throw std::logic_error("EGL marker missing");});
  }
};
EglHost::EglHost(NativeWindows &windows,const std::wstring &directory,addr_t marker):impl_(std::make_unique<Impl>(windows,directory,marker)){}
EglHost::~EglHost()=default;
addr_t EglHost::Marker(const std::string &name)const{for(size_t i=0;i<std::size(names);++i)if(name==names[i])return impl_->marker+i*8;throw std::invalid_argument("Unsupported EGL import: "+name);}
void EglHost::Invoke(const std::string &name,State &state){std::lock_guard lock(impl_->mutex);auto found=impl_->bridges.find(name);if(found==impl_->bridges.end())throw std::invalid_argument("Unsupported EGL import: "+name);std::unique_ptr<WindowDpiScope> dpi;if(auto window=impl_->DpiWindow(name,&state))dpi=std::make_unique<WindowDpiScope>(window);found->second(state);}
void EglHost::Install(recomp::Runtime &runtime){if(impl_->installed)throw std::logic_error("EGL imports already installed");for(const auto *name:names)runtime.AddImport(Marker(name),[this,name](State &state){try{Invoke(name,state);}catch(const std::exception &e){std::fprintf(stderr,"EGL %s: %s\n",name,e.what());std::abort();}});impl_->installed=true;}
void EglHost::ReleaseCurrentThread(){std::lock_guard lock(impl_->mutex);impl_->ReleaseThread();}
void EglHost::SetProcedureResolver(std::function<addr_t(const std::string&)> resolver){std::lock_guard lock(impl_->mutex);impl_->procedure_resolver=std::move(resolver);}
}  // namespace bunker::windows

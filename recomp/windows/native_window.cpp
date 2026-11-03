#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "native_window.h"
#include "../whole/bridge.h"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <deque>
#include <future>
#include <limits>
#include <map>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace bunker::windows {
namespace {
std::atomic<uint64_t> next_owner{1};
std::atomic<addr_t> next_window{0x7ff410000000ULL};
constexpr UINT kCommand=WM_APP+147;
constexpr const wchar_t *kClass=L"BunkerRecompNativeWindow";
addr_t WindowToken(){auto current=next_window.load();do{
  if(current>=0x7ff420000000ULL)throw std::overflow_error("native window token namespace exhausted");
}while(!next_window.compare_exchange_weak(current,current+8));return current;}
const char *const imports[]={"ANativeWindow_fromSurface","ANativeWindow_acquire","ANativeWindow_release",
  "ANativeWindow_getWidth","ANativeWindow_getHeight","ANativeWindow_setBuffersGeometry"};
void Dimensions(int32_t width,int32_t height){
  if(width<=0||height<=0||width>32767||height>32767)throw std::invalid_argument("window client dimensions out of supported range");
}
template<class T>T UserProcedure(const char *name){
  auto address=GetProcAddress(GetModuleHandleW(L"user32.dll"),name);
  T function=nullptr;static_assert(sizeof(function)==sizeof(address));std::memcpy(&function,&address,sizeof(function));return function;
}
using SetDpi=HANDLE(WINAPI*)(HANDLE);
void ResizePhysical(HWND hwnd,int32_t width,int32_t height){
  for(unsigned attempt=0;attempt<3;++attempt){
    RECT client{},outer{};if(!GetClientRect(hwnd,&client)||!GetWindowRect(hwnd,&outer))throw std::runtime_error("cannot query native window geometry");
    if(client.right==width&&client.bottom==height)return;
    const int outer_width=outer.right-outer.left+width-client.right,outer_height=outer.bottom-outer.top+height-client.bottom;
    if(!SetWindowPos(hwnd,nullptr,0,0,outer_width,outer_height,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE))throw std::runtime_error("native client resize failed");
  }
  RECT actual{};GetClientRect(hwnd,&actual);
  if(actual.right==width&&actual.bottom==height)return;
  throw std::runtime_error("native client pixel size did not converge: requested "+std::to_string(width)+"x"+std::to_string(height)+
    ", observed "+std::to_string(actual.right)+"x"+std::to_string(actual.bottom));
}
}
WindowDpiScope::WindowDpiScope(void *window){
  using GetContext=HANDLE(WINAPI*)(HWND);
  auto get=UserProcedure<GetContext>("GetWindowDpiAwarenessContext");auto set=UserProcedure<SetDpi>("SetThreadDpiAwarenessContext");
  if(get&&set){auto context=get(static_cast<HWND>(window));if(!context||(previous_=set(context))==nullptr)throw std::runtime_error("cannot adopt native window DPI context");}
}
WindowDpiScope::~WindowDpiScope(){if(previous_)UserProcedure<SetDpi>("SetThreadDpiAwarenessContext")(previous_);}
class NativeWindows::Window {
 public:
  const uint64_t owner;
  const addr_t token;
  std::mutex mutex,geometry_operation;
  HWND hwnd=nullptr;
  int32_t client_width=0,client_height=0,buffer_width=0,buffer_height=0,buffer_format=0;
  std::vector<Event> events;
  explicit Window(uint64_t owner,int32_t width,int32_t height,const std::u16string &title,bool visible)
      :owner(owner),token(WindowToken()) {
    std::promise<void> ready;auto started=ready.get_future();
    thread=std::thread([this,width,height,title,visible,ready=std::move(ready)]()mutable{
      try{
        // A per-thread setting avoids changing the host process's DPI policy.
        auto dpi=UserProcedure<SetDpi>("SetThreadDpiAwarenessContext");
        if(dpi)dpi(reinterpret_cast<HANDLE>(-4));
        static std::once_flag registered;
        std::call_once(registered,[]{WNDCLASSW type{};type.style=CS_OWNDC;type.lpfnWndProc=Procedure;type.hInstance=GetModuleHandleW(nullptr);
          type.lpszClassName=kClass;type.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));
          if(!RegisterClassW(&type))throw std::runtime_error("cannot register native window class");});
        MSG message;PeekMessageW(&message,nullptr,WM_USER,WM_USER,PM_NOREMOVE);
        thread_id=GetCurrentThreadId();
        RECT rectangle{0,0,width,height};
        if(!AdjustWindowRectEx(&rectangle,WS_OVERLAPPEDWINDOW,FALSE,0))throw std::runtime_error("cannot size native window");
        static_assert(sizeof(wchar_t)==sizeof(char16_t));
        const std::wstring caption(reinterpret_cast<const wchar_t*>(title.data()),title.size());
        auto window=CreateWindowExW(0,kClass,caption.c_str(),WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,
          rectangle.right-rectangle.left,rectangle.bottom-rectangle.top,nullptr,nullptr,GetModuleHandleW(nullptr),this);
        if(!window)throw std::runtime_error("cannot create native Win32 window");
        {std::lock_guard lock(mutex);hwnd=window;}
        ResizePhysical(window,width,height);
        RefreshClient();
        if(visible)ShowWindow(window,SW_SHOWNORMAL);
        ready.set_value();
        while(GetMessageW(&message,nullptr,0,0)>0){
          if(!message.hwnd&&message.message==kCommand){
            std::deque<std::function<void()>> commands;
            {std::lock_guard lock(command_mutex);commands.swap(queue);}
            for(auto &command:commands)command();
          }else{TranslateMessage(&message);DispatchMessageW(&message);}
        }
      }catch(...){try{ready.set_exception(std::current_exception());}catch(...){} }
    });
    try{started.get();}catch(...){if(thread.joinable())thread.join();throw;}
  }
  ~Window(){
    if(thread.joinable()){
      try{Submit([this]{auto window=Native();if(window)DestroyWindow(window);PostQuitMessage(0);});}
      catch(...){std::terminate();}
      thread.join();
    }
  }
  HWND Native(){std::lock_guard lock(mutex);return hwnd;}
  void RefreshClient(){
    auto window=Native();RECT client{};
    if(!window||!GetClientRect(window,&client))throw std::runtime_error("cannot refresh native client geometry");
    std::lock_guard lock(mutex);
    if(client_width!=client.right||client_height!=client.bottom){
      client_width=client.right;client_height=client.bottom;events.push_back({Event::Resized,client_width,client_height,false});
    }
  }
  Geometry Description(){std::lock_guard lock(mutex);return{buffer_width?buffer_width:client_width,
    buffer_height?buffer_height:client_height,buffer_format?buffer_format:1,client_width,client_height,bool(buffer_width)};}
  void Submit(std::function<void()> function){
    if(GetCurrentThreadId()==thread_id){function();return;}
    auto task=std::make_shared<std::packaged_task<void()>>(std::move(function));auto done=task->get_future();
    {std::lock_guard lock(command_mutex);queue.emplace_back([task]{(*task)();});}
    if(!PostThreadMessageW(thread_id,kCommand,0,0))throw std::runtime_error("native window UI thread unavailable");
    done.get();
  }
  static LRESULT CALLBACK Procedure(HWND window,UINT message,WPARAM wparam,LPARAM lparam){
    auto *self=reinterpret_cast<Window*>(GetWindowLongPtrW(window,GWLP_USERDATA));
    if(message==WM_NCCREATE){self=static_cast<Window*>(reinterpret_cast<CREATESTRUCTW*>(lparam)->lpCreateParams);
      SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(self));}
    if(self){
      std::lock_guard lock(self->mutex);
      switch(message){
        case WM_SIZE:
          if(wparam!=SIZE_MINIMIZED){RECT client{};if(GetClientRect(window,&client)){
            self->client_width=client.right;self->client_height=client.bottom;
            self->events.push_back({Event::Resized,client.right,client.bottom,false});}}
          return 0;
        case WM_SETFOCUS:case WM_KILLFOCUS:self->events.push_back({Event::Focus,0,0,message==WM_SETFOCUS});return 0;
        // The lifecycle owner retires its EGL surface before actually closing.
        case WM_CLOSE:self->events.push_back({Event::CloseRequested});return 0;
        case WM_DESTROY:self->hwnd=nullptr;self->events.push_back({Event::Destroyed});return 0;
      }
    }
    return DefWindowProcW(window,message,wparam,lparam);
  }
 private:
  std::thread thread;
  DWORD thread_id=0;
  std::mutex command_mutex;
  std::deque<std::function<void()>> queue;
};
struct NativeWindows::Impl {
  struct Reference {std::weak_ptr<Window> weak;Handle retained;uint64_t count=0;};
  jni::Host &java;const uint64_t owner=next_owner++;addr_t marker;bool installed=false;
  mutable std::mutex mutex;std::map<addr_t,Reference> windows;ApplyGeometry apply;
  Impl(jni::Host &java,addr_t marker):java(java),marker(marker){}
  Handle Find(addr_t token)const{std::lock_guard lock(mutex);auto found=windows.find(token);
    if(found==windows.end())throw std::invalid_argument("unknown ANativeWindow pointer");
    auto window=found->second.weak.lock();if(!window)throw std::invalid_argument("expired ANativeWindow pointer");return window;}
};
NativeWindows::NativeWindows(jni::Host &java,addr_t marker):impl_(std::make_unique<Impl>(java,marker)){
  if(marker&7)throw std::invalid_argument("native window marker alignment");
  java.DefineClass("android/view/Surface",{},"java/lang/Object",true);
}
NativeWindows::~NativeWindows()=default;
NativeWindows::Handle NativeWindows::Create(int32_t width,int32_t height,const std::u16string &title,bool visible){
  Dimensions(width,height);if(title.find(u'\0')!=std::u16string::npos)throw std::invalid_argument("NUL window title");
  auto window=std::make_shared<Window>(impl_->owner,width,height,title,visible);
  {std::lock_guard lock(impl_->mutex);impl_->windows.emplace(window->token,Impl::Reference{window,{ },0});}
  return window;
}
addr_t NativeWindows::NewSurface(const Handle &window){
  if(!window||window->owner!=impl_->owner||!window->Native())throw std::invalid_argument("Surface needs a live owned Win32 window");
  return impl_->java.NewHostInstance("android/view/Surface",window);
}
addr_t NativeWindows::FromSurface(addr_t surface){
  if(!surface)return 0;
  auto window=impl_->java.ReadHostState<Window>(surface);
  if(!window)return 0;
  if(window->owner!=impl_->owner||!window->Native())return 0;
  Acquire(window->token);return window->token;
}
void NativeWindows::Acquire(addr_t token){
  std::lock_guard lock(impl_->mutex);auto found=impl_->windows.find(token);
  if(found==impl_->windows.end())throw std::invalid_argument("unknown ANativeWindow acquire");
  auto window=found->second.weak.lock();if(!window)throw std::invalid_argument("expired ANativeWindow acquire");
  if(found->second.count==UINT64_MAX)throw std::overflow_error("ANativeWindow reference count exhausted");
  found->second.retained=std::move(window);++found->second.count;
}
void NativeWindows::Release(addr_t token){
  Handle release;
  {std::lock_guard lock(impl_->mutex);auto found=impl_->windows.find(token);
    if(found==impl_->windows.end()||!found->second.count)throw std::invalid_argument("unbalanced ANativeWindow release");
    if(!--found->second.count)release=std::move(found->second.retained);}
  // Last native release may join the UI thread; no registry lock spans it.
}
NativeWindows::Geometry NativeWindows::Describe(addr_t token)const{
  auto window=impl_->Find(token);if(!window->Native())throw std::invalid_argument("closed ANativeWindow");return window->Description();
}
int32_t NativeWindows::Width(addr_t token)const{try{return Describe(token).width;}catch(const std::invalid_argument&){return -19;}}
int32_t NativeWindows::Height(addr_t token)const{try{return Describe(token).height;}catch(const std::invalid_argument&){return -19;}}
void *NativeWindows::NativeHandle(addr_t token)const{return impl_->Find(token)->Native();}
std::function<void*()> NativeWindows::NativeHandleReader(const Handle &window)const{
  if(!window||window->owner!=impl_->owner||!window->Native())throw std::invalid_argument("native handle reader needs a live owned window");
  std::weak_ptr<Window> weak=window;
  return [weak]()->void*{auto current=weak.lock();return current?current->Native():nullptr;};
}
void NativeWindows::SetGeometryBackend(ApplyGeometry apply){std::lock_guard lock(impl_->mutex);impl_->apply=std::move(apply);}
int NativeWindows::SetBuffersGeometry(addr_t token,int32_t width,int32_t height,int32_t format){
  if(width<0||height<0||bool(width)!=bool(height)||width>32767||height>32767)return -22;
  if(format!=0&&format!=1&&format!=2&&format!=3&&format!=4&&format!=22&&format!=43)return -22;
  Handle window;ApplyGeometry apply;
  try{window=impl_->Find(token);}catch(const std::invalid_argument&){return -19;}
  std::lock_guard mutation(window->geometry_operation);
  if(!window->Native())return -19;
  Geometry proposed=window->Description();proposed.width=width?width:proposed.client_width;
  proposed.height=height?height:proposed.client_height;proposed.format=format?format:1;
  proposed.fixed_size=bool(width);
  const auto old=window->Description();
  if(proposed.width!=old.width||proposed.height!=old.height||proposed.format!=old.format||proposed.fixed_size!=old.fixed_size){
    {std::lock_guard lock(impl_->mutex);apply=impl_->apply;}
    if(!apply)return -38;
    const int error=apply(token,proposed);if(error)return error;
  }
  {std::lock_guard lock(window->mutex);window->buffer_width=width;window->buffer_height=height;window->buffer_format=format;}
  return 0;
}
std::vector<NativeWindows::Event> NativeWindows::DrainEvents(const Handle &window){
  if(!window||window->owner!=impl_->owner)throw std::invalid_argument("window event owner mismatch");
  std::vector<Event> events;{std::lock_guard lock(window->mutex);events.swap(window->events);}return events;
}
void NativeWindows::ResizeClient(const Handle &window,int32_t width,int32_t height){
  Dimensions(width,height);if(!window||window->owner!=impl_->owner)throw std::invalid_argument("window resize owner mismatch");
  auto *raw=window.get();window->Submit([raw,width,height]{auto hwnd=raw->Native();if(!hwnd)throw std::invalid_argument("closed window resize");
    ResizePhysical(hwnd,width,height);raw->RefreshClient();});
}
void NativeWindows::Close(const Handle &window){
  if(!window||window->owner!=impl_->owner)throw std::invalid_argument("window close owner mismatch");
  auto *raw=window.get();window->Submit([raw]{auto hwnd=raw->Native();if(hwnd&&!DestroyWindow(hwnd))throw std::runtime_error("native window destruction failed");});
}
addr_t NativeWindows::Marker(const std::string &name)const{
  for(size_t i=0;i<std::size(imports);++i)if(name==imports[i])return impl_->marker+i*8;
  throw std::invalid_argument("unsupported native window import: "+name);
}
void NativeWindows::Install(recomp::Runtime &runtime){
  if(impl_->installed)throw std::logic_error("native window imports already installed");
  auto add=[&](const char *name,auto bridge){runtime.AddImport(Marker(name),[name,bridge](State &s){
    try{bridge(s);}catch(const std::exception &e){std::fprintf(stderr,"native window %s: %s\n",name,e.what());std::abort();}});};
  add(imports[0],recomp::MakeBridge<addr_t(addr_t,addr_t)>([this](addr_t env,addr_t surface){
    if(env!=impl_->java.EnvAddress())throw std::invalid_argument("ANativeWindow_fromSurface JNIEnv mismatch");
    return FromSurface(surface);}));
  add(imports[1],recomp::MakeBridge<void(addr_t)>([this](addr_t window){Acquire(window);}));
  add(imports[2],recomp::MakeBridge<void(addr_t)>([this](addr_t window){Release(window);}));
  add(imports[3],recomp::MakeBridge<int32_t(addr_t)>([this](addr_t window){return Width(window);}));
  add(imports[4],recomp::MakeBridge<int32_t(addr_t)>([this](addr_t window){return Height(window);}));
  add(imports[5],recomp::MakeBridge<int32_t(addr_t,int32_t,int32_t,int32_t)>([this](auto window,auto width,auto height,auto format){return SetBuffersGeometry(window,width,height,format);}));
  impl_->installed=true;
}
}  // namespace bunker::windows

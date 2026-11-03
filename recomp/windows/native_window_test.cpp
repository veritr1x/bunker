#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "native_window.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <thread>

using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};NativeWindows *provider;
void Check(bool value,const char *why){++checks;if(!value){std::fprintf(stderr,"native window check: %s\n",why);std::abort();}}
void *Resolve(const char *name){return reinterpret_cast<void*>(provider->Marker(name));}
}
int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(30));std::fputs("native window watchdog\n",stderr);std::_Exit(95);}).detach();
  bunker::jni::Host java([](addr_t){return false;});
  recomp::Runtime runtime;NativeWindows windows(java);provider=&windows;windows.Install(runtime);
  auto window=windows.Create(640,360,u"Bunker native window",false);
  auto surface=windows.NewSurface(window);Check(surface&&!java.PendingException().size(),"typed Surface owns actual HWND");
  const auto token=windows.FromSurface(surface);
  Check(token&&IsWindow(static_cast<HWND>(windows.NativeHandle(token))),"acquired ANativeWindow resolves real HWND");
  const auto initial_owners=window.use_count();
  auto reader=windows.NativeHandleReader(window);
  Check(reader()==windows.NativeHandle(token)&&window.use_count()==initial_owners,"reader observes owned HWND without retaining Window or acquiring native reference");
  bool invalid_reader=false;try{windows.NativeHandleReader({});}catch(const std::invalid_argument&){invalid_reader=true;}
  Check(invalid_reader,"reader rejects null Handle");
  {
    bunker::jni::Host foreign_java([](addr_t){return false;});NativeWindows foreign(foreign_java);
    auto other=foreign.Create(320,240,u"Bunker foreign reader",false);
    bool rejected=false;try{windows.NativeHandleReader(other);}catch(const std::invalid_argument&){rejected=true;}
    Check(rejected,"reader rejects another provider's live Handle");
  }
  WindowDpiScope dpi(windows.NativeHandle(token));
  RECT rectangle{};Check(GetClientRect(static_cast<HWND>(windows.NativeHandle(token)),&rectangle)&&rectangle.right==640&&rectangle.bottom==360,"native client pixel dimensions exact");
  auto geometry=windows.Describe(token);Check(geometry.width==640&&geometry.height==360&&geometry.format==1&&!geometry.fixed_size,"default Android buffer geometry");
  elf_image image{};Check(!elf_load(NATIVE_WINDOW_LIBRARY,0x5e000000,Resolve,&image),"NDK native-window fixture image load");
  runtime.AddTraces(kTraces,std::size(kTraces));
  alignas(16)uint8_t stack[65536]{};int64_t result[16]{};State state{};
  state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=surface;state.gpr.x2.qword=reinterpret_cast<addr_t>(result);
  state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));state.gpr.x30.qword=0xfeedffff;
  runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"window_guest")));
  const int64_t expected[]={static_cast<int64_t>(token),640,360,0,-38,-38,-22,-22,-22,640,360,1};
  Check(state.gpr.x0.qword==std::size(expected)&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack+sizeof(stack)),"NDK caller result count and balanced SP");
  for(size_t i=0;i<std::size(expected);++i)Check(result[i]==expected[i],"actual NDK fromSurface/refs/geometry/size result");
  Check(java.PendingException().empty(),"valid native-window calls preserve clean JNI state");
  windows.SetGeometryBackend([&](addr_t object,const NativeWindows::Geometry &proposed){
    Check(object==token&&proposed.width==320&&proposed.height==240&&proposed.fixed_size,"renderer receives separate requested buffer size");
    const auto old=windows.Describe(object);Check(old.client_width==640&&old.client_height==360&&!old.fixed_size,"backend query is unlocked and old state remains transactional");return -38;
  });
  Check(windows.SetBuffersGeometry(token,320,240,1)==-38&&windows.Width(token)==640,"unsupported renderer geometry does not claim allocated buffers");
  windows.SetGeometryBackend({});
  std::thread refs[4];for(auto &thread:refs)thread=std::thread([&]{for(unsigned i=0;i<64;++i){windows.Acquire(token);Check(windows.Width(token)==640,"concurrent native reference keeps live window");windows.Release(token);}});
  for(auto &thread:refs)thread.join();
  windows.DrainEvents(window);windows.ResizeClient(window,320,240);
  Check(windows.Width(token)==320&&windows.Height(token)==240,"real Win32 resize changes default buffer base size");
  auto events=windows.DrainEvents(window);bool resized=false;for(auto &event:events)resized|=event.kind==NativeWindows::Event::Resized&&event.width==320&&event.height==240;
  Check(resized,"lifecycle consumes actual client resize event");
  Check(windows.SetBuffersGeometry(token,0,0,0)==0,"zero geometry restores base values");
  auto hwnd=static_cast<HWND>(windows.NativeHandle(token));
  Check(PostMessageW(hwnd,WM_CLOSE,0,0),"queue actual UI close request");
  windows.ResizeClient(window,320,240);events=windows.DrainEvents(window);bool close_requested=false;
  for(auto &event:events)close_requested|=event.kind==NativeWindows::Event::CloseRequested;
  Check(close_requested&&IsWindow(hwnd),"UI close waits for lifecycle to retire EGL resources");
  windows.Close(window);Check(!IsWindow(hwnd)&&windows.Width(token)==-19,"explicit lifecycle close destroys actual HWND");
  Check(windows.FromSurface(surface)==0,"closed native Surface does not reacquire live window");
  Check(reader()==nullptr,"reader returns null for closed window still held by Java/native references");
  bool closed_reader=false;try{windows.NativeHandleReader(window);}catch(const std::invalid_argument&){closed_reader=true;}
  Check(closed_reader,"new reader rejects a closed owned Handle");
  windows.Release(token);java.DeleteLocalReference(surface);window.reset();
  Check(windows.Width(token)==-19,"expired window token cannot alias a later window");
  Check(reader()==nullptr,"reader returns null for expired Window");
  bool rejected=false;try{windows.Release(token);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"double native release rejected");
  auto retained=windows.Create(320,240,u"Bunker retained window",false);auto local=windows.NewSurface(retained);auto native=windows.FromSurface(local);
  retained.reset();java.DeleteLocalReference(local);
  Check(windows.Width(native)==320&&IsWindow(static_cast<HWND>(windows.NativeHandle(native))),"native reference retains window after Java and host references drop");
  windows.Release(native);Check(windows.Width(native)==-19,"last native release joins and retires UI window");
  {
    auto weak_only=windows.Create(320,240,u"Bunker weak reader",false);
    std::weak_ptr<NativeWindows::Window> weak=weak_only;
    auto observe=windows.NativeHandleReader(weak_only);auto hwnd=static_cast<HWND>(observe());
    weak_only.reset();
    Check(weak.expired()&&!IsWindow(hwnd)&&observe()==nullptr,"reader alone cannot retain Window or native HWND");
  }
  {
    bunker::jni::Host separate_java([](addr_t){return false;});
    auto separate=std::make_unique<NativeWindows>(separate_java);
    auto surviving=separate->Create(320,240,u"Bunker provider reader",false);
    auto observe=separate->NativeHandleReader(surviving);auto hwnd=static_cast<HWND>(observe());
    separate.reset();
    Check(observe()==hwnd&&IsWindow(hwnd),"reader remains safe after provider destruction while Window has a real owner");
    surviving.reset();
    Check(observe()==nullptr&&!IsWindow(hwnd),"reader after provider and Window destruction is safely null");
  }
  auto wrong=java.NewString(u"not a surface");Check(!windows.FromSurface(wrong)&&!java.PendingException().empty(),"wrong Java object fails checked host state");java.ClearException();java.DeleteLocalReference(wrong);
  Check(windows.Marker("ANativeWindow_getWidth")!=windows.Marker("ANativeWindow_getHeight"),"distinct native import markers");
  std::printf("Native Windows window provider: %u checks, six imports through actual NDK caller, real HWND/lifetime/events; scaled buffer backend remains explicit.\n",checks.load());
}

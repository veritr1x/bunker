#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "native_window.h"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

using namespace bunker::windows;
namespace {
unsigned checks=0;
void Check(bool ok,const char *why){++checks;if(!ok)throw std::runtime_error(why);}
constexpr UINT kBlock=WM_APP+811,kEnd=WM_APP+812;
struct Observation {UINT message;uint32_t time;DWORD thread;};
struct Observer {
  WNDPROC original=nullptr;HANDLE entered=CreateEventW(nullptr,TRUE,FALSE,nullptr),release=CreateEventW(nullptr,TRUE,FALSE,nullptr),done=CreateEventW(nullptr,TRUE,FALSE,nullptr);
  std::mutex mutex;std::vector<Observation> events;
  ~Observer(){if(entered)CloseHandle(entered);if(release)CloseHandle(release);if(done)CloseHandle(done);}
};
Observer *observer=nullptr;
bool Input(UINT m){return m==WM_MOUSEMOVE||m==WM_LBUTTONDOWN||m==WM_LBUTTONUP||m==WM_LBUTTONDBLCLK||m==WM_RBUTTONDOWN||m==WM_RBUTTONUP||m==WM_RBUTTONDBLCLK||m==WM_MBUTTONDOWN||m==WM_MBUTTONUP||m==WM_MBUTTONDBLCLK||m==WM_XBUTTONDOWN||m==WM_XBUTTONUP||m==WM_XBUTTONDBLCLK||m==WM_MOUSEWHEEL||m==WM_MOUSEHWHEEL||m==WM_KEYDOWN||m==WM_KEYUP||m==WM_SYSKEYDOWN||m==WM_SYSKEYUP;}
LRESULT CALLBACK Observe(HWND hwnd,UINT message,WPARAM wp,LPARAM lp)noexcept{
  auto &o=*observer;
  if(message==kBlock){SetEvent(o.entered);if(WaitForSingleObject(o.release,5000)!=WAIT_OBJECT_0)std::terminate();return 0;}
  if(message==kEnd){SetEvent(o.done);return 0;}
  if(Input(message)){std::lock_guard lock(o.mutex);o.events.push_back({message,static_cast<uint32_t>(GetMessageTime()),GetCurrentThreadId()});}
  return CallWindowProcW(o.original,hwnd,message,wp,lp);
}
struct Stimulus {UINT message;WPARAM wp;LPARAM lp;NativeWindows::Event::Kind kind;NativeWindows::MouseData mouse{};NativeWindows::KeyData key{};};
LPARAM Point(int x,int y){return static_cast<LPARAM>(static_cast<uint16_t>(x)|(uint32_t(static_cast<uint16_t>(y))<<16));}
LPARAM KeyBits(uint16_t repeat,uint8_t scan,bool ext,bool alt,bool previous,bool up){return static_cast<LPARAM>(uint32_t(repeat)|(uint32_t(scan)<<16)|(uint32_t(ext)<<24)|(uint32_t(alt)<<29)|(uint32_t(previous)<<30)|(uint32_t(up)<<31));}
}
int main(){
  try{
    static_assert(NativeWindows::Event::Resized==0&&NativeWindows::Event::Focus==1&&NativeWindows::Event::CloseRequested==2&&NativeWindows::Event::Destroyed==3);
    Check(sizeof(State)==1200&&sizeof(addr_t)==8&&sizeof(Memory*)==8,"selected actual State/address ABI");
    NativeWindows::Event legacy{NativeWindows::Event::Focus,11,22,true};Check(legacy.width==11&&legacy.height==22&&legacy.focused&&legacy.native_message==0,"old aggregate prefix stays compatible");
    bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);auto window=windows.Create(320,180,u"Bunker owned hidden input fixture",false);auto hwnd=static_cast<HWND>(windows.NativeHandleReader(window)());
    Check(IsWindow(hwnd)&&!IsWindowVisible(hwnd)&&GetForegroundWindow()!=hwnd,"fixture HWND is owned, hidden and never foreground");WindowDpiScope dpi(hwnd);
    Observer o;Check(o.entered&&o.release&&o.done,"fixture-only synchronization events");observer=&o;o.original=reinterpret_cast<WNDPROC>(GetWindowLongPtrW(hwnd,GWLP_WNDPROC));Check(o.original!=nullptr,"read own original window procedure");
    Check(reinterpret_cast<WNDPROC>(SetWindowLongPtrW(hwnd,GWLP_WNDPROC,reinterpret_cast<LONG_PTR>(&Observe)))==o.original,"observe only own hidden HWND");
    Check(PostMessageW(hwnd,kBlock,0,0)!=0&&WaitForSingleObject(o.entered,5000)==WAIT_OBJECT_0,"block own UI dequeue before test posts");windows.DrainEvents(window);
    std::vector<Stimulus> inputs;
    auto mouse=[&](UINT message,NativeWindows::Event::Kind kind,NativeWindows::MouseData::Button button,uint32_t state,int x,int y,uint16_t xb=0){Stimulus s{message,WPARAM(state)|(WPARAM(xb)<<16),Point(x,y),kind};s.mouse.x=x;s.mouse.y=y;s.mouse.client_position_valid=true;s.mouse.button_state=state;s.mouse.button=button;s.mouse.x_button_id=xb;inputs.push_back(s);};
    using E=NativeWindows::Event;using B=NativeWindows::MouseData::Button;
    mouse(WM_MOUSEMOVE,E::MouseMove,B::None,MK_CONTROL|MK_LBUTTON,-9,27);mouse(WM_MOUSEMOVE,E::MouseMove,B::None,MK_SHIFT,-32768,32767);
    for(auto row:std::vector<std::pair<UINT,B>>{{WM_LBUTTONDOWN,B::Left},{WM_LBUTTONDBLCLK,B::Left},{WM_RBUTTONDOWN,B::Right},{WM_RBUTTONDBLCLK,B::Right},{WM_MBUTTONDOWN,B::Middle},{WM_MBUTTONDBLCLK,B::Middle}})mouse(row.first,E::MouseButtonDown,row.second,MK_LBUTTON|MK_RBUTTON|MK_MBUTTON|MK_CONTROL,13,-22);
    for(auto row:std::vector<std::pair<UINT,B>>{{WM_LBUTTONUP,B::Left},{WM_RBUTTONUP,B::Right},{WM_MBUTTONUP,B::Middle}})mouse(row.first,E::MouseButtonUp,row.second,MK_SHIFT,-7,31);
    mouse(WM_XBUTTONDOWN,E::MouseButtonDown,B::X1,MK_XBUTTON1|MK_LBUTTON,-17,4,XBUTTON1);mouse(WM_XBUTTONUP,E::MouseButtonUp,B::X1,MK_RBUTTON,12,-6,XBUTTON1);mouse(WM_XBUTTONDBLCLK,E::MouseButtonDown,B::X1,MK_XBUTTON1,5,8,XBUTTON1);
    mouse(WM_XBUTTONDOWN,E::MouseButtonDown,B::X2,MK_XBUTTON2|MK_SHIFT,-15,10,XBUTTON2);mouse(WM_XBUTTONUP,E::MouseButtonUp,B::X2,MK_CONTROL,22,-11,XBUTTON2);
    for(bool horizontal:{false,true}){
      const int x=horizontal?33:-13,y=horizontal?-19:42,delta=horizontal?-30:120;const uint32_t state=horizontal?MK_SHIFT|MK_XBUTTON1:MK_CONTROL|MK_RBUTTON;POINT screen{x,y};Check(ClientToScreen(hwnd,&screen)!=0,"independent wheel screen-coordinate stimulus");Check(screen.x>=-32768&&screen.x<=32767&&screen.y>=-32768&&screen.y<=32767,"owned fixture location fits Win32 wheel message coordinate contract");
      Stimulus s{static_cast<UINT>(horizontal?WM_MOUSEHWHEEL:WM_MOUSEWHEEL),WPARAM(state)|(WPARAM(static_cast<uint16_t>(delta))<<16),Point(screen.x,screen.y),E::MouseWheel};s.mouse.x=x;s.mouse.y=y;s.mouse.client_position_valid=true;s.mouse.screen_x=screen.x;s.mouse.screen_y=screen.y;s.mouse.screen_position_valid=true;s.mouse.button_state=state;s.mouse.wheel_delta=delta;s.mouse.horizontal_wheel=horizontal;inputs.push_back(s);
    }
    auto key=[&](UINT message,uint32_t vk,uint16_t repeat,uint8_t scan,bool extended,bool alt,bool previous,bool up){Stimulus s{message,vk,KeyBits(repeat,scan,extended,alt,previous,up),up?E::KeyUp:E::KeyDown};s.key={vk,repeat,scan,extended,alt,previous,up,message==WM_SYSKEYDOWN||message==WM_SYSKEYUP};inputs.push_back(s);};
    key(WM_KEYDOWN,'A',3,0x1e,false,false,true,false);key(WM_KEYUP,'A',1,0x1e,false,false,true,true);key(WM_SYSKEYDOWN,VK_RIGHT,2,0x4d,true,true,false,false);key(WM_SYSKEYUP,VK_RIGHT,1,0x4d,true,true,true,true);key(WM_KEYDOWN,VK_F8,65535,0xff,true,false,true,false);
    const uint32_t posted_before=GetTickCount();for(const auto &s:inputs)Check(PostMessageW(hwnd,s.message,s.wp,s.lp)!=0,"post explicit test stimulus only to owned hidden window");const uint32_t posted_after=GetTickCount();std::this_thread::sleep_for(std::chrono::milliseconds(45));Check(SetEvent(o.release)!=0,"release fixture-only UI barrier");Check(PostMessageW(hwnd,kEnd,0,0)!=0&&WaitForSingleObject(o.done,5000)==WAIT_OBJECT_0,"all posted input messages finished default dispatch");
    auto actual=windows.DrainEvents(window);std::vector<E> captured;for(const auto &e:actual)if(e.kind>=E::MouseMove)captured.push_back(e);std::vector<Observation> observed;{std::lock_guard lock(o.mutex);observed=o.events;}
    Check(captured.size()==inputs.size()&&observed.size()==inputs.size(),"every actual dequeued test input appears once and in order");const auto ui_thread=GetWindowThreadProcessId(hwnd,nullptr);
    for(size_t i=0;i<inputs.size();++i){
      const auto &s=inputs[i];const auto &a=captured[i];Check(a.kind==s.kind&&a.native_message==s.message&&observed[i].message==s.message,"native message order and typed event kind preserved");Check(a.message_time_ms==observed[i].time&&observed[i].thread==ui_thread,"MSG.time equals independent WndProc GetMessageTime on the actual UI thread");Check(uint32_t(a.message_time_ms-posted_before)<=uint32_t(posted_after-posted_before),"queued input retains original post time rather than later dispatch time");Check(uint32_t(GetTickCount()-a.message_time_ms)>=20,"deliberate queued delay cannot be mistaken for a fresh synthetic clock");Check(a.width==0&&a.height==0&&!a.focused,"input never fabricates lifecycle fields");
      if(a.kind==E::KeyDown||a.kind==E::KeyUp){const auto &k=a.key,&e=s.key;Check(k.virtual_key==e.virtual_key&&k.repeat_count==e.repeat_count&&k.scan_code==e.scan_code&&k.extended==e.extended&&k.alt_context==e.alt_context&&k.previous_down==e.previous_down&&k.transition_up==e.transition_up&&k.system==e.system,"key direction/repeat/scancode/extended/Alt/previous/transition metadata exact");Check(!a.mouse.client_position_valid&&a.mouse.button_state==0,"keyboard payload cannot masquerade as pointer input");}
      else{const auto &m=a.mouse,&e=s.mouse;Check(m.client_position_valid&&m.x==e.x&&m.y==e.y&&m.client_position_error==0,"signed client coordinates preserved including negative and16-bit bounds");Check(m.button_state==e.button_state&&m.button==e.button&&m.x_button_id==e.x_button_id,"actual button flags and changed-button identity preserved");Check(m.wheel_delta==e.wheel_delta&&m.horizontal_wheel==e.horizontal_wheel&&m.screen_position_valid==e.screen_position_valid,"wheel direction and partial signed delta exact");if(e.screen_position_valid)Check(m.screen_x==e.screen_x&&m.screen_y==e.screen_y,"actual wheel screen position retained alongside converted client point");Check(a.key.virtual_key==0&&a.key.repeat_count==0,"pointer payload cannot masquerade as keyboard input");}
    }
    Check(reinterpret_cast<WNDPROC>(SetWindowLongPtrW(hwnd,GWLP_WNDPROC,reinterpret_cast<LONG_PTR>(o.original)))==&Observe,"restore only the owned fixture window procedure");observer=nullptr;
    windows.ResizeClient(window,300,170);auto resized=windows.DrainEvents(window);bool found_size=false;for(const auto &e:resized)found_size|=e.kind==E::Resized&&e.width==300&&e.height==170;Check(found_size,"real resize semantics still reach the lifecycle queue");
    Check(PostMessageW(hwnd,WM_CLOSE,0,0)!=0,"fixture close remains a request");bool found_close=false;const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(2);while(!found_close&&std::chrono::steady_clock::now()<until){for(const auto &e:windows.DrainEvents(window))found_close|=e.kind==E::CloseRequested;std::this_thread::sleep_for(std::chrono::milliseconds(1));}Check(found_close&&IsWindow(hwnd)&&!IsWindowVisible(hwnd)&&GetForegroundWindow()!=hwnd,"close still awaits lifecycle destruction and hidden fixture never steals focus");windows.Close(window);Check(!IsWindow(hwnd),"owned fixture HWND retired normally");
    std::printf("NATIVE-INPUT-PASS checks=%u messages=%zu hidden=1 timestamp_oracle=1 signed_client=1 wheel_screen_conversion=1 key_metadata=1 old_lifecycle=1 State=1200 Memory64=1 test_stimuli_only=1\n",checks,inputs.size());return 0;
  }catch(const std::exception &e){std::fprintf(stderr,"NATIVE-INPUT-FAIL %s\n",e.what());return 1;}
}

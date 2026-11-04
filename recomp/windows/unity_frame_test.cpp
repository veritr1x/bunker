#include "unity_lifecycle.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <future>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};
void Check(bool value,const char *why){++checks;if(!value)throw std::runtime_error(why);}
template<class F>void Reject(F f,const char *why){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Check(rejected,why);}
struct Fixture {
  bunker::jni::Host java{[](addr_t){return true;}};
  addr_t player=0,surface=0;
  std::vector<std::string> log;
  UnitySurfaceLifecycle *queue=nullptr;
  bool pause_result=false,done_result=false,render_result=true,throw_resume=false,throw_render=false;
  std::function<void()> render_hook,focus_hook;
  unsigned cleaned=0;
  std::thread::id caller=std::this_thread::get_id(),worker;
  Fixture(){java.DefineClass("com/unity3d/player/UnityPlayer");java.DefineClass("android/view/Surface");player=java.NewInstance("com/unity3d/player/UnityPlayer");surface=java.NewInstance("android/view/Surface");}
  uint64_t Run(addr_t entry,const std::vector<addr_t>&args){
    Check(std::this_thread::get_id()!=caller,"every native frame callback stays on UnityMain");
    if(worker==std::thread::id{})worker=std::this_thread::get_id();Check(worker==std::this_thread::get_id(),"one stable UnityMain thread");
    Check(args.size()>=2&&args[0]==java.EnvAddress()&&args[1]!=0,"native instance callback has worker env/receiver");
    switch(entry){
      case 1:log.push_back(args.at(3)?"surface":"detach");return 0;
      case 2:log.push_back("changed");return 0;
      case 3:log.push_back("resume");if(throw_resume)throw std::runtime_error("unsupported resume dependency");return 0;
      case 4:log.push_back(args.at(2)?"focus+":"focus-");if(focus_hook)focus_hook();return 0;
      case 5:Check(queue->Describe().resumed&&queue->Describe().surface,"render requires both resumed and surface");log.push_back("render");if(render_hook)render_hook();if(throw_render)throw std::runtime_error("original render dependency failed");return render_result;
      case 6:Check(!queue->Describe().resumed,"PAUSE message precedes nativePause Runnable");log.push_back("pause");return pause_result;
      case 7:Check(!queue->Describe().resumed,"PAUSE message precedes shutdown/nativeDone Runnable");log.push_back("done");return done_result;
      default:throw std::runtime_error("unexpected diagnostic native entry");
    }
  }
  UnitySurfaceLifecycle::Runner Runner(){return [this](addr_t entry,const std::vector<addr_t>&args){return Run(entry,args);};}
  UnitySurfaceLifecycle::WorkerExit Cleanup(){return [this]{Check(java.EnvAddress()!=0,"native lifecycle cleanup precedes JNI detach");++cleaned;};}
};
}
int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(20));std::fputs("one-frame FIFO watchdog\n",stderr);std::_Exit(95);}).detach();
  {
    Fixture f;f.done_result=true;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;
    Reject([&]{q.ConfigureOneFrame({3,4,0,6,7});},"incomplete frame native profile rejected");q.ConfigureOneFrame({3,4,5,6,7});
    q.AfterInitJni();q.Start();Reject([&]{q.ConfigureOneFrame({3,4,5,6,7});},"cannot change native profile after start");
    q.SurfaceCreated(f.surface);q.WaitIdle();q.ActivityResumed();q.WaitIdle();
    Check(f.log==std::vector<std::string>{"surface"},"activity resume alone cannot bypass initial focus prerequisite");
    q.WindowFocusChanged(true);Check(q.WaitForFrame(),"real nativeRender boolean is preserved");q.WaitIdle();
    Check(f.log==std::vector<std::string>{"surface","focus+","resume","render"},"focus delivery then first frame drains nativeResume before nativeRender");
    q.WaitIdle();Check(q.Describe().rendered==1,"diagnostic does not auto-schedule a second nativeRender");
    Reject([&]{q.ActivityResumed();},"a second resume cannot silently exceed one-frame budget");
    q.WindowFocusChanged(false);q.WaitIdle();Check(f.log.back()=="focus-","focus loss preserves native callback");
    q.PauseNative(true);Check(f.log.back()=="done","finishing pause selects nativeDone directly");
    Check(q.Describe().native_done&&q.Describe().process_kill_requested&&!q.Describe().initialized,"shutdown preserves native kill result and clears initialized");
    auto size=f.log.size();q.WindowFocusChanged(false);q.SurfaceDestroyed();q.Stop();
    Check(f.log.size()==size,"post-shutdown surface/focus callbacks respect initialized guard");Check(f.cleaned==1,"successful lifecycle cleans worker once");
  }
  {
    Fixture f;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();
    q.ActivityResumed();q.WindowFocusChanged(true);q.WaitIdle();
    Check(f.log==std::vector<std::string>{"resume"},"NEXT_FRAME drains resume job even while surface is absent");Check(q.Describe().rendered==0,"missing surface blocks nativeRender");
    q.SurfaceCreated(f.surface);Check(q.WaitForFrame(),"late acquired surface permits exactly one frame");q.WaitIdle();
    Check(f.log==std::vector<std::string>{"resume","surface","focus+","render"},"pending focus is delivered only after surface acquisition");
    q.PauseNative(false);Check(f.log.back()=="pause"&&!q.Describe().native_done&&q.Describe().initialized,"normal false nativePause result does not invent nativeDone");q.SurfaceDestroyed();q.Stop();Check(f.log.back()=="detach","normal paused surface detach still executes native recreate(null)");
  }
  {
    Fixture f;f.pause_result=true;f.render_result=false;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();q.SurfaceCreated(f.surface);q.ActivityResumed();q.WindowFocusChanged(true);
    Check(!q.WaitForFrame(),"false nativeRender result is reported to host activity owner");q.PauseNative(false);
    Check(f.log.size()>=2&&f.log[f.log.size()-2]=="pause"&&f.log.back()=="done","true nativePause result selects shutdown exactly after pause");q.SurfaceDestroyed();q.Stop();
  }
  {
    Fixture f;f.throw_resume=true;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();q.SurfaceCreated(f.surface);q.ActivityResumed();q.WindowFocusChanged(true);
    Reject([&]{q.WaitForFrame();},"resume failure reaches frame waiter instead of claiming a completed frame");Reject([&]{q.Stop();},"resume failure remains decisive through worker teardown");Check(f.cleaned==1,"failed resume cleans worker before JNI detach");
  }
  {
    Fixture f;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();
    Check(!q.PollFrame().has_value(),"pending first frame is distinct from an original false result");
    Reject([&]{q.RequestNextFrame();},"cannot continue before initial frame completes");
    q.SurfaceCreated(f.surface);q.ActivityResumed();q.WindowFocusChanged(true);Check(q.WaitForFrame(),"first frame returns true before continuation");q.WaitIdle();
    auto original_worker=f.worker;
    q.WindowFocusChanged(false);q.WaitIdle();Check(!q.RequestNextFrame(),"known lost focus cannot grant continuation");
    std::promise<void> focus_entered,focus_release;auto focus_released=focus_release.get_future().share();std::atomic<bool> focus_held{false};
    f.focus_hook=[&]{if(!focus_held.exchange(true)){focus_entered.set_value();focus_released.wait();}};
    q.WindowFocusChanged(true);focus_entered.get_future().get();
    Check(!q.RequestNextFrame(),"owner focus cannot bypass pending worker focus acknowledgment");focus_release.set_value();q.WaitIdle();f.focus_hook={};
    std::promise<void> entered,release;auto released=release.get_future().share();
    f.render_hook=[&]{entered.set_value();Reject([&]{q.RequestNextFrame();},"UnityMain cannot request its own continuation");released.wait();};
    Check(q.RequestNextFrame(),"completed true result permits one explicit request");entered.get_future().get();
    Check(!q.PollFrame().has_value(),"fresh request does not reuse ready prior future");
    Reject([&]{q.RequestNextFrame();},"duplicate in-flight continuation rejected");
    Check(q.Describe().requested_frames==2&&q.Describe().rendered==1,"requested and completed frame counters remain cumulative");
    release.set_value();Check(q.WaitForFrame(),"second actual result reaches its own promise");q.WaitIdle();f.render_hook={};
    Check(q.PollFrame()==std::optional<bool>(true),"poll returns actual completed true result");
    Check(f.worker==original_worker&&std::count(f.log.begin(),f.log.end(),"resume")==1&&std::count(f.log.begin(),f.log.end(),"render")==2,"continuation preserves worker and performs no second nativeResume");
    q.WaitIdle();Check(q.Describe().rendered==2,"explicit second request does not start a third frame");
    q.SurfaceDestroyed();Check(!q.RequestNextFrame(),"detached surface cannot grant continuation");
    q.PauseNative(false);Reject([&]{q.RequestNextFrame();},"paused Activity cannot grant continuation");q.Stop();
    Reject([&]{q.RequestNextFrame();},"stopped lifecycle cannot grant continuation");Check(f.cleaned==1,"continued lifecycle cleans worker exactly once");
  }
  {
    Fixture f;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();q.SurfaceCreated(f.surface);q.ActivityResumed();q.WindowFocusChanged(true);q.WaitForFrame();q.WaitIdle();
    f.render_result=false;Check(q.RequestNextFrame(),"next render may return a different actual boolean");Check(!q.WaitForFrame(),"second native false is retained");q.WaitIdle();
    Check(q.PollFrame()==std::optional<bool>(false),"ready original false is not pending");Reject([&]{q.RequestNextFrame();},"original false permanently refuses continuation");
    q.PauseNative(false);q.SurfaceDestroyed();q.Stop();
  }
  {
    Fixture f;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();q.SurfaceCreated(f.surface);q.ActivityResumed();q.WindowFocusChanged(true);q.WaitForFrame();q.WaitIdle();
    std::promise<void> entered,release;auto released=release.get_future().share();f.render_hook=[&]{entered.set_value();released.wait();};f.throw_render=true;
    Check(q.RequestNextFrame(),"render-failure request admitted before original call");entered.get_future().get();Check(!q.PollFrame().has_value(),"in-flight failing call remains pending until it throws");release.set_value();
    Reject([&]{q.WaitForFrame();},"second render exception reaches current waiter");Reject([&]{q.PollFrame();},"ready render exception reaches poller");Reject([&]{q.Stop();},"render exception preserved through stop");Check(f.cleaned==1,"failed continuation cleans worker exactly once");
  }
  {
    Fixture f;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();
    q.PauseNative(false);Reject([&]{q.WaitForFrame();},"pause settles an unused initial frame request");q.Stop();Check(f.cleaned==1,"canceled unused request still cleans worker");
  }
  {
    Fixture f;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();q.SurfaceCreated(f.surface);q.ActivityResumed();
    std::promise<void> entered,release;auto released=release.get_future().share();std::atomic<bool> held{false};
    f.focus_hook=[&]{if(!held.exchange(true)){entered.set_value();released.wait();}};
    q.WindowFocusChanged(true);entered.get_future().get();q.WindowFocusChanged(false);release.set_value();q.WaitIdle();
    Check(q.Describe().rendered==0&&!q.PollFrame().has_value(),"lost focus before first render preserves the initial pending request");
    f.focus_hook={};q.WindowFocusChanged(true);Check(q.WaitForFrame(),"regaining focus reschedules the same initial pending request");q.WaitIdle();
    Check(q.Describe().requested_frames==1&&q.Describe().rendered==1&&std::count(f.log.begin(),f.log.end(),"resume")==1,"focus recovery does not create another request or nativeResume");
    q.PauseNative(false);q.SurfaceDestroyed();q.Stop();
  }
  {
    Fixture f;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;
    q.ConfigureOneFrame({3,4,5,6,7},[&]{
      Check(std::this_thread::get_id()==f.worker,"GL jobs execute on the same attached UnityMain as native callbacks");
      Check(f.java.EnvAddress()!=0,"GL jobs retain the worker JNI environment");f.log.push_back("gljobs");
    });
    q.AfterInitJni();q.Start();q.SurfaceCreated(f.surface);q.ActivityResumed();q.WindowFocusChanged(true);q.WaitForFrame();q.WaitIdle();
    Check(f.log==std::vector<std::string>{"surface","focus+","gljobs","resume","render"},"NEXT_FRAME drains GL jobs before nativeResume and nativeRender");
    Check(q.RequestNextFrame()&&q.WaitForFrame(),"continuation executes the original render after another drain");q.WaitIdle();
    Check(f.log[f.log.size()-2]=="gljobs"&&f.log.back()=="render","each explicit NEXT_FRAME drains once before rendering");
    q.PauseNative(false);q.SurfaceDestroyed();q.Stop();
  }
  {
    Fixture f;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.queue=&q;
    q.ConfigureOneFrame({3,4,5,6,7},[]{throw std::runtime_error("GL job dependency failed");});
    q.AfterInitJni();q.Start();q.SurfaceCreated(f.surface);q.ActivityResumed();q.WindowFocusChanged(true);
    Reject([&]{q.WaitForFrame();},"GL job failure reaches frame waiter");Reject([&]{q.Stop();},"GL job failure remains visible through stop");
    Check(std::find(f.log.begin(),f.log.end(),"resume")==f.log.end()&&std::find(f.log.begin(),f.log.end(),"render")==f.log.end(),"failed GL job cannot fall through to nativeResume or nativeRender");
    Check(f.cleaned==1,"GL job failure retires the attached worker once");
  }
  std::printf("Bounded native frame FIFO: %u checks passed (synthetic callbacks; no real rendering claim)\n",checks.load());
}

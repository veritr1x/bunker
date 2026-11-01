#include "unity_lifecycle.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
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
  bool pause_result=false,done_result=false,render_result=true,throw_resume=false;
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
      case 4:log.push_back(args.at(2)?"focus+":"focus-");return 0;
      case 5:Check(queue->Describe().resumed&&queue->Describe().surface,"render requires both resumed and surface");log.push_back("render");return render_result;
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
  std::printf("Bounded native frame FIFO: %u checks passed (synthetic callbacks; no real rendering claim)\n",checks.load());
}

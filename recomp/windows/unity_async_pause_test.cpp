#include "unity_lifecycle.h"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <future>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
using namespace bunker::windows;
std::atomic<unsigned> checks{0},negatives{0};
void Check(bool ok,const char *why){++checks;if(!ok)throw std::runtime_error(why);}
template<class F>void Reject(F f,const char *why){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Check(rejected,why);++negatives;}
struct Fixture {
  bunker::jni::Host java{[](addr_t){return true;}};
  addr_t player=0,surface=0;
  UnitySurfaceLifecycle *queue=nullptr;
  std::thread::id caller=std::this_thread::get_id(),worker;
  std::atomic<unsigned> pauses{0},dones{0},cleanups{0};
  std::atomic<bool> resources{true};
  bool pause_result=false,done_result=false,hold=false,java_failure=false;
  std::promise<void> entered,release;std::shared_future<void> released=release.get_future().share();
  std::vector<unsigned> order;
  Fixture(){java.DefineClass("com/unity3d/player/UnityPlayer");java.DefineClass("android/view/Surface");player=java.NewInstance("com/unity3d/player/UnityPlayer");surface=java.NewInstance("android/view/Surface");}
  uint64_t Run(addr_t pc,const std::vector<addr_t>&args){
    Check(resources,"providers alive throughout actual callback");
    Check(std::this_thread::get_id()==worker&&worker!=caller,"same attached UnityMain callback");
    Check(args.size()>=2&&args[0]==java.EnvAddress()&&args[1],"actual worker JNI environment and receiver");
    if(pc==1||pc==2||pc==3||pc==4||pc==5)return 0;
    Check(!queue->Describe().resumed,"real FIFO Pause precedes native callback");
    if(pc==6){++pauses;return pause_result;}
    if(pc!=7)throw std::runtime_error("unexpected callback");
    ++dones;order.push_back(2);
    Reject([&]{queue->BeginPauseNative(true);},"worker cannot begin its own acknowledgment");
    Reject([&]{queue->PollNativePause();},"worker cannot poll its own acknowledgment");
    if(hold){entered.set_value();released.wait();}
    Check(resources,"providers retained until real callback returns");
    if(java_failure)java.ThrowException("java/lang/IllegalStateException",u"actual test callback failure");
    order.push_back(3);return done_result;
  }
  UnitySurfaceLifecycle::Runner Runner(){return [this](addr_t pc,const std::vector<addr_t>&args){return Run(pc,args);};}
  UnitySurfaceLifecycle::WorkerExit Cleanup(){return [this]{Check(resources,"providers survive worker cleanup");Check(std::this_thread::get_id()==worker&&java.EnvAddress()!=0,"same worker cleanup before JNI detach");++cleanups;};}
  void Start(UnitySurfaceLifecycle &q){queue=&q;q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start([&]{worker=std::this_thread::get_id();});}
  bool PollUntil(UnitySurfaceLifecycle &q){
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    while(!q.PollNativePause()){Check(std::chrono::steady_clock::now()<deadline,"released callback eventually acknowledges");std::this_thread::sleep_for(std::chrono::milliseconds(1));}
    return true;
  }
};
}

int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(25));std::fputs("async pause watchdog\n",stderr);std::_Exit(95);}).detach();
  try{
    {
      Fixture f;f.hold=true;f.done_result=true;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());
      Reject([&]{q.BeginPauseNative(true);},"begin before initialization rejected");Reject([&]{q.PollNativePause();},"poll without request rejected");f.Start(q);
      Check(q.Post([&]{f.order.push_back(1);}),"earlier real FIFO task queued");
      const auto start=std::chrono::steady_clock::now();q.BeginPauseNative(true);f.entered.get_future().get();
      Check(q.Post([&]{f.order.push_back(4);}),"later FIFO task queued without executing synchronously");
      Reject([&]{q.BeginPauseNative(true);},"duplicate asynchronous request rejected");
      Reject([&]{q.PauseNative(true);},"legacy request cannot duplicate outstanding job");
      Reject([&]{q.ActivityResumed();},"resume cannot reenter pending pause");
      for(unsigned i=0;i<9;++i){std::this_thread::sleep_for(std::chrono::milliseconds(500));Check(!q.PollNativePause(),"genuinely blocked callback remains pending without timeout");Check(f.resources&&f.cleanups==0,"event owner retains providers and attached worker");}
      Check(std::chrono::steady_clock::now()-start>=std::chrono::seconds(4),"actual pending interval exceeds legacy four seconds");
      Check(f.dones==1&&f.pauses==0&&!q.Describe().native_done&&q.Describe().initialized,"finishing calls Done once and fabricates no early status");
      f.release.set_value();Check(f.PollUntil(q),"actual success consumed");q.WaitIdle();
      Check(f.order==std::vector<unsigned>({1,2,3,4}),"same-worker FIFO tasks bracket actual Done return");
      Check(q.Describe().native_done&&q.Describe().process_kill_requested&&!q.Describe().initialized,"genuine Done result updates status before acknowledgment");
      Reject([&]{q.PollNativePause();},"success acknowledgment cannot be consumed twice");
      Reject([&]{q.BeginPauseNative(true);},"finished lifecycle cannot restart pause");q.SurfaceDestroyed();q.Stop();
      Check(f.cleanups==1&&f.dones==1&&f.pauses==0,"cleanup once after actual acknowledgment");f.resources=false;
    }
    {
      Fixture f;f.hold=true;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.Start(q);
      const auto start=std::chrono::steady_clock::now();bool timed_out=false;
      try{q.PauseNative(true);}catch(const std::runtime_error&e){timed_out=std::string(e.what())=="timeout waiting for native pause/shutdown acknowledgment";}
      Check(timed_out&&std::chrono::steady_clock::now()-start>=std::chrono::seconds(4),"legacy wait still reports original four-second timeout");
      f.entered.get_future().get();Check(!q.PollNativePause()&&f.cleanups==0&&f.dones==1,"legacy timeout neither cancels nor acknowledges callback");
      f.release.set_value();Check(f.PollUntil(q),"legacy timed-out request retains genuine later acknowledgment");q.SurfaceDestroyed();q.Stop();Check(f.cleanups==1,"legacy eventual cleanup once");f.resources=false;
    }
    {
      Fixture f;f.hold=true;f.java_failure=true;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.Start(q);q.BeginPauseNative(true);f.entered.get_future().get();
      Check(!q.PollNativePause(),"pending error is not fabricated before callback finishes");f.release.set_value();
      bool propagated=false;const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
      while(!propagated){try{Check(!q.PollNativePause(),"failing callback cannot claim successful acknowledgment");}catch(const std::runtime_error&e){propagated=std::string(e.what()).find("actual test callback failure")!=std::string::npos;}Check(std::chrono::steady_clock::now()<deadline,"callback failure reaches owner");std::this_thread::sleep_for(std::chrono::milliseconds(1));}
      Check(!q.Describe().native_done&&q.Describe().initialized,"callback Java error cannot fabricate nativeDone status");
      Reject([&]{q.PollNativePause();},"error acknowledgment consumed once");Reject([&]{q.BeginPauseNative(true);},"observed callback failure rejects immediate reentry");Reject([&]{q.Stop();},"worker failure remains decisive through actual join");Check(f.cleanups==1,"exception path cleanup once before JNI detach");Check(f.java.PendingException().empty(),"worker Java exception does not migrate to UI JNI state");f.resources=false;
    }
    for(bool wants_done:{false,true}){
      Fixture f;f.pause_result=wants_done;UnitySurfaceLifecycle q(f.java,f.Runner(),{1,2},f.player,f.Cleanup());f.Start(q);q.BeginPauseNative(false);Check(f.PollUntil(q),"normal pause actual acknowledgment");
      Check(f.pauses==1&&f.dones==unsigned(wants_done),"normal nativePause boolean alone selects nativeDone");Check(q.Describe().native_done==wants_done&&q.Describe().initialized!=wants_done,"normal pause preserves real status branch");q.SurfaceDestroyed();q.Stop();Check(f.cleanups==1,"normal branch worker cleanup once");f.resources=false;
    }
    std::printf("ASYNC-PAUSE-PASS checks=%u negatives=%u delayed_over4s=1 legacy_timeout4s=1 cases=5 native_callbacks=6 same_worker=1 exact_finishing_branch=1 genuine_exception=1 providers_retained=1\n",checks.load(),negatives.load());return 0;
  }catch(const std::exception&e){std::fprintf(stderr,"ASYNC-PAUSE-FAIL %s\n",e.what());return 1;}
}

#include "unity_lifecycle.h"
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>

using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};
void Check(bool value,const char *message){++checks;if(!value)throw std::runtime_error(message);}
template<class F>void Reject(F fn,const char *message){bool rejected=false;try{fn();}catch(const std::exception&){rejected=true;}Check(rejected,message);}
addr_t RefKind(bunker::jni::Host &java,addr_t object){State state{};state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=object;java.InvokeEnv(232,state);return state.gpr.x0.qword;}
}
int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(20));std::fputs("surface FIFO watchdog\n",stderr);std::_Exit(95);}).detach();
  bunker::jni::Host java([](addr_t){return true;});
  java.DefineClass("com/unity3d/player/UnityPlayer");java.DefineClass("android/view/Surface",{},"java/lang/Object",true);
  auto player=java.NewHostInstance("com/unity3d/player/UnityPlayer",std::make_shared<int>(7));
  auto state=std::make_shared<int>(19);std::weak_ptr<int> lifetime=state;
  auto surface=java.NewHostInstance("android/view/Surface",state);state.reset();
  const auto caller=std::this_thread::get_id();std::thread::id worker;std::vector<std::string> log;
  std::mutex gate;std::condition_variable cv;bool allow=false;std::atomic<int> released{0};
  UnitySurfaceLifecycle *lifecycle=nullptr;
  recomp::Runtime runtime;
  // These are explicitly synthetic Runtime import callbacks; the separate real
  // Unity harness is the translated-library execution gate.
  runtime.AddImport(0x72000100,[&](State &s){
    {std::unique_lock<std::mutex> lock(gate);cv.wait(lock,[&]{return allow;});}
    worker=std::this_thread::get_id();Check(worker!=caller,"native callbacks run on dedicated UnityMain worker");
    Check(s.gpr.x0.qword==java.EnvAddress()&&s.gpr.x0.qword!=0,"worker owns a valid attached JNIEnv");
    Check(RefKind(java,s.gpr.x1.qword)==1,"worker receiver is a caller-local reference");
    Check(*java.ReadHostState<int>(s.gpr.x1.qword)==7,"UnityPlayer survives caller-local deletion");
    Check(s.gpr.x2.qword==0,"main display ID is zero");
    auto object=s.gpr.x3.qword;
    if(object){Check(RefKind(java,object)==1,"recreate receives worker-local Surface");Check(*java.ReadHostState<int>(object)==19,"queued Surface retains typed host state");log.push_back("recreate");}
    else{Check(!lifecycle->Describe().surface,"SURFACE_LOST precedes recreate(null)");log.push_back("detach");}
    Check(!lifecycle->Describe().resumed,"surface-only path never resumes or schedules rendering");
  });
  runtime.AddImport(0x72000200,[&](State &){Check(lifecycle->Describe().surface,"SURFACE_ACQUIRED precedes changed notification");Check(std::this_thread::get_id()==worker,"changed uses same UnityMain FIFO");log.push_back("changed");});
  auto run=[&](addr_t entry,const std::vector<addr_t>&args){State s{};if(args.size()>0)s.gpr.x0.qword=args[0];if(args.size()>1)s.gpr.x1.qword=args[1];if(args.size()>2)s.gpr.x2.qword=args[2];if(args.size()>3)s.gpr.x3.qword=args[3];s.gpr.x30.qword=0xfffffff0;runtime.Run(s,entry);return s.gpr.x0.qword;};
  UnitySurfaceLifecycle queue(java,run,{0x72000100,0x72000200},player,[&]{Check(java.EnvAddress()!=0,"runner TLS cleanup occurs before JNI detach");++released;});lifecycle=&queue;
  Reject([&]{queue.Start();},"UnityMain cannot start before real initJni completion transition");
  Reject([&]{queue.SurfaceCreated(surface);},"surface callbacks cannot run before UnityMain starts");
  queue.AfterInitJni();Check(queue.Describe().initialized,"post-init flag is explicit");
  std::atomic<bool> entered{false};
  Reject([&]{queue.AfterInitJni();},"duplicate post-init transition rejected");queue.Start([&]{Check(std::this_thread::get_id()!=caller,"WorkerEnter runs on UnityMain");Check(java.EnvAddress()!=0,"WorkerEnter runs after JNI attachment");entered=true;});Check(entered,"WorkerEnter completes before Start acknowledges readiness");
  Reject([&]{queue.SurfaceCreated(player);},"wrong Surface object type rejected");Reject([&]{queue.SurfaceChanged(0);},"null changed Surface rejected");
  auto dead=java.NewInstance("android/view/Surface");State weak_state{};weak_state.gpr.x0.qword=java.EnvAddress();weak_state.gpr.x1.qword=dead;java.InvokeEnv(226,weak_state);auto weak=weak_state.gpr.x0.qword;java.DeleteLocalReference(dead);
  Reject([&]{queue.SurfaceCreated(weak);},"cleared weak Surface is rejected despite IsInstanceOf(null) semantics");
  queue.SurfaceCreated(surface);queue.SurfaceChanged(surface);
  Reject([&]{queue.Stop();},"queued acquisition requires detach even before worker has run");
  java.DeleteLocalReference(surface);java.DeleteLocalReference(player);Check(!lifetime.expired(),"FIFO retains Surface after caller reference deletion");
  {std::lock_guard<std::mutex> lock(gate);allow=true;}cv.notify_all();queue.WaitIdle();
  Check((log==std::vector<std::string>{"recreate","recreate","changed"}),"created/change native callbacks retain APK FIFO ordering");
  Check(queue.Describe().surface&&!queue.Describe().resumed,"surface acquired while player remains paused");
  Check(lifetime.expired(),"consumed queued Surface roots are released");queue.SurfaceDestroyed();queue.Stop();
  Check(log.back()=="detach","destroy acknowledges completed native detach");Check(released==1,"runner worker TLS released exactly once");Check(!queue.Describe().started&&!queue.Describe().surface,"stopped and detached state");
  Reject([&]{queue.WaitIdle();},"post-stop submission rejected");
  auto player2=java.NewInstance("com/unity3d/player/UnityPlayer"),surface2=java.NewInstance("android/view/Surface");
  std::atomic<int> failed_cleanup{0};
  UnitySurfaceLifecycle broken(java,[](addr_t,const std::vector<addr_t>&)->uint64_t{throw std::runtime_error("real callback failure");},{1,2},player2,[&]{++failed_cleanup;});
  broken.AfterInitJni();broken.Start();broken.SurfaceCreated(surface2);
  Reject([&]{broken.WaitIdle();},"native callback failure reaches waiting owner");Reject([&]{broken.Stop();},"callback failure is retained on stop");Check(failed_cleanup==1,"failed callback still cleans runner TLS before detaching");
  Check(java.PendingException().empty(),"all expected host sequencing errors leave caller Java state clear");
  std::atomic<int> entry_cleanup{0};
  UnitySurfaceLifecycle bad_entry(java,run,{1,2},player2,[&]{Check(java.EnvAddress()!=0,"failed WorkerEnter cleans up while JNI attached");++entry_cleanup;});bad_entry.AfterInitJni();
  Reject([&]{bad_entry.Start([]{throw std::runtime_error("virtual-thread registration failed");});},"WorkerEnter failure reaches Start caller");
  Reject([&]{bad_entry.Stop();},"WorkerEnter failure remains decisive on Stop");Check(entry_cleanup==1,"failed WorkerEnter still runs worker cleanup exactly once");
  std::printf("UnityMain surface FIFO: %u checks passed (synthetic Runtime callbacks; no render/resume)\n",checks.load());
}

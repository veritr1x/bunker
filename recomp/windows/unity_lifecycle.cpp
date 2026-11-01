#include "unity_lifecycle.h"
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <cstdio>
#include <deque>
#include <future>
#include <mutex>
#include <stdexcept>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#endif

namespace bunker::windows {
struct UnitySurfaceLifecycle::Impl {
  struct Job {enum Kind{Recreate,Acquire,Lost,Changed,Barrier,Resume,FocusGained,FocusLost,Frame,Pause,PauseNative};Kind kind; jni::Host::ObjectValue surface; std::shared_ptr<std::promise<void>> ack;bool finishing=false;};
  jni::Host &java;Runner run;WorkerExit worker_exit;Entries entries;jni::Host::ObjectValue player;
  mutable std::mutex mutex;std::condition_variable ready;std::deque<Job> jobs;
  std::thread worker;Status status;bool stopping=false,attached=false,requested_surface=false;
  std::exception_ptr failure;
  FrameEntries frame_entries{};
  enum FocusState {Unfocused,PendingFocus,Focused};FocusState focus=Unfocused;
  bool frame_configured=false,activity_paused=true,activity_focused=false,activity_running=false;
  bool resume_job=false,frame_queued=false,frame_signaled=false;
  std::shared_ptr<std::promise<bool>> frame_done;std::shared_future<bool> frame_result;
  Impl(jni::Host &host,Runner runner,Entries addresses,addr_t receiver,WorkerExit exit):java(host),run(std::move(runner)),worker_exit(std::move(exit)),entries(addresses){
    if(!run||!worker_exit||!entries.recreate||!entries.changed)throw std::invalid_argument("surface lifecycle needs native entries, runner and worker cleanup");
    RequireType(receiver,"com/unity3d/player/UnityPlayer");player=java.CaptureValue(receiver);
  }
  void Check(){if(failure)std::rethrow_exception(failure);}
  void RequireType(addr_t object,const char *name){
    if(!object)throw std::invalid_argument("surface lifecycle requires a nonnull typed object");
    // JNI IsInstanceOf(null, clazz) is true, so it cannot by itself reject a
    // cleared weak reference supplied where a live Surface/player is required.
    auto retained=java.NewLocalReference(object);
    if(!retained)throw std::invalid_argument("surface lifecycle requires a live object reference");
    java.DeleteLocalReference(retained);
    State s{};s.gpr.x0.qword=java.EnvAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(name);java.InvokeEnv(6,s);auto clazz=s.gpr.x0.qword;
    if(!clazz||!java.PendingException().empty())throw std::runtime_error("surface lifecycle class lookup failed: "+java.PendingException());
    s={};s.gpr.x0.qword=java.EnvAddress();s.gpr.x1.qword=object;s.gpr.x2.qword=clazz;java.InvokeEnv(32,s);java.DeleteLocalReference(clazz);
    if(!s.gpr.x0.qword||!java.PendingException().empty())throw std::invalid_argument(std::string("surface lifecycle wrong object type: ")+name);
  }
  void RequireStarted(){Check();if(!status.started||stopping)throw std::logic_error("UnityMain surface queue is not running");}
  void RequireFrame(){RequireStarted();if(!frame_configured||!status.initialized)throw std::logic_error("native frame lifecycle is not configured/initialized");}
  void MaybeResumeLocked(){
    if(status.initialized&&!activity_paused&&activity_focused&&!activity_running){
      activity_running=true;resume_job=true;jobs.push_back({Job::Resume,{},{}});
    }
  }
  uint64_t Native(addr_t entry,addr_t receiver,std::optional<addr_t> value={}){
    std::vector<addr_t> args{java.EnvAddress(),receiver};if(value)args.push_back(*value);
    auto result=run(entry,args);
    if(!java.PendingException().empty())throw std::runtime_error("native frame callback raised: "+java.PendingException());
    return result;
  }
  void MaybeFocus(addr_t receiver){
    bool notify=false;
    {std::lock_guard<std::mutex> lock(mutex);notify=frame_configured&&status.initialized&&status.surface&&focus==PendingFocus;}
    if(notify){Native(frame_entries.focus,receiver,1);std::lock_guard<std::mutex> lock(mutex);focus=Focused;}
  }
  void ScheduleFrame(){
    std::lock_guard<std::mutex> lock(mutex);
    if(frame_configured&&status.initialized&&status.resumed&&(status.surface||resume_job)&&!status.rendered&&!frame_queued){frame_queued=true;jobs.push_back({Job::Frame,{},{}});}
  }
  void NativeDone(addr_t receiver){
    auto kill=Native(frame_entries.done,receiver);
    std::lock_guard<std::mutex> lock(mutex);status.native_done=true;status.process_kill_requested=static_cast<int32_t>(kill)!=0;status.initialized=false;
  }
  void FrameJob(addr_t receiver){
    bool invoke_resume=false,render=false;
    {std::lock_guard<std::mutex> lock(mutex);frame_queued=false;invoke_resume=resume_job;resume_job=false;}
    // DEX NEXT_FRAME drains GL jobs before checking resumed/surface flags.
    if(invoke_resume)Native(frame_entries.resume,receiver);
    {std::lock_guard<std::mutex> lock(mutex);render=status.initialized&&status.resumed&&status.surface&&!status.rendered;}
    if(render){
      auto result=Native(frame_entries.render,receiver);
      {std::lock_guard<std::mutex> lock(mutex);++status.rendered;frame_signaled=true;}
      frame_done->set_value(static_cast<int32_t>(result)!=0);
      // Diagnostic budget: no automatic second NEXT_FRAME is scheduled. The
      // owner requests an explicit finishing PAUSE after this first boundary.
    }
  }
  void Call(const Job &job,addr_t receiver){
    addr_t surface=0;
    if(job.kind==Job::Recreate)surface=java.LocalValue(job.surface);
    try{
      if(job.kind==Job::Recreate)run(entries.recreate,{java.EnvAddress(),receiver,0,surface});
      else if(job.kind==Job::Changed)run(entries.changed,{java.EnvAddress(),receiver});
      if(!java.PendingException().empty())throw std::runtime_error("surface lifecycle native callback raised: "+java.PendingException());
    }catch(...){if(surface)java.DeleteLocalReference(surface);throw;}
    if(surface)java.DeleteLocalReference(surface);
  }
  void Work(std::promise<void> startup,WorkerEnter enter){
    bool startup_sent=false;addr_t receiver=0;
    try{
      addr_t env=0;State vm{};vm.gpr.x0.qword=java.VmAddress();vm.gpr.x1.qword=reinterpret_cast<addr_t>(&env);java.InvokeVm(4,vm);
      if(static_cast<int32_t>(vm.gpr.x0.dword)||!env)throw std::runtime_error("UnityMain AttachCurrentThread failed");
      attached=true;receiver=java.LocalValue(player);
      if(enter)enter();
#ifdef _WIN32
      // Naming is diagnostic; no Android service or scheduling result is faked.
      using SetDescription=HRESULT(WINAPI*)(HANDLE,PCWSTR);
      auto address=GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"SetThreadDescription");
      SetDescription set=nullptr;static_assert(sizeof(set)==sizeof(address));std::memcpy(&set,&address,sizeof(set));
      if(set)set(GetCurrentThread(),L"UnityMain");
#endif
      startup.set_value();startup_sent=true;
      while(true){
        Job job;
        {std::unique_lock<std::mutex> lock(mutex);ready.wait(lock,[&]{return stopping||!jobs.empty();});if(jobs.empty()&&stopping)break;job=std::move(jobs.front());jobs.pop_front();}
        if(job.kind==Job::Barrier){std::lock_guard<std::mutex> lock(mutex);if(frame_queued){jobs.push_back(std::move(job));continue;}}
        try{
          if(job.kind==Job::Recreate||job.kind==Job::Changed)Call(job,receiver);
          {std::lock_guard<std::mutex> lock(mutex);if(job.kind==Job::Acquire)status.surface=true;if(job.kind==Job::Lost)status.surface=false;if(job.kind==Job::Resume)status.resumed=true;if(job.kind==Job::Pause)status.resumed=false;++status.completed;}
          if(job.kind==Job::Acquire){MaybeFocus(receiver);ScheduleFrame();}
          if(job.kind==Job::Resume)ScheduleFrame();
          if(job.kind==Job::FocusGained){focus=PendingFocus;MaybeFocus(receiver);}
          if(job.kind==Job::FocusLost){if(focus==Focused)Native(frame_entries.focus,receiver,0);focus=Unfocused;}
          if(job.kind==Job::Frame)FrameJob(receiver);
          if(job.kind==Job::PauseNative){
            if(job.finishing||static_cast<int32_t>(Native(frame_entries.pause,receiver))!=0)NativeDone(receiver);
          }
          if(job.ack)job.ack->set_value();
        }catch(...){if(job.ack)job.ack->set_exception(std::current_exception());throw;}
      }
    }catch(...){
      auto exception=std::current_exception();
      {std::lock_guard<std::mutex> lock(mutex);failure=exception;stopping=true;for(auto &job:jobs)if(job.ack)job.ack->set_exception(exception);jobs.clear();if(frame_done&&!frame_signaled){frame_signaled=true;frame_done->set_exception(exception);}}
      if(!startup_sent)startup.set_exception(exception);
    }
    if(attached){try{worker_exit();}catch(...){std::lock_guard<std::mutex> lock(mutex);if(!failure)failure=std::current_exception();}}
    if(receiver)java.DeleteLocalReference(receiver);
    if(attached){State vm{};vm.gpr.x0.qword=java.VmAddress();java.InvokeVm(5,vm);if(static_cast<int32_t>(vm.gpr.x0.dword)){std::lock_guard<std::mutex> lock(mutex);if(!failure)failure=std::make_exception_ptr(std::runtime_error("UnityMain DetachCurrentThread failed"));}}
  }
};
UnitySurfaceLifecycle::UnitySurfaceLifecycle(jni::Host &java,Runner runner,Entries entries,addr_t player,WorkerExit exit):impl_(std::make_unique<Impl>(java,std::move(runner),entries,player,std::move(exit))){}
UnitySurfaceLifecycle::~UnitySurfaceLifecycle(){
  // Destruction always drains/joins even after a reported error. Explicit Stop
  // exposes failures to the owner; no guest callbacks outlive provider teardown.
  auto &p=*impl_;{std::lock_guard<std::mutex> lock(p.mutex);p.stopping=true;}p.ready.notify_all();if(p.worker.joinable())p.worker.join();
}
void UnitySurfaceLifecycle::AfterInitJni(){auto &p=*impl_;std::lock_guard<std::mutex> lock(p.mutex);p.Check();if(p.status.initialized||p.status.started)throw std::logic_error("duplicate post-init transition");if(!p.java.PendingException().empty())throw std::logic_error("post-init transition with pending Java exception");p.status.initialized=true;}
void UnitySurfaceLifecycle::Start(WorkerEnter enter){auto &p=*impl_;std::promise<void> start;auto done=start.get_future();{std::lock_guard<std::mutex> lock(p.mutex);p.Check();if(!p.status.initialized||p.status.started||p.stopping)throw std::logic_error("invalid UnityMain start ordering");p.status.started=true;p.worker=std::thread([&p,start=std::move(start),enter=std::move(enter)]()mutable{p.Work(std::move(start),std::move(enter));});}done.get();}
void UnitySurfaceLifecycle::ConfigureOneFrame(FrameEntries entries){
  auto &p=*impl_;std::lock_guard<std::mutex> lock(p.mutex);p.Check();
  if(p.status.started||p.frame_configured||!entries.resume||!entries.focus||!entries.render||!entries.pause||!entries.done)throw std::invalid_argument("one-frame profile needs all native entries before UnityMain starts");
  p.frame_entries=entries;p.frame_configured=true;p.frame_done=std::make_shared<std::promise<bool>>();p.frame_result=p.frame_done->get_future().share();
}
void UnitySurfaceLifecycle::ActivityResumed(){auto &p=*impl_;{std::lock_guard<std::mutex> lock(p.mutex);p.RequireFrame();if(p.status.rendered)throw std::logic_error("one-frame diagnostic budget exhausted");p.activity_paused=false;p.MaybeResumeLocked();}p.ready.notify_one();}
void UnitySurfaceLifecycle::WindowFocusChanged(bool focused){auto &p=*impl_;{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();if(!p.frame_configured)throw std::logic_error("native frame lifecycle is not configured");p.activity_focused=focused;if(!p.status.initialized)return;p.jobs.push_back({focused?Impl::Job::FocusGained:Impl::Job::FocusLost,{},{}});p.MaybeResumeLocked();}p.ready.notify_one();}
bool UnitySurfaceLifecycle::WaitForFrame(){auto &p=*impl_;{std::lock_guard<std::mutex> lock(p.mutex);p.RequireFrame();if(std::this_thread::get_id()==p.worker.get_id())throw std::logic_error("UnityMain cannot wait for its own frame");}if(p.frame_result.wait_for(std::chrono::seconds(30))!=std::future_status::ready)throw std::runtime_error("one-frame diagnostic timed out before nativeRender completed");return p.frame_result.get();}
void UnitySurfaceLifecycle::PauseNative(bool finishing){
  auto &p=*impl_;auto ack=std::make_shared<std::promise<void>>();auto done=ack->get_future();
  {std::lock_guard<std::mutex> lock(p.mutex);p.RequireFrame();if(std::this_thread::get_id()==p.worker.get_id())throw std::logic_error("UnityMain cannot wait on its own pause acknowledgment");p.jobs.push_back({Impl::Job::Pause,{},{}});p.jobs.push_back({Impl::Job::PauseNative,{},ack,finishing});}
  p.ready.notify_one();if(done.wait_for(std::chrono::seconds(4))!=std::future_status::ready)throw std::runtime_error("timeout waiting for native pause/shutdown acknowledgment");done.get();
  {std::lock_guard<std::mutex> lock(p.mutex);p.activity_paused=true;p.activity_running=false;}
}
void UnitySurfaceLifecycle::SurfaceCreated(addr_t surface){auto &p=*impl_;p.RequireType(surface,"android/view/Surface");auto value=p.java.CaptureValue(surface);{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();p.requested_surface=true;p.jobs.push_back({Impl::Job::Recreate,value,{}});p.jobs.push_back({Impl::Job::Acquire,{},{}});}p.ready.notify_one();}
void UnitySurfaceLifecycle::SurfaceChanged(addr_t surface){auto &p=*impl_;p.RequireType(surface,"android/view/Surface");auto value=p.java.CaptureValue(surface);{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();p.requested_surface=true;p.jobs.push_back({Impl::Job::Recreate,value,{}});p.jobs.push_back({Impl::Job::Acquire,{},{}});p.jobs.push_back({Impl::Job::Changed,{},{}});}p.ready.notify_one();}
void UnitySurfaceLifecycle::SurfaceDestroyed(){auto &p=*impl_;auto ack=std::make_shared<std::promise<void>>();auto done=ack->get_future();{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();if(std::this_thread::get_id()==p.worker.get_id())throw std::logic_error("UnityMain cannot wait for its own surface acknowledgment");p.requested_surface=false;if(!p.status.initialized){p.status.surface=false;return;}p.jobs.push_back({Impl::Job::Lost,{},{}});p.jobs.push_back({Impl::Job::Recreate,{},ack});}p.ready.notify_one();if(done.wait_for(std::chrono::seconds(4))!=std::future_status::ready)throw std::runtime_error("timeout detaching primary Unity surface; retain HWND until UnityMain stops");done.get();}
void UnitySurfaceLifecycle::WaitIdle(){auto &p=*impl_;auto ack=std::make_shared<std::promise<void>>();auto done=ack->get_future();{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();if(std::this_thread::get_id()==p.worker.get_id())throw std::logic_error("UnityMain cannot wait on its own FIFO");p.jobs.push_back({Impl::Job::Barrier,{},ack});}p.ready.notify_one();done.get();}
void UnitySurfaceLifecycle::Stop(){auto &p=*impl_;{std::lock_guard<std::mutex> lock(p.mutex);if(p.worker.joinable()&&std::this_thread::get_id()==p.worker.get_id())throw std::logic_error("UnityMain cannot join itself");if(p.requested_surface&&!p.failure)throw std::logic_error("detach the primary Unity surface before stopping UnityMain");p.stopping=true;}p.ready.notify_all();if(p.worker.joinable())p.worker.join();{std::lock_guard<std::mutex> lock(p.mutex);p.status.started=false;p.Check();}}
UnitySurfaceLifecycle::Status UnitySurfaceLifecycle::Describe()const{auto &p=*impl_;std::lock_guard<std::mutex> lock(p.mutex);return p.status;}
} // namespace bunker::windows

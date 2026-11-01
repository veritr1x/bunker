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
  struct Job {enum Kind{Recreate,Acquire,Lost,Changed,Barrier};Kind kind; jni::Host::ObjectValue surface; std::shared_ptr<std::promise<void>> ack;};
  jni::Host &java;Runner run;WorkerExit worker_exit;Entries entries;jni::Host::ObjectValue player;
  mutable std::mutex mutex;std::condition_variable ready;std::deque<Job> jobs;
  std::thread worker;Status status;bool stopping=false,attached=false,requested_surface=false;
  std::exception_ptr failure;
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
  void Work(std::promise<void> startup){
    bool startup_sent=false;addr_t receiver=0;
    try{
      addr_t env=0;State vm{};vm.gpr.x0.qword=java.VmAddress();vm.gpr.x1.qword=reinterpret_cast<addr_t>(&env);java.InvokeVm(4,vm);
      if(static_cast<int32_t>(vm.gpr.x0.dword)||!env)throw std::runtime_error("UnityMain AttachCurrentThread failed");
      attached=true;receiver=java.LocalValue(player);
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
        try{
          if(job.kind==Job::Recreate||job.kind==Job::Changed)Call(job,receiver);
          {std::lock_guard<std::mutex> lock(mutex);if(job.kind==Job::Acquire)status.surface=true;if(job.kind==Job::Lost)status.surface=false;++status.completed;}
          if(job.ack)job.ack->set_value();
        }catch(...){if(job.ack)job.ack->set_exception(std::current_exception());throw;}
      }
    }catch(...){
      auto exception=std::current_exception();
      {std::lock_guard<std::mutex> lock(mutex);failure=exception;stopping=true;for(auto &job:jobs)if(job.ack)job.ack->set_exception(exception);jobs.clear();}
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
void UnitySurfaceLifecycle::Start(){auto &p=*impl_;std::promise<void> start;auto done=start.get_future();{std::lock_guard<std::mutex> lock(p.mutex);p.Check();if(!p.status.initialized||p.status.started||p.stopping)throw std::logic_error("invalid UnityMain start ordering");p.status.started=true;p.worker=std::thread([&p,start=std::move(start)]()mutable{p.Work(std::move(start));});}done.get();}
void UnitySurfaceLifecycle::SurfaceCreated(addr_t surface){auto &p=*impl_;p.RequireType(surface,"android/view/Surface");auto value=p.java.CaptureValue(surface);{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();p.requested_surface=true;p.jobs.push_back({Impl::Job::Recreate,value,{}});p.jobs.push_back({Impl::Job::Acquire,{},{}});}p.ready.notify_one();}
void UnitySurfaceLifecycle::SurfaceChanged(addr_t surface){auto &p=*impl_;p.RequireType(surface,"android/view/Surface");auto value=p.java.CaptureValue(surface);{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();p.requested_surface=true;p.jobs.push_back({Impl::Job::Recreate,value,{}});p.jobs.push_back({Impl::Job::Acquire,{},{}});p.jobs.push_back({Impl::Job::Changed,{},{}});}p.ready.notify_one();}
void UnitySurfaceLifecycle::SurfaceDestroyed(){auto &p=*impl_;auto ack=std::make_shared<std::promise<void>>();auto done=ack->get_future();{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();if(std::this_thread::get_id()==p.worker.get_id())throw std::logic_error("UnityMain cannot wait for its own surface acknowledgment");p.requested_surface=false;p.jobs.push_back({Impl::Job::Lost,{},{}});p.jobs.push_back({Impl::Job::Recreate,{},ack});}p.ready.notify_one();if(done.wait_for(std::chrono::seconds(4))!=std::future_status::ready)throw std::runtime_error("timeout detaching primary Unity surface; retain HWND until UnityMain stops");done.get();}
void UnitySurfaceLifecycle::WaitIdle(){auto &p=*impl_;auto ack=std::make_shared<std::promise<void>>();auto done=ack->get_future();{std::lock_guard<std::mutex> lock(p.mutex);p.RequireStarted();if(std::this_thread::get_id()==p.worker.get_id())throw std::logic_error("UnityMain cannot wait on its own FIFO");p.jobs.push_back({Impl::Job::Barrier,{},ack});}p.ready.notify_one();done.get();}
void UnitySurfaceLifecycle::Stop(){auto &p=*impl_;{std::lock_guard<std::mutex> lock(p.mutex);if(p.worker.joinable()&&std::this_thread::get_id()==p.worker.get_id())throw std::logic_error("UnityMain cannot join itself");if(p.requested_surface&&!p.failure)throw std::logic_error("detach the primary Unity surface before stopping UnityMain");p.stopping=true;}p.ready.notify_all();if(p.worker.joinable())p.worker.join();{std::lock_guard<std::mutex> lock(p.mutex);p.status.started=false;p.Check();}}
UnitySurfaceLifecycle::Status UnitySurfaceLifecycle::Describe()const{auto &p=*impl_;std::lock_guard<std::mutex> lock(p.mutex);return p.status;}
} // namespace bunker::windows

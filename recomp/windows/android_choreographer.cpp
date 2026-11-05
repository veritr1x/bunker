#include <cfenv>
#include "android_choreographer.h"
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <limits>
#include <map>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

namespace bunker::windows {
namespace {
constexpr const char* kThread="java/lang/Thread";
constexpr const char* kHandlerThread="android/os/HandlerThread";
constexpr const char* kLooper="android/os/Looper";
constexpr const char* kHandler="android/os/Handler";
constexpr const char* kHandlerCallback="android/os/Handler$Callback";
constexpr const char* kMessage="android/os/Message";
constexpr const char* kChoreographer="android/view/Choreographer";
constexpr const char* kFrameCallback="android/view/Choreographer$FrameCallback";
using Value=jni::Host::ObjectValue;
struct Environment {
#ifdef _WIN32
  DWORD error=GetLastError();
#endif
  int saved_errno=errno;fenv_t floating{};
  Environment(){std::fegetenv(&floating);}
  ~Environment(){std::fesetenv(&floating);errno=saved_errno;
#ifdef _WIN32
    SetLastError(error);
#endif
  }
};
addr_t Env(jni::Host& h,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){
  ::State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;
  h.InvokeEnv(slot,s);return s.gpr.x0.qword;
}
void Healthy(jni::Host& h){if(!h.PendingException().empty())throw std::runtime_error("Android queue JNI operation failed: "+h.PendingException());}
addr_t Method(jni::Host& h,const char* owner,const char* name,const char* signature,bool stat=false){
  const auto clazz=Env(h,6,reinterpret_cast<addr_t>(owner));Healthy(h);
  const auto result=Env(h,stat?113:33,clazz,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(signature));
  h.DeleteLocalReference(clazz);Healthy(h);return result;
}
struct Frame {
  Value callback;std::atomic<bool> cancelled{false};int64_t due_ns=0;
};
struct Thread {
  const void* owner;std::u16string name;
  std::mutex mutex;std::condition_variable ready;std::thread worker;
  bool started=false,starting=false,joining=false,joined=false,prepared=false,done=false,quitting=false,safe_quit=false;
  bool external=false,pumping=false,pump_queued=false,owner_wake_active=false;
  std::function<bool()> wake_owner;
  std::thread::id worker_id;
  Value looper,choreographer;bool choreographer_created=false;
  std::deque<Value> messages;std::vector<std::shared_ptr<Frame>> frames;
  int64_t next_frame_ns=0;
  explicit Thread(const void* p,std::u16string n):owner(p),name(std::move(n)){}
};
struct Looper {const void* owner;std::weak_ptr<Thread> thread;};
struct Handler {const void* owner;std::weak_ptr<Thread> thread;Value callback;bool has_callback=false;};
struct Message {const void* owner;std::mutex mutex;Value handler;bool enqueued=false;explicit Message(const void* p):owner(p){}};
struct Choreographer {const void* owner;std::weak_ptr<Thread> thread;};
struct LocalFrame {
  jni::Host& host;
  explicit LocalFrame(jni::Host& h):host(h){if(static_cast<int32_t>(Env(h,19,32)))throw std::runtime_error("Android queue local-frame allocation failed");Healthy(h);}
  ~LocalFrame(){try{Env(host,20,0);}catch(...){std::terminate();}}
};
}  // namespace

struct AndroidChoreographer::Shared:std::enable_shared_from_this<Shared> {
  jni::Host& host;Config config;
  mutable std::mutex mutex;bool active=true,stopping=false;
  std::vector<std::shared_ptr<Thread>> threads;
  std::map<std::thread::id,std::weak_ptr<Thread>> prepared;
  std::exception_ptr failure;
  Shared(jni::Host& h,Config c):host(h),config(std::move(c)){}
  void Check()const{std::lock_guard lock(mutex);if(failure)std::rethrow_exception(failure);}
  void Require()const{std::lock_guard lock(mutex);if(failure)std::rethrow_exception(failure);if(!active)throw std::runtime_error("Android queue service is stopped");}
  void Observe(const char* operation,const std::shared_ptr<Thread>& thread,int32_t what=0,int64_t stamp=0){
    Environment native;if(config.observer)config.observer(Event{operation,thread->name,what,stamp});
  }
  template<class T> std::shared_ptr<T> Payload(addr_t receiver){
    auto value=host.ReadHostState<T>(receiver);Healthy(host);
    if(!value||value->owner!=this)throw std::runtime_error("Android queue object does not belong to this service");return value;
  }
  std::shared_ptr<Thread> Current(){
    std::lock_guard lock(mutex);auto found=prepared.find(std::this_thread::get_id());
    return found==prepared.end()?nullptr:found->second.lock();
  }
  std::shared_ptr<Thread> Target(const std::weak_ptr<Thread>& weak){auto thread=weak.lock();if(!thread)throw std::runtime_error("Android Looper owner expired");return thread;}
  void Type(addr_t object,const char* name){
    if(!object){host.ThrowException("java/lang/NullPointerException");return;}
    auto clazz=Env(host,6,reinterpret_cast<addr_t>(name));Healthy(host);
    const bool correct=Env(host,32,object,clazz)!=0;host.DeleteLocalReference(clazz);Healthy(host);
    if(!correct)host.ThrowException("java/lang/IllegalArgumentException");
  }
  ClockSample Clock(const std::shared_ptr<Thread>& thread){
    Environment native;const auto sample=config.read_frame_clock();
    if(sample.monotonic_ns<0||!sample.refresh_numerator||!sample.refresh_denominator)
      throw std::runtime_error("Android nominal frame clock requires real monotonic time and observed refresh");
    // Independent callers can sample and return out of order. Do not mistake
    // that valid race for a backwards clock, or fabricate a replacement time.
    return sample;
  }
  static int64_t Period(const ClockSample& clock){
    const uint64_t value=UINT64_C(1000000000)*clock.refresh_denominator/clock.refresh_numerator;
    if(!value||value>uint64_t(INT64_MAX))throw std::runtime_error("Android observed refresh period is outside the native clock range");return static_cast<int64_t>(value);
  }
  static int64_t Next(int64_t now,int64_t period){if(now>INT64_MAX-period)throw std::overflow_error("Android nominal frame deadline overflow");return now+period;}
  void Quit(const std::shared_ptr<Thread>& thread,bool safe){
    std::deque<Value> discarded;std::vector<std::shared_ptr<Frame>> frames;
    {std::lock_guard lock(thread->mutex);thread->quitting=true;thread->safe_quit=safe;
      if(!safe)discarded.swap(thread->messages);frames.swap(thread->frames);}
    for(auto& frame:frames)frame->cancelled.store(true,std::memory_order_release);
    thread->ready.notify_all();
  }
  void Failed(std::exception_ptr error){
    {std::lock_guard lock(mutex);if(!failure)failure=error;}
    if(config.failure)try{Environment native;config.failure(error);}catch(...){/* Preserve the original worker failure. */}
  }
  void Dispatch(const std::shared_ptr<Thread>& thread,const Value& message){
    {std::lock_guard lock(thread->mutex);if(thread->quitting&&!thread->safe_quit)return;}
    LocalFrame frame(host);const auto local=host.LocalValue(message);auto m=Payload<Message>(local);
    Value target;{std::lock_guard lock(m->mutex);target=m->handler;}
    const auto handler=host.LocalValue(target);auto h=Payload<Handler>(handler);
    auto clazz=Env(host,6,reinterpret_cast<addr_t>(kMessage));
    const auto field=Env(host,94,clazz,reinterpret_cast<addr_t>("what"),reinterpret_cast<addr_t>("I"));
    const auto what=static_cast<int32_t>(Env(host,100,local,field));Healthy(host);
    Observe("dispatchMessage",thread,what);
    if(h->has_callback){
      const auto callback=host.LocalValue(h->callback);
      Env(host,37,callback,Method(host,kHandlerCallback,"handleMessage","(Landroid/os/Message;)Z"),local);Healthy(host);
    }
    // The actual base Handler.handleMessage implementation is empty. This
    // bounded profile has no Runnable or user-subclass Handler dispatch body.
  }
  void DispatchFrame(const std::shared_ptr<Thread>& thread,const std::shared_ptr<Frame>& request,int64_t stamp){
    if(request->cancelled.load(std::memory_order_acquire))return;
    // Quit/Stop also cancels requests already extracted for this pulse but
    // not yet admitted to dispatch. No service lock spans the actual callback.
    {std::lock_guard lock(thread->mutex);if(thread->quitting)return;}
    LocalFrame frame(host);const auto callback=host.LocalValue(request->callback);
    Observe("doFrame",thread,0,stamp);
    Env(host,61,callback,Method(host,kFrameCallback,"doFrame","(J)V"),static_cast<addr_t>(stamp));Healthy(host);
  }
  void Work(const std::shared_ptr<Thread>& thread,const Config::WorkerLease& lease){
    bool entered=false;
    try{
      config.enter_worker(thread->name,lease);entered=true;
      if(!host.EnvAddress())throw std::runtime_error("Android worker hook did not attach the actual JNI thread");Healthy(host);
      {LocalFrame frame(host);const auto looper=host.NewHostInstance(kLooper,std::make_shared<Looper>(Looper{this,thread}));
        auto value=host.CaptureValue(looper);
        {std::lock_guard lock(thread->mutex);thread->looper=std::move(value);thread->prepared=true;}}
      {std::lock_guard lock(mutex);prepared[std::this_thread::get_id()]=thread;}
      thread->ready.notify_all();Observe("prepared",thread);
      for(;;){
        Value message;bool have_message=false;std::vector<std::shared_ptr<Frame>> due;
        bool has_frames=false;
        {std::unique_lock lock(thread->mutex);
          if(thread->quitting&&(!thread->safe_quit||thread->messages.empty()))break;
          if(!thread->messages.empty()){message=std::move(thread->messages.front());thread->messages.pop_front();have_message=true;}
          else if(thread->frames.empty()){thread->ready.wait(lock);continue;}
          else has_frames=true;}
        if(have_message){Dispatch(thread,message);continue;}
        if(has_frames){
          const auto clock=Clock(thread);
          int64_t earliest=INT64_MAX;
          {std::lock_guard lock(thread->mutex);
            for(auto it=thread->frames.begin();it!=thread->frames.end();){
              if((*it)->cancelled.load(std::memory_order_acquire))it=thread->frames.erase(it);
              else if((*it)->due_ns<=clock.monotonic_ns){due.push_back(*it);it=thread->frames.erase(it);}
              else{earliest=std::min(earliest,(*it)->due_ns);++it;}}
            if(!due.empty())thread->next_frame_ns=Next(clock.monotonic_ns,Period(clock));}
          for(const auto& request:due)DispatchFrame(thread,request,clock.monotonic_ns);
          if(due.empty()&&earliest!=INT64_MAX){
            const auto delay=std::min<int64_t>(earliest-clock.monotonic_ns,INT64_C(50000000));
            std::unique_lock lock(thread->mutex);
            if(thread->messages.empty()&&!thread->quitting)thread->ready.wait_for(lock,std::chrono::nanoseconds(std::max<int64_t>(delay,1)));}
        }
      }
    }catch(...){Failed(std::current_exception());}
    std::deque<Value> messages;std::vector<std::shared_ptr<Frame>> frames;
    {std::lock_guard lock(thread->mutex);messages.swap(thread->messages);frames.swap(thread->frames);thread->quitting=true;}
    for(auto& frame:frames)frame->cancelled.store(true,std::memory_order_release);
    if(entered)try{config.exit_worker(lease);}catch(...){Failed(std::current_exception());}
    {std::lock_guard lock(mutex);prepared.erase(std::this_thread::get_id());}
    {std::lock_guard lock(thread->mutex);thread->done=true;}
    thread->ready.notify_all();
  }
  addr_t NewThread(addr_t name){
    Require();if(!name){host.ThrowException("java/lang/NullPointerException");return 0;}
    auto text=host.StringValue(name);Healthy(host);if(!text)return 0;
    auto thread=std::make_shared<Thread>(this,*text);
    {std::lock_guard lock(mutex);if(!active||stopping)throw std::runtime_error("Android queue service is stopping");threads.push_back(thread);}
    return host.NewHostInstance(kHandlerThread,thread);
  }
  void Start(addr_t receiver){
    Require();auto thread=Payload<Thread>(receiver);
    {std::lock_guard lock(thread->mutex);
      if(thread->started){host.ThrowException("java/lang/IllegalThreadStateException");return;}
      if(thread->quitting)throw std::runtime_error("cannot start stopped Android worker");
      thread->started=true;thread->starting=true;}
    try{
      auto lease=config.prepare_worker(thread->name);
      if(!lease)throw std::runtime_error("Android worker preparation returned no owned creator context");
      auto self=shared_from_this();
      {std::lock_guard lock(thread->mutex);
        if(thread->quitting)throw std::runtime_error("Android service stopped during worker preparation");
        thread->worker=std::thread([self,thread,lease]{self->Work(thread,lease);});
        thread->worker_id=thread->worker.get_id();thread->starting=false;}
      thread->ready.notify_all();
    }catch(...){
      {std::lock_guard lock(thread->mutex);thread->started=false;thread->starting=false;}
      thread->ready.notify_all();throw;
    }
  }
  addr_t GetLooper(addr_t receiver){
    Require();auto thread=Payload<Thread>(receiver);Value value;
    {std::unique_lock lock(thread->mutex);if(!thread->started)return 0;thread->ready.wait(lock,[&]{return thread->prepared||thread->done;});if(!thread->done)value=thread->looper;}
    Check();return host.LocalValue(value);
  }
  bool Alive(addr_t receiver){Require();auto thread=Payload<Thread>(receiver);std::lock_guard lock(thread->mutex);return thread->started&&!thread->done;}
  void JoinThread(const std::shared_ptr<Thread>& thread){
    {std::unique_lock lock(thread->mutex);
      if(thread->external){
        if(!thread->done)throw std::logic_error("external Android Looper must be released by its actual owner before Stop");
        thread->joined=true;return; // The lifecycle owns its actual native thread.
      }
      if(!thread->started||thread->joined)return;
      if(thread->worker_id==std::this_thread::get_id())throw std::runtime_error("joining the current Android HandlerThread is outside this profile");
      thread->ready.wait(lock,[&]{return !thread->starting&&!thread->joining;});
      if(!thread->started||thread->joined)return;thread->joining=true;}
    try{if(thread->worker.joinable())thread->worker.join();}
    catch(...){std::lock_guard lock(thread->mutex);thread->joining=false;thread->ready.notify_all();throw;}
    {std::lock_guard lock(thread->mutex);thread->joined=true;thread->joining=false;}
    thread->ready.notify_all();
  }
  void Join(addr_t receiver){Require();JoinThread(Payload<Thread>(receiver));Check();}
  addr_t HandlerLooper(addr_t receiver){
    Require();auto thread=Target(Payload<Handler>(receiver)->thread);Value value;
    {std::lock_guard lock(thread->mutex);value=thread->looper;}return host.LocalValue(value);
  }
  addr_t MessageTarget(addr_t receiver){
    Require();auto message=Payload<Message>(receiver);Value value;
    {std::lock_guard lock(message->mutex);value=message->handler;}return host.LocalValue(value);
  }
  addr_t NewHandler(addr_t looper,addr_t callback,bool use_current=false){
    Require();
    if(!looper&&!use_current){host.ThrowException("java/lang/NullPointerException",u"Handler requires a nonnull Looper");return 0;}
    auto thread=looper?Target(Payload<Looper>(looper)->thread):Current();
    if(!thread){host.ThrowException("java/lang/RuntimeException",u"Handler requires a prepared Looper");return 0;}
    if(callback){Type(callback,kHandlerCallback);if(!host.PendingException().empty())return 0;}
    return host.NewHostInstance(kHandler,std::make_shared<Handler>(Handler{this,thread,callback?host.CaptureValue(callback):Value{},callback!=0}));
  }
  addr_t Obtain(addr_t receiver,int32_t what){
    Require();Payload<Handler>(receiver);auto m=std::make_shared<Message>(this);m->handler=host.CaptureValue(receiver);
    auto result=host.NewHostInstance(kMessage,m);host.SetIntFieldValue(result,"what",what);return result;
  }
  bool Send(addr_t message){
    Require();auto m=Payload<Message>(message);Value target;
    {std::lock_guard lock(m->mutex);if(m->enqueued){host.ThrowException("java/lang/IllegalStateException",u"Message is already in use");return false;}m->enqueued=true;target=m->handler;}
    const auto local=host.LocalValue(target);auto h=Payload<Handler>(local);host.DeleteLocalReference(local);auto thread=Target(h->thread);
    auto retained=host.CaptureValue(message);
    bool wake=false,waking_on_owner=false;std::function<bool()> wake_callback;
    {std::lock_guard lock(thread->mutex);if(thread->quitting||thread->done)return false;
      thread->messages.push_back(std::move(retained));
      if(thread->external&&!thread->pump_queued){thread->pump_queued=true;wake=true;wake_callback=thread->wake_owner;
        waking_on_owner=thread->worker_id==std::this_thread::get_id();if(waking_on_owner)thread->owner_wake_active=true;}}
    if(wake){
      bool accepted=false;
      try{accepted=wake_callback();}
      catch(...){if(waking_on_owner){std::lock_guard lock(thread->mutex);thread->owner_wake_active=false;}Quit(thread,false);throw;}
      if(waking_on_owner){std::lock_guard lock(thread->mutex);thread->owner_wake_active=false;}
      if(!accepted){Quit(thread,false);return false;}
    }
    thread->ready.notify_all();Observe("enqueueMessage",thread);return true;
  }
  addr_t GetInstance(){
    Require();auto thread=Current();if(!thread){host.ThrowException("java/lang/IllegalStateException",u"Choreographer requires a prepared Looper");return 0;}
    Value current;
    {std::lock_guard lock(thread->mutex);if(thread->choreographer_created)current=thread->choreographer;}
    if(auto local=host.LocalValue(current))return local;
    const auto result=host.NewHostInstance(kChoreographer,std::make_shared<Choreographer>(Choreographer{this,thread}));
    auto retained=host.CaptureValue(result);
    {std::lock_guard lock(thread->mutex);thread->choreographer=std::move(retained);thread->choreographer_created=true;}
    return result;
  }
  void Post(addr_t receiver,addr_t callback){
    Require();auto thread=Target(Payload<Choreographer>(receiver)->thread);
    if(!callback){host.ThrowException("java/lang/IllegalArgumentException",u"callback must not be null");return;}
    Type(callback,kFrameCallback);if(!host.PendingException().empty())return;
    if(thread->external)throw std::runtime_error("frame deadlines on an externally-owned Android Looper are not implemented");
    const auto clock=Clock(thread);auto request=std::make_shared<Frame>();request->callback=host.CaptureValue(callback);
    {std::lock_guard lock(thread->mutex);if(thread->quitting||thread->done)return;
      if(thread->next_frame_ns<=clock.monotonic_ns)thread->next_frame_ns=Next(clock.monotonic_ns,Period(clock));
      request->due_ns=thread->next_frame_ns;thread->frames.push_back(request);}
    thread->ready.notify_all();Observe("postFrameCallback",thread);
  }
  void Remove(addr_t receiver,addr_t callback){
    Require();auto thread=Target(Payload<Choreographer>(receiver)->thread);
    if(!callback){host.ThrowException("java/lang/IllegalArgumentException",u"callback must not be null");return;}
    Type(callback,kFrameCallback);if(!host.PendingException().empty())return;
    std::vector<std::shared_ptr<Frame>> snapshot;
    {std::lock_guard lock(thread->mutex);snapshot=thread->frames;}
    for(auto& request:snapshot){const auto local=host.LocalValue(request->callback);const bool same=Env(host,24,local,callback)!=0;host.DeleteLocalReference(local);Healthy(host);if(same)request->cancelled.store(true,std::memory_order_release);}
    std::vector<std::shared_ptr<Frame>> retired;
    {std::lock_guard lock(thread->mutex);
      for(auto it=thread->frames.begin();it!=thread->frames.end();){
        if((*it)->cancelled.load(std::memory_order_acquire)){retired.push_back(*it);it=thread->frames.erase(it);}
        else ++it;
      }}
    // Snapshot/retired references release outside the queue lock, before this
    // call returns. A removed pending request cannot keep its action alive
    // until the owner next happens to wake. Already-dispatched actions differ.
    thread->ready.notify_all();Observe("removeFrameCallback",thread);
  }
  void Stop(){
    std::vector<std::shared_ptr<Thread>> snapshot;
    // Stop new workers and cancel queued work, but retain service methods for
    // an already-admitted native callback until it has actually returned.
    {std::lock_guard lock(mutex);snapshot=threads;
      for(const auto& thread:snapshot){std::lock_guard thread_lock(thread->mutex);
        if(thread->external&&!thread->done)throw std::logic_error("external Android Looper must be released before service Stop");}
      stopping=true;}
    for(const auto& thread:snapshot)Quit(thread,false);
    for(const auto& thread:snapshot)JoinThread(thread);
    {std::lock_guard lock(mutex);active=false;}
    Check();
  }
  void PrepareExternal(const std::u16string& name,std::function<bool()> wake){
    Require();if(!wake)throw std::invalid_argument("external Android Looper needs an asynchronous owner wakeup");
    if(!host.EnvAddress()||!host.PendingException().empty())throw std::logic_error("external Looper preparation requires the actual attached healthy owner");
    if(Current())throw std::logic_error("actual Android Looper thread is already prepared");
    auto thread=std::make_shared<Thread>(this,name);thread->external=true;thread->started=true;thread->prepared=true;
    thread->worker_id=std::this_thread::get_id();thread->wake_owner=std::move(wake);
    {LocalFrame frame(host);const auto looper=host.NewHostInstance(kLooper,std::make_shared<Looper>(Looper{this,thread}));thread->looper=host.CaptureValue(looper);}
    {std::lock_guard lock(mutex);if(stopping||!active)throw std::logic_error("Android queue service is stopping");
      threads.push_back(thread);prepared[std::this_thread::get_id()]=thread;}
    Observe("preparedExternal",thread);
  }
  void PumpExternal(){
    auto thread=Current();
    if(!thread||!thread->external)throw std::logic_error("Android owner pump requires its actual prepared external thread");
    {std::lock_guard lock(thread->mutex);
      thread->pump_queued=false;
      if(thread->quitting||thread->done)return;
      if(thread->owner_wake_active)throw std::logic_error("Android owner wakeup must enqueue Pump asynchronously");
      if(thread->pumping)throw std::logic_error("external Android owner pump cannot run synchronously or recursively");
      thread->pumping=true;}
    try{
      for(;;){Value message;
        {std::lock_guard lock(thread->mutex);if(thread->quitting||thread->messages.empty())break;
          message=std::move(thread->messages.front());thread->messages.pop_front();}
        Dispatch(thread,message);
      }
    }catch(...){
      const auto error=std::current_exception();Quit(thread,false);
      {std::lock_guard lock(thread->mutex);thread->pumping=false;}
      thread->ready.notify_all();Failed(error);std::rethrow_exception(error);
    }
    {std::lock_guard lock(thread->mutex);thread->pumping=false;}
    thread->ready.notify_all();
  }
  void ReleaseExternal(){
    auto thread=Current();
    if(!thread||!thread->external)throw std::logic_error("external Android Looper release requires its actual owner");
    {std::lock_guard lock(thread->mutex);if(thread->pumping)throw std::logic_error("cannot release an external Android Looper inside its callback");}
    Quit(thread,false);
    {std::lock_guard lock(mutex);prepared.erase(std::this_thread::get_id());}
    {std::lock_guard lock(thread->mutex);thread->prepared=false;thread->done=true;thread->wake_owner={};}
    thread->ready.notify_all();Observe("releasedExternal",thread);
  }
};

AndroidChoreographer::AndroidChoreographer(jni::Host& host,Config config){
  if(!config.prepare_worker||!config.enter_worker||!config.exit_worker||!config.read_frame_clock)throw std::invalid_argument("Android queues require real creator/worker hooks and an observed frame clock");
  if(!host.EnvAddress()||!host.PendingException().empty())throw std::invalid_argument("Android queue setup requires attached healthy JNI context");
  auto s=std::make_shared<Shared>(host,std::move(config));std::weak_ptr<Shared> weak=s;
  auto get=[weak]{auto value=weak.lock();if(!value)throw std::runtime_error("Android queue service owner expired");value->Require();return value;};
  host.DefineClass("java/lang/IllegalThreadStateException",{},"java/lang/IllegalArgumentException",true);
  host.DefineClass(kThread,{},"java/lang/Object",true);
  host.DefineClass(kHandlerThread,{},kThread,true);
  host.DefineClass(kLooper,{},"java/lang/Object",true);
  host.DefineInterface(kHandlerCallback,{{"handleMessage","(Landroid/os/Message;)Z"}});
  host.DefineInterface(kFrameCallback,{{"doFrame","(J)V"}});
  host.DefineClass(kHandler,{},"java/lang/Object",true);
  host.DefineClass(kMessage,{},"java/lang/Object",true);host.DefineField(kMessage,"what","I");
  host.DefineClass(kChoreographer,{},"java/lang/Object",true);
  host.DefineConstructor(kHandlerThread,"(Ljava/lang/String;)V",[get](const auto& a){Environment native;return get()->NewThread(a[0]);});
  host.DefineVoidMethod(kThread,"start","()V",[get](addr_t r,const auto&){Environment native;get()->Start(r);});
  host.DefineBooleanMethod(kThread,"isAlive","()Z",[get](addr_t r,const auto&){Environment native;return get()->Alive(r);});
  host.DefineVoidMethod(kThread,"join","()V",[get](addr_t r,const auto&){Environment native;get()->Join(r);});
  host.DefineObjectMethod(kHandlerThread,"getLooper","()Landroid/os/Looper;",[get](addr_t r,const auto&){Environment native;return get()->GetLooper(r);});
  host.DefineConstructor(kHandler,"(Landroid/os/Looper;Landroid/os/Handler$Callback;)V",[get](const auto& a){Environment native;return get()->NewHandler(a[0],a[1]);});
  host.DefineConstructor(kHandler,"()V",[get](const auto&){Environment native;return get()->NewHandler(0,0,true);});
  host.DefineObjectMethod(kHandler,"obtainMessage","(I)Landroid/os/Message;",[get](addr_t r,const auto& a){Environment native;return get()->Obtain(r,static_cast<int32_t>(a[0]));});
  host.DefineObjectMethod(kHandler,"getLooper","()Landroid/os/Looper;",[get](addr_t r,const auto&){Environment native;return get()->HandlerLooper(r);});
  host.DefineVoidMethod(kMessage,"sendToTarget","()V",[get](addr_t r,const auto&){Environment native;get()->Send(r);});
  host.DefineObjectMethod(kMessage,"getTarget","()Landroid/os/Handler;",[get](addr_t r,const auto&){Environment native;return get()->MessageTarget(r);});
  host.DefineStaticObjectMethod(kLooper,"myLooper","()Landroid/os/Looper;",[get](addr_t,const auto&)->addr_t{Environment native;auto s=get();auto thread=s->Current();if(!thread)return 0;Value value;{std::lock_guard lock(thread->mutex);value=thread->looper;}return s->host.LocalValue(value);});
  host.DefineVoidMethod(kLooper,"quit","()V",[get](addr_t r,const auto&){Environment native;auto s=get();s->Quit(s->Target(s->Payload<Looper>(r)->thread),false);});
  host.DefineStaticObjectMethod(kChoreographer,"getInstance","()Landroid/view/Choreographer;",[get](addr_t,const auto&){Environment native;return get()->GetInstance();});
  host.DefineVoidMethod(kChoreographer,"postFrameCallback","(Landroid/view/Choreographer$FrameCallback;)V",[get](addr_t r,const auto& a){Environment native;get()->Post(r,a[0]);});
  host.DefineVoidMethod(kChoreographer,"removeFrameCallback","(Landroid/view/Choreographer$FrameCallback;)V",[get](addr_t r,const auto& a){Environment native;get()->Remove(r,a[0]);});
  state_=std::move(s);
}
AndroidChoreographer::~AndroidChoreographer(){if(state_)try{state_->Stop();}catch(...){/* Explicit Stop/CheckHealthy reports failure; all workers were joined. */}}
void AndroidChoreographer::CheckHealthy()const{state_->Check();}
void AndroidChoreographer::PrepareCurrentLooper(const std::u16string& name,std::function<bool()> wake_owner){Environment native;state_->PrepareExternal(name,std::move(wake_owner));}
void AndroidChoreographer::PumpCurrentLooper(){Environment native;state_->PumpExternal();}
void AndroidChoreographer::ReleaseCurrentLooper(){Environment native;state_->ReleaseExternal();}
void AndroidChoreographer::Stop(){state_->Stop();}
}  // namespace bunker::windows

#pragma once
#include "jni_host.h"
#include <deque>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace bunker::windows {
// The audited UnityPlayer.hideSoftInput null-dialog path. UI posting is always
// deferred; its two f jobs use the original native-loaded/finishing gates and
// are drained at Java NEXT_FRAME's executeGLThreadJobs point. This supplies no
// general Handler, dialog, keyboard, or Android thread implementation.
class UnitySoftInputSession {
 public:
  using Runner=std::function<uint64_t(addr_t,const std::vector<addr_t>&)>;
  UnitySoftInputSession(jni::Host& host,addr_t player,Runner run)
      : state_(std::make_shared<Shared>(host,player,std::move(run))) {
    host.DefineField(kPlayer,"mSoftInputDialog",kDialog);
    // A newly supplied instance field has Java's null default. Never overwrite
    // an existing dialog: a second field/session definition is rejected.
    {Local dialog(host,host.GetObjectFieldValue(player,"mSoftInputDialog",kDialog));
      RequireNoException(host,"initial dialog field");
      if(dialog.value)throw std::runtime_error("soft input: initial dialog is not null");}
    host.BindVoidMethod(kPlayer,"hideSoftInput","()V",
      [s=state_](addr_t receiver,const jni::Host::MethodArguments&) {
        RequireNoException(s->host,"hideSoftInput entry");
        Local owner(s->host,s->host.LocalValue(s->player));
        State call{};call.gpr.x0.qword=s->host.EnvAddress();
        call.gpr.x1.qword=receiver;call.gpr.x2.qword=owner.value;
        s->host.InvokeEnv(24,call);
        RequireNoException(s->host,"receiver identity");
        if(!call.gpr.x0.qword)throw std::runtime_error("soft input: unowned UnityPlayer");
        // postOnUiThread always Handler.post, even for the current UI thread.
        std::lock_guard lock(s->mutex);s->ui_jobs.push_back(0);
      });
  }
  UnitySoftInputSession(const UnitySoftInputSession&)=delete;
  UnitySoftInputSession& operator=(const UnitySoftInputSession&)=delete;
  void SetNativeLoaded(bool value) { std::lock_guard lock(state_->mutex);state_->native_loaded=value; }
  // isFinishing returns true immediately once mQuitting has become true.
  void SetFinishing(bool value) { std::lock_guard lock(state_->mutex);state_->finishing=state_->finishing||value; }
  void SetUnityMainCurrent() {
    std::lock_guard lock(state_->mutex);
    const auto current=std::this_thread::get_id();
    if(state_->main!=std::thread::id{}&&state_->main!=current)
      throw std::runtime_error("soft input: UnityMain owner changed");
    state_->main=current;
  }
  void DrainUiJobs() {
    if(std::this_thread::get_id()!=state_->ui)throw std::runtime_error("soft input: foreign UI pump");
    RequireNoException(state_->host,"UI pump entry");
    for(;;) {
      {std::lock_guard lock(state_->mutex);if(state_->ui_jobs.empty())return;state_->ui_jobs.pop_front();}
      Report(Job::Area);Report(Job::Visible);
      Local player(state_->host,state_->host.LocalValue(state_->player));
      Local dialog(state_->host,state_->host.GetObjectFieldValue(player.value,"mSoftInputDialog",kDialog));
      RequireNoException(state_->host,"dialog field");
      if(dialog.value)throw std::runtime_error("soft input: original dialog dismissal/configuration is not implemented");
    }
  }
  void DrainGlThreadJobs() {
    {std::lock_guard lock(state_->mutex);if(state_->main!=std::this_thread::get_id())
      throw std::runtime_error("soft input: foreign GL job pump");}
    for(;;) {
      Job job;
      {std::lock_guard lock(state_->mutex);if(state_->gl_jobs.empty())return;job=state_->gl_jobs.front();state_->gl_jobs.pop_front();}
      Execute(job);
    }
  }
  // Audit only at a genuinely quiescent shutdown. Never flush on the wrong
  // thread or discard a queued original report to make teardown look idle.
  void CheckIdle() const {
    std::lock_guard lock(state_->mutex);
    if(!state_->ui_jobs.empty()||!state_->gl_jobs.empty())throw std::runtime_error("soft input: undrained jobs");
  }
 private:
  static constexpr const char* kPlayer="com/unity3d/player/UnityPlayer";
  static constexpr const char* kDialog="Lcom/unity3d/player/l;";
  enum class Job { Area,Visible };
  static void RequireNoException(jni::Host& host,const char* operation) {
    if(!host.PendingException().empty())throw std::runtime_error(std::string("soft input: pending Java exception at ")+operation);
  }
  struct Local {
    jni::Host& host;addr_t value;
    Local(jni::Host& h,addr_t v):host(h),value(v){}
    ~Local(){host.DeleteLocalReference(value);}
  };
  struct Shared {
    jni::Host& host;jni::Host::ObjectValue player;Runner run;
    const std::thread::id ui=std::this_thread::get_id();std::thread::id main;
    std::mutex mutex;bool native_loaded=false,finishing=false;
    std::deque<int> ui_jobs;std::deque<Job> gl_jobs;
    Shared(jni::Host& h,addr_t p,Runner r):host(h),run(std::move(r)) {
      if(!run)throw std::invalid_argument("soft input: missing original native runner");
      RequireNoException(h,"session construction");
      if(!p)throw std::invalid_argument("soft input: null UnityPlayer");
      State call{};call.gpr.x0.qword=h.EnvAddress();call.gpr.x1.qword=p;
      h.InvokeEnv(31,call);
      Local owner(h,call.gpr.x0.qword);
      RequireNoException(h,"player class");
      const auto type=h.ClassNameValue(owner.value);
      RequireNoException(h,"player validation");
      if(!type||*type!=kPlayer)throw std::invalid_argument("soft input: expected live UnityPlayer instance");
      player=h.CaptureValue(p);
      RequireNoException(h,"player retention");
    }
  };
  void Report(Job job) {
    bool inline_main;
    {std::lock_guard lock(state_->mutex);
      if(state_->finishing||!state_->native_loaded)return;
      inline_main=state_->main==std::this_thread::get_id();
      if(!inline_main)state_->gl_jobs.push_back(job);
    }
    if(inline_main)Execute(job);
  }
  void Execute(Job job) {
    {std::lock_guard lock(state_->mutex);if(state_->finishing)return;}
    RequireNoException(state_->host,"native report entry");
    const char* name=job==Job::Area?"nativeSetInputArea":"nativeSetKeyboardIsVisible";
    const char* sig=job==Job::Area?"(IIII)V":"(Z)V";
    const auto entry=state_->host.NativeEntry(kPlayer,name,sig);
    if(!entry)throw std::runtime_error(std::string("soft input: original native not registered: ")+name);
    Local player(state_->host,state_->host.LocalValue(state_->player));
    RequireNoException(state_->host,"native report player");
    std::vector<addr_t> args={state_->host.EnvAddress(),player.value,0};
    if(job==Job::Area)args.insert(args.end(),3,0);
    state_->run(entry,args);
    if(!state_->host.PendingException().empty())throw std::runtime_error("soft input: native report left Java exception");
  }
  std::shared_ptr<Shared> state_;
};
}

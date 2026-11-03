#include <cfenv>
#include "android_process.h"
#include <cerrno>
#include <cstring>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#endif
namespace bunker::windows {
namespace {
struct ObserveEnvironment {
 int error=errno;fenv_t fp{};
#ifdef _WIN32
 DWORD last_error=GetLastError();
#endif
 ObserveEnvironment(){std::fegetenv(&fp);}
 ~ObserveEnvironment(){std::fesetenv(&fp);errno=error;
#ifdef _WIN32
  SetLastError(last_error);
#endif
 }
};
}
struct AndroidProcess::State {
 jni::Host &host;std::function<int(uint32_t,int32_t)> setter;Observer observer;
 State(jni::Host&h,ThreadPriorities&p,Observer o):host(h),setter(p.Setter()),observer(std::move(o)){}
 void Observe(Observation::Phase phase,uint32_t who,int32_t nice,int error){if(observer){ObserveEnvironment preserve;observer({phase,who,nice,error});}}
 void Set(uint32_t who,int32_t nice){
  Observe(Observation::Phase::Enter,who,nice,0);
  const int error=setter(who,nice);
  Observe(Observation::Phase::Return,who,nice,error);
  if(!error)return;
  const char *type=error==22||error==3?"java/lang/IllegalArgumentException":error==1||error==13?"java/lang/SecurityException":"java/lang/RuntimeException";
  int32_t tid;std::memcpy(&tid,&who,sizeof(tid));
  const auto id=std::to_string(tid);
  const auto message=error==22?"Invalid argument: "+id:error==3?"Given thread "+id+" does not exist":error==1?"No permission to modify given thread "+id:error==13?"No permission to set the priority of "+id:std::string("Unknown error");
  host.ThrowException(type,std::u16string(message.begin(),message.end()));
 }
};
AndroidProcess::AndroidProcess(jni::Host&host,ThreadPriorities&priorities,Observer observer){
 state_=std::make_shared<State>(host,priorities,std::move(observer));std::weak_ptr<State> weak=state_;
 host.DefineClass("android/os/Process",{{"setThreadPriority","(II)V",true,true}},"java/lang/Object",true);
 host.BindPlatformNativeStaticVoidMethod("android/os/Process","setThreadPriority","(II)V",[weak](addr_t,const jni::Host::MethodArguments&args){
  auto state=weak.lock();if(!state)throw std::runtime_error("Android Process adapter owner expired");
  uint32_t tid=static_cast<uint32_t>(args[0]),raw=static_cast<uint32_t>(args[1]);int32_t nice;std::memcpy(&nice,&raw,sizeof(nice));state->Set(tid,nice);
 });
}
AndroidProcess::~AndroidProcess()=default;
}

#include <cfenv>
#include "thread_priority.h"
#include "../whole/bridge.h"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <stdexcept>
#include <windows.h>
namespace bunker::windows {
namespace {
struct Environment {
 int error=errno;DWORD last_error=GetLastError();fenv_t fp{};
 Environment(){std::fegetenv(&fp);}
 ~Environment(){std::fesetenv(&fp);errno=error;SetLastError(last_error);}
};
int Error(DWORD error){
 switch(error){case ERROR_ACCESS_DENIED:return 13;case ERROR_INVALID_HANDLE:return 3;case ERROR_INVALID_PARAMETER:return 22;}
 throw std::runtime_error("unsupported native thread priority error: "+std::to_string(error));
}
int Native(int32_t nice){
 switch(nice){case 10:return THREAD_PRIORITY_LOWEST;case 1:return THREAD_PRIORITY_BELOW_NORMAL;case 0:return THREAD_PRIORITY_NORMAL;case -2:return THREAD_PRIORITY_ABOVE_NORMAL;}
 throw std::runtime_error("unsupported nice outside explicit Unity4 Windows priority profile");
}
int32_t Nice(int native){
 switch(native){case THREAD_PRIORITY_LOWEST:return 10;case THREAD_PRIORITY_BELOW_NORMAL:return 1;case THREAD_PRIORITY_NORMAL:return 0;case THREAD_PRIORITY_ABOVE_NORMAL:return -2;}
 throw std::runtime_error("unsupported native thread level outside explicit Unity4 priority profile");
}
}
struct ThreadPriorities::State {
 Pthreads &threads;addr_t marker;bool installed=false;std::mutex mutex;std::function<void(int)> error_sink;
 State(Pthreads&t,addr_t m):threads(t),marker(m){}
 int Fail(int error){if(!error_sink)throw std::logic_error("thread priority needs guest errno sink");error_sink(error);return error;}
 int Query(const Pthreads::NativeThreadLease &lease,int32_t &nice){
  const auto process_class=GetPriorityClass(GetCurrentProcess());
  if(!process_class)return Error(GetLastError());
  if(process_class!=NORMAL_PRIORITY_CLASS)throw std::runtime_error("unsupported non-NORMAL process class for Unity4 priority profile");
  const int value=::GetThreadPriority(reinterpret_cast<HANDLE>(lease.NativeHandleBits()));
  if(value==THREAD_PRIORITY_ERROR_RETURN)return Error(GetLastError());
  nice=Nice(value);return 0;
 }
 int32_t Get(int32_t which,uint32_t who){
  Environment preserve;
  if(which<0||which>2){Fail(22);return -1;}
  if(which)throw std::runtime_error("unsupported getpriority group/user namespace");
  auto lease=threads.AcquireNativeThread(who);if(!lease){Fail(3);return -1;}
  int32_t nice=0;int error=0;{std::lock_guard lock(mutex);error=Query(lease,nice);}
  if(error){Fail(error);return -1;}return nice;
 }
 int Set(uint32_t who,int32_t nice){
  Environment preserve;const int desired=Native(nice);
  // Require an error sink before any real mutation; changed success clears
  // guest errno as in Android13 androidSetThreadPriority, not C setpriority.
  if(!error_sink)throw std::logic_error("JNI thread priority needs guest errno sink");
  auto lease=threads.AcquireNativeThread(who);if(!lease)return Fail(3);
  int error=0;bool changed=false;
  {
   std::lock_guard lock(mutex);int32_t old=0;error=Query(lease,old);
   if(!error&&old!=nice){
    if(!::SetThreadPriority(reinterpret_cast<HANDLE>(lease.NativeHandleBits()),desired))error=Error(GetLastError());
    else {int32_t actual=0;error=Query(lease,actual);if(!error&&actual!=nice)throw std::runtime_error("native priority readback differs from requested Unity4 level");changed=!error;}
   }
  }
  if(error)return Fail(error);
  if(changed)error_sink(0);
  return 0;
 }
};
ThreadPriorities::ThreadPriorities(Pthreads&t,Profile p,addr_t marker){
 if(p!=Profile::UnityNormalClass||marker%8)throw std::invalid_argument("priority needs explicit UnityNormalClass/aligned marker");
 state_=std::make_shared<State>(t,marker);
}
ThreadPriorities::~ThreadPriorities()=default;
void ThreadPriorities::SetErrorSink(std::function<void(int)> sink){state_->error_sink=std::move(sink);}
int32_t ThreadPriorities::GetPriority(int32_t which,uint32_t who){return state_->Get(which,who);}
int ThreadPriorities::SetThreadPriority(uint32_t who,int32_t nice){return state_->Set(who,nice);}
std::function<int(uint32_t,int32_t)> ThreadPriorities::Setter()const{
 std::weak_ptr<State> weak=state_;return [weak](uint32_t who,int32_t nice){auto state=weak.lock();if(!state)throw std::runtime_error("priority provider owner expired");return state->Set(who,nice);};
}
addr_t ThreadPriorities::Marker(const std::string&name)const{if(name!="getpriority")throw std::invalid_argument("unsupported priority import "+name);return state_->marker;}
void ThreadPriorities::Install(recomp::Runtime&runtime){
 if(state_->installed)throw std::logic_error("thread priorities installed twice");
 std::weak_ptr<State> weak=state_;
 auto bridge=recomp::MakeBridge<int32_t(int32_t,uint32_t)>([weak](auto which,auto who){auto state=weak.lock();if(!state)throw std::runtime_error("priority provider owner expired");return state->Get(which,who);});
 runtime.AddImport(state_->marker,[bridge=std::move(bridge)](::State&s){try{bridge(s);}catch(const std::exception&e){std::fprintf(stderr,"thread priority getpriority: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fprintf(stderr,"thread priority getpriority: unknown native exception\n");std::fflush(stderr);std::abort();}});
 state_->installed=true;
}
}

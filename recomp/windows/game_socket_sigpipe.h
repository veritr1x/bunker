#pragma once
// Included after SignalHost and the native runtime/environment declarations.
// Windows has no POSIX wait status: 141 is this adapter's explicit default
// SIGPIPE termination status. Custom handlers need a separate delivery gate.
class GameSocketSigpipe {
 public:
  static void Notify(bunker::windows::SignalHost &signals,uint64_t token,State *state){
    struct NativeEnvironment {
      int error=errno;DWORD last=GetLastError();fenv_t environment{};
      NativeEnvironment(){std::fegetenv(&environment);}
      ~NativeEnvironment(){std::fesetenv(&environment);errno=error;SetLastError(last);}
    } native;
    if(!state||state!=recomp::CurrentExecutionState())
      throw std::runtime_error("SIGPIPE has no active original import State");
    bunker::windows::AndroidSignalAction action{};
    if(signals.Action(13,nullptr,&action))
      throw std::runtime_error("cannot query the original SIGPIPE disposition");
    if(action.handler==1)return;
    if(action.handler==0){
      uint64_t mask=0;
      if(signals.Mask(token,0,nullptr,&mask))
        throw std::runtime_error("SIGPIPE has no bound original thread mask");
      if(mask&bunker::windows::SignalHost::Bit(13))
        throw std::runtime_error("blocked default SIGPIPE is outside the qualified pending-delivery profile");
      std::fprintf(stderr,"Game socket SIGPIPE: actual broken-pipe operation with guest SIG_DFL token=%#llx native_tid=%lu LR=%#llx; terminating with adapter status 141\n",(unsigned long long)token,GetCurrentThreadId(),(unsigned long long)state->gpr.x30.qword);
      std::fflush(stderr);std::_Exit(141);
    }
    throw std::runtime_error("custom guest SIGPIPE handler is outside the qualified native delivery profile");
  }
};

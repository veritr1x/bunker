#pragma once
#include "signal_host.h"
namespace bunker::windows {
// Android LP64 relative nanosleep. Signal delivery requires the owner's exact
// admission policy; this does not add a collector checkpoint or provider roots.
class SignalNanoSleeps {
 public:
  using Admission=std::function<uint64_t(uint64_t)>;
  struct Observation {
    addr_t request=0,remaining=0;bool copied=false;
    int64_t seconds=0,nanoseconds=0;
  };
  using RequestObserver=std::function<void(const Observation&)>;
  SignalNanoSleeps(SignalHost&,SignalHost::Current,SignalHost::Boundary,Admission,
                   addr_t marker_base=0x7ff600300008ULL);
  void SetErrorSink(std::function<void(int)> sink){error_sink_=std::move(sink);}
  // Configure while callers are quiescent. One immutable request observation,
  // outside memory/signal locks, before validation/wait; never reread pointers.
  void SetRequestObserver(RequestObserver observer){observer_=std::move(observer);}
  int32_t NanoSleep(addr_t request,addr_t remaining);
  addr_t Marker(const std::string&)const;
  void Install(recomp::Runtime&);
 private:
  SignalHost &signals_;SignalHost::Current current_;SignalHost::Boundary boundary_;
  Admission admission_;RequestObserver observer_;std::function<void(int)> error_sink_;
  addr_t marker_base_;bool installed_=false;
};
}

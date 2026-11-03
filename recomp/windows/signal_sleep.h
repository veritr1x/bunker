#pragma once
#include "signal_host.h"
namespace bunker::windows {
// Optional, explicitly admitted sleep boundary. Does not qualify a Runtime
// phase's roots or expand any collector/native-provider safepoint policy.
class SignalSleeps {
 public:
  // Called outside provider locks; read-only, no guest execution or queue/mask
  // changes. All eligible pending bits must be admitted before any is consumed.
  using Admission=std::function<uint64_t(uint64_t)>;
  SignalSleeps(SignalHost&,SignalHost::Current,SignalHost::Boundary,Admission,
               addr_t marker_base=0x7ff600300000ULL);
  void SetErrorSink(std::function<void(int)> sink){error_sink_=std::move(sink);}
  int32_t USleep(uint32_t microseconds);
  addr_t Marker(const std::string&)const;
  void Install(recomp::Runtime&);
 private:
  SignalHost &signals_;SignalHost::Current current_;SignalHost::Boundary boundary_;
  Admission admission_;std::function<void(int)> error_sink_;addr_t marker_base_;
  bool installed_=false;
};
}

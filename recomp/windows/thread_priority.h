#pragma once
#include "pthread_host.h"
namespace bunker::windows {
// Explicit Windows relative-priority translation, not Linux CFS equivalence.
// Actual NORMAL process class is required; no process-class/boost mutation.
// Pthreads must outlive this provider and every active operation. A lease
// retains the acquired native object across exit/TID reuse; it is not a claim
// that the thread remains alive throughout a subsequent native query/set.
class ThreadPriorities {
 public:
  enum class Profile { UnityNormalClass };
  ThreadPriorities(Pthreads&,Profile,addr_t marker_base=0x7ff600500000ULL);
  ~ThreadPriorities();
  ThreadPriorities(const ThreadPriorities&)=delete;
  ThreadPriorities&operator=(const ThreadPriorities&)=delete;
  void SetErrorSink(std::function<void(int)>);
  int32_t GetPriority(int32_t which,uint32_t who);
  // JNI androidSetThreadPriority convention: 0 or positive Android errno.
  // Equal native priority preserves guest errno; changed success clears it.
  int SetThreadPriority(uint32_t who,int32_t nice);
  std::function<int(uint32_t,int32_t)> Setter() const;
  addr_t Marker(const std::string&)const;
  void Install(recomp::Runtime&);
 private:
  struct State;
  std::shared_ptr<State> state_;
};
}

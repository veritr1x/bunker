#pragma once
#include "pthread_host.h"
namespace bunker::windows {
// Explicit native Windows CPU-index profile, not an emulated Android device.
// Pthreads must outlive this provider and all active calls. Configure the errno
// sink before publication; all calls must quiesce before provider destruction.
class ThreadAffinities {
 public:
  enum class Profile { WindowsSingleGroupNativeIndices };
  struct Observation {
    enum class Phase { MaskCopied,Return } phase=Phase::MaskCopied;
    int32_t pid=0;uint32_t size=0;addr_t user_mask=0;
    uint32_t requested_mask=0,resolved_tid=0;
    uint64_t process_mask=0,system_mask=0,effective_mask=0,previous_mask=0,readback_mask=0;
    int64_t result=0;int error=0;
    bool mask_copied=false,target_resolved=false,topology_valid=false,native_set_called=false,readback_valid=false;
  };
  // Diagnostics only, outside registry/service/runtime-memory locks. Must
  // return normally without guest execution or provider/scheduling mutations.
  // Each callback alone preserves native errno/fenv/LastError. MaskCopied has
  // no return result; Return.error is the operation error, not guest errno.
  using Observer=std::function<void(const Observation&)>;
  ThreadAffinities(Pthreads&,Profile,addr_t marker_base=0x7ff600600000ULL,Observer={});
  ~ThreadAffinities();
  ThreadAffinities(const ThreadAffinities&)=delete;
  ThreadAffinities&operator=(const ThreadAffinities&)=delete;
  void SetErrorSink(std::function<void(int)>);
  // Only kernel low32 number122 and cpusetsize4. Copy exactly4 unaligned
  // bytes fault-safely before PID resolution. Kernel pid/len decode low32;
  // the three unused syscall argument registers are ignored without reads.
  int64_t Syscall(int64_t number,int32_t pid,uint32_t cpusetsize,addr_t user_mask,
                  addr_t unused4,addr_t unused5,addr_t unused6);
  // Public Bionic getter: exact128B software profile, raw8B kernel word then
  // libc zero-tail. Other valid sizes are unsupported; invalid sizes EINVAL.
  // A tail-only copy fault is a fatal libc boundary, not kernel EFAULT.
  int32_t Get(int32_t pid,uint64_t cpusetsize,addr_t user_mask);
  // Public128 setter copies only the explicit kernel64 word before PID lookup.
  // Remaining120 input bytes are ignored; old raw122/len4 stays separate.
  int32_t Set(int32_t pid,uint64_t cpusetsize,addr_t user_mask);
  addr_t Marker(const std::string&)const;
  void Install(recomp::Runtime&);
 private:
  struct Impl;std::shared_ptr<Impl> impl_;
};
}
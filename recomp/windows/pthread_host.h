#pragma once
#include <cstddef>
#include <cstdint>
#include <functional>
#include <initializer_list>
#include <memory>
#include <string>
#include <vector>
#include "../whole/runtime.h"
#include "android_types.h"

namespace bunker::windows {
// Android AArch64 wire types. Host Windows pthread/CRT layouts never escape.
struct AndroidThreadAttr {
  uint32_t flags = 0, padding = 0;
  uint64_t stack_base = 0, stack_size = 0, guard_size = 0;
  int32_t sched_policy = 0, sched_priority = 0;
  uint8_t reserved[16]{};
};
static_assert(sizeof(AndroidThreadAttr) == 56 && offsetof(AndroidThreadAttr, stack_base) == 8);
static_assert(offsetof(AndroidThreadAttr, sched_policy) == 32 && sizeof(AndroidTimespec) == 16);

// Must outlive its registered imports and workers. All guest callbacks execute
// translated traces via Runtime::Run, with their own State and per-thread stack.
// Invalid guest memory is outside this API's contract, as for native pthreads.
class Pthreads {
 public:
  Pthreads(recomp::Runtime &, std::function<bool(addr_t)> translated_entry,
           addr_t marker_base = 0x7ff900000000ULL);
  ~Pthreads();
  Pthreads(const Pthreads &) = delete;
  Pthreads &operator=(const Pthreads &) = delete;
  void Install();
  void SetErrorSink(std::function<void(int)>);
  addr_t Marker(const std::string &) const;
  uint64_t Run(addr_t entry, std::initializer_list<addr_t> args = {});
  uint64_t Run(addr_t entry, const std::vector<addr_t> &args);
  // For callers that invoke Runtime themselves: register the actual guest stack
  // before imports need pthread_getattr_np. This is not the host native stack.
  void AttachCurrentStack(void *base, uint64_t size);
  // External native threads call this before exiting to run their guest TLS
  // destructors on the correct thread. pthread_create workers do so automatically.
  int ReleaseCurrent();
  uint64_t Self();
  int Create(uint64_t *thread, const AndroidThreadAttr *, addr_t entry, addr_t arg);
  int Join(uint64_t thread, uint64_t *result);
  int Detach(uint64_t thread);
  [[noreturn]] void Exit(uint64_t result);
  int AttrInit(AndroidThreadAttr *);
  int AttrDestroy(AndroidThreadAttr *);
  int AttrSetDetach(AndroidThreadAttr *, int);
  int AttrSetStackSize(AndroidThreadAttr *, uint64_t);
  int AttrGetStack(const AndroidThreadAttr *, uint64_t *base, uint64_t *size);
  int GetAttr(uint64_t thread, AndroidThreadAttr *);
  int MutexAttrInit(int64_t *);
  int MutexAttrDestroy(int64_t *);
  int MutexAttrSetType(int64_t *, int);
  int MutexInit(void *, const int64_t *);
  int MutexDestroy(void *);
  int MutexLock(void *, bool try_only = false);
  int MutexUnlock(void *);
  int CondAttrInit(int64_t *);
  int CondAttrDestroy(int64_t *);
  int CondAttrSetClock(int64_t *, int);
  int CondInit(void *, const int64_t *);
  int CondDestroy(void *);
  int CondWake(void *, bool all);
  int CondWait(void *, void *mutex, const AndroidTimespec *deadline = nullptr);
  int Once(int32_t *, addr_t callback);
  int KeyCreate(int32_t *, addr_t destructor);
  int KeyDelete(int32_t);
  int SetSpecific(int32_t, uint64_t);
  uint64_t GetSpecific(int32_t);
  int RwInit(void *, const int64_t *);
  int RwDestroy(void *);
  int RwLock(void *, bool write);
  int RwUnlock(void *);
  int SetName(uint64_t, const char *);
  int Kill(uint64_t, int signal);
  static int ClockGetTime(int clock, AndroidTimespec *);
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows

#pragma once
#include "filesystem.h"
#include <functional>
#include <memory>
#include <string>

namespace bunker::windows {
class SocketTransport {
 public:
  struct PollFd {int32_t descriptor;int16_t events,revents;};
  struct Timeval {int64_t seconds,microseconds;};
  struct Iovec {addr_t base;uint64_t length;};
  struct Message {addr_t name;uint32_t name_length,pad0;addr_t vectors;uint64_t vector_count;addr_t control;uint64_t control_length;int32_t flags,pad1;};
  static_assert(sizeof(PollFd)==8&&sizeof(Timeval)==16&&sizeof(Iovec)==16&&sizeof(Message)==56);
  struct WaitContext {State *state;int32_t descriptor;bool writing;};
  // A checkpoint observes the actual installed invocation on the waiting
  // worker, outside all descriptor/provider locks. It does not by itself
  // certify a collector wait; bootstrap must supply a separately admitted hook.
  using WaitCheckpoint=std::function<void(const WaitContext&)>;
  enum class WaitOperation { Read,Write,Connect,Accept,Poll,Select,PipeRead,PipeWrite };
  enum class WaitPhase { Copied,BeforeNativeWait,AfterNativeWait,Returned };
  struct WaitObservation {
    State *state;int32_t descriptor;WaitOperation operation;WaitPhase phase;
    const void *request_identity;std::shared_ptr<const void> retained_request;
    bool finite;int64_t deadline_nanoseconds;
  };
  struct WaitDecision {bool handled=false,restart=false;};
  using WaitObserver=std::function<WaitDecision(const WaitObservation&)>;
  explicit SocketTransport(FileSystem &,addr_t marker_base=0x7ffb10000000ULL);
  ~SocketTransport();
  void SetWaitCheckpoint(WaitCheckpoint);
  void SetWaitObserver(WaitObserver);
  void SetBrokenPipeNotification(std::function<void(State*)>);
  addr_t Marker(const std::string&)const;
  void Install(recomp::Runtime&,DescriptorImportInterceptor interceptor={});
  int32_t Socket(int32_t family,int32_t type,int32_t protocol);
  int32_t Connect(int32_t descriptor,addr_t address,uint32_t length);
  int32_t Bind(int32_t descriptor,addr_t address,uint32_t length);
  int32_t Listen(int32_t descriptor,int32_t backlog);
  int32_t Accept(int32_t descriptor,addr_t address,addr_t length);
  int64_t Send(int32_t descriptor,addr_t input,uint64_t length,int32_t flags);
  int64_t Recv(int32_t descriptor,addr_t output,uint64_t length,int32_t flags);
  int64_t SendTo(int32_t descriptor,addr_t input,uint64_t length,int32_t flags,addr_t address,uint32_t address_length);
  int64_t RecvFrom(int32_t descriptor,addr_t output,uint64_t length,int32_t flags,addr_t address,addr_t address_length);
  int32_t Name(int32_t descriptor,addr_t address,addr_t length,bool peer);
  int32_t SetOption(int32_t descriptor,int32_t level,int32_t option,addr_t value,uint32_t length);
  int32_t GetOption(int32_t descriptor,int32_t level,int32_t option,addr_t value,addr_t length);
  int32_t Shutdown(int32_t descriptor,int32_t how);
  int64_t SendMsg(int32_t descriptor,addr_t message,int32_t flags);
  int64_t RecvMsg(int32_t descriptor,addr_t message,int32_t flags);
  int32_t Dup2(int32_t source,int32_t target);
  int32_t Fcntl(int32_t descriptor,int32_t command,addr_t argument);
  int32_t Ioctl(int32_t descriptor,uint64_t request,addr_t argument);
  int32_t Pipe(addr_t output);
  int32_t Poll(addr_t descriptors,uint32_t count,int32_t timeout);
  int32_t Select(int32_t count,addr_t reads,addr_t writes,addr_t excepts,addr_t timeout);
  const char *InetNtop(int32_t family,addr_t input,addr_t output,uint32_t length);
 private:
  struct Impl;
  std::shared_ptr<Impl> impl_;
  addr_t marker_base_;
  bool installed_=false;
};
}  // namespace bunker::windows

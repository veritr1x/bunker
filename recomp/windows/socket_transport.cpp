#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include "socket_transport.h"
#include "provider_memory.h"
#include "libc_uname_detail.h"
#include "../whole/bridge.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <deque>
#include <limits>
#include <thread>
#include <vector>

namespace bunker::windows {
namespace {
namespace pm=provider_memory;
using Environment=libc_detail::uname_detail::NativeEnvironment;
using Clock=std::chrono::steady_clock;
constexpr int kNonblock=0x800,kCloexec=0x80000,kDontwait=0x40,kNoSignal=0x4000;
int32_t ActiveDescriptorNumber(){return ActiveDescriptorState()?static_cast<int32_t>(ActiveDescriptorState()->gpr.x0.dword):-1;}
const char *const names[]={"socket","connect","bind","listen","accept","send","recv","sendto","recvfrom","getsockname","getpeername","setsockopt","getsockopt","shutdown","sendmsg","recvmsg","dup2","fcntl","ioctl","pipe","poll","select","inet_ntop"};
int SocketError(int error,bool connecting=false){
  switch(error){
    case 0:return 0;case WSAEBADF:return 9;case WSAEINTR:return 4;case WSAEACCES:return 13;
    case WSAEFAULT:return 14;case WSAEINVAL:return 22;case WSAEMFILE:return 24;
    case WSAEWOULDBLOCK:return connecting?115:11;case WSAEINPROGRESS:return 115;
    case WSAEALREADY:return 114;case WSAENOTSOCK:return 88;case WSAEDESTADDRREQ:return 89;
    case WSAEMSGSIZE:return 90;case WSAEPROTOTYPE:return 91;case WSAENOPROTOOPT:return 92;
    case WSAEPROTONOSUPPORT:return 93;case WSAESOCKTNOSUPPORT:return 94;case WSAEOPNOTSUPP:return 95;
    case WSAEAFNOSUPPORT:return 97;case WSAEADDRINUSE:return 98;case WSAEADDRNOTAVAIL:return 99;
    case WSAENETDOWN:return 100;case WSAENETUNREACH:return 101;case WSAENETRESET:return 102;
    case WSAECONNABORTED:return 103;case WSAECONNRESET:return 104;case WSAENOBUFS:return 105;
    case WSAEISCONN:return 106;case WSAENOTCONN:return 107;case WSAESHUTDOWN:return 32;
    case WSAETIMEDOUT:return 110;case WSAECONNREFUSED:return 111;case WSAEHOSTUNREACH:return 113;
    default:return 5;
  }
}
struct Native {
  HMODULE module=nullptr;
#define SOCKET_NATIVE(name) decltype(&::name) name##_call=nullptr;
  SOCKET_NATIVE(WSAStartup) SOCKET_NATIVE(WSACleanup) SOCKET_NATIVE(WSAGetLastError)
  SOCKET_NATIVE(socket) SOCKET_NATIVE(closesocket) SOCKET_NATIVE(ioctlsocket)
  SOCKET_NATIVE(connect) SOCKET_NATIVE(bind) SOCKET_NATIVE(listen) SOCKET_NATIVE(accept)
  SOCKET_NATIVE(send) SOCKET_NATIVE(recv) SOCKET_NATIVE(sendto) SOCKET_NATIVE(recvfrom)
  SOCKET_NATIVE(getsockname) SOCKET_NATIVE(getpeername) SOCKET_NATIVE(setsockopt) SOCKET_NATIVE(getsockopt)
  SOCKET_NATIVE(shutdown) SOCKET_NATIVE(WSAPoll) SOCKET_NATIVE(select)
#undef SOCKET_NATIVE
  using Ntop=PCSTR (WSAAPI*)(INT,const VOID*,PSTR,size_t);
  Ntop ntop_call=nullptr;
  template<typename T>void Load(T &target,const char *name){auto raw=GetProcAddress(module,name);static_assert(sizeof(raw)==sizeof(target));std::memcpy(&target,&raw,sizeof(raw));if(!target)throw std::runtime_error(std::string("missing native Winsock API: ")+name);}
  Native(){
    module=LoadLibraryExW(L"ws2_32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!module)throw std::runtime_error("cannot load System32 Winsock");
    try{
#define SOCKET_LOAD(name) Load(name##_call,#name);
      SOCKET_LOAD(WSAStartup) SOCKET_LOAD(WSACleanup) SOCKET_LOAD(WSAGetLastError)
      SOCKET_LOAD(socket) SOCKET_LOAD(closesocket) SOCKET_LOAD(ioctlsocket)
      SOCKET_LOAD(connect) SOCKET_LOAD(bind) SOCKET_LOAD(listen) SOCKET_LOAD(accept)
      SOCKET_LOAD(send) SOCKET_LOAD(recv) SOCKET_LOAD(sendto) SOCKET_LOAD(recvfrom)
      SOCKET_LOAD(getsockname) SOCKET_LOAD(getpeername) SOCKET_LOAD(setsockopt) SOCKET_LOAD(getsockopt)
      SOCKET_LOAD(shutdown) SOCKET_LOAD(WSAPoll) SOCKET_LOAD(select)
#undef SOCKET_LOAD
      Load(ntop_call,"inet_ntop");WSADATA data{};auto error=WSAStartup_call(MAKEWORD(2,2),&data);
      if(error)throw std::runtime_error("Winsock startup failed: "+std::to_string(error));
    }catch(...){FreeLibrary(module);module=nullptr;throw;}
  }
  ~Native(){if(module){WSACleanup_call();FreeLibrary(module);}}
};
struct Address {sockaddr_storage value{};int length=0;};
bool InputAddress(addr_t pointer,uint32_t length,Address &out,int &error){
  if(!pointer){error=14;return false;}if(length<2){error=22;return false;}
  uint16_t family=0;recomp::ReadGuestMemory(&family,pointer,2);
  if(family==0){out.length=2;return true;}
  const uint32_t size=family==2?16:family==10?28:0;
  if(!size){error=97;return false;}if(length<size){error=22;return false;}
  recomp::ReadGuestMemory(&out.value,pointer,size);out.value.ss_family=family==2?AF_INET:AF_INET6;out.length=size;return true;
}
void OutputAddress(const sockaddr_storage &value,int length,addr_t pointer,addr_t length_pointer){
  if(!pointer)return;
  if(!length_pointer)throw std::invalid_argument("socket address output requires socklen pointer");
  const auto capacity=pm::Read(reinterpret_cast<const uint32_t*>(length_pointer));
  const uint16_t family=value.ss_family==AF_INET?2:value.ss_family==AF_INET6?10:0;
  if(!family)throw std::runtime_error("native socket returned non-Internet address");
  const uint32_t size=family==2?16:28;if(length<static_cast<int>(size))throw std::runtime_error("native socket returned short address");
  std::array<unsigned char,28> bytes{};std::memcpy(bytes.data(),&value,size);std::memcpy(bytes.data(),&family,2);
  recomp::WriteGuestMemory(pointer,bytes.data(),std::min(capacity,size));pm::Write(reinterpret_cast<uint32_t*>(length_pointer),size);
}
int NativeOption(int level,int option,int &native_level){
  if(level==1){native_level=SOL_SOCKET;switch(option){
    case 2:return SO_REUSEADDR;case 3:return SO_TYPE;case 4:return SO_ERROR;case 5:return SO_DONTROUTE;
    case 6:return SO_BROADCAST;case 7:return SO_SNDBUF;case 8:return SO_RCVBUF;case 9:return SO_KEEPALIVE;
    case 10:return SO_OOBINLINE;case 13:return SO_LINGER;case 20:return SO_RCVTIMEO;case 21:return SO_SNDTIMEO;
    default:return -1;}}
  if(level==6){native_level=IPPROTO_TCP;switch(option){case 1:return TCP_NODELAY;case 4:return TCP_KEEPIDLE;case 5:return TCP_KEEPINTVL;case 6:return TCP_KEEPCNT;default:return -1;}}
  if(level==0){native_level=IPPROTO_IP;switch(option){case 1:return IP_TOS;case 2:return IP_TTL;default:return -1;}}
  if(level==41){native_level=IPPROTO_IPV6;switch(option){case 26:return IPV6_V6ONLY;default:return -1;}}
  return -1;
}
}  // namespace

struct SocketTransport::Impl : std::enable_shared_from_this<Impl> {
  struct Endpoint {
    std::shared_ptr<Native> native;SOCKET socket=INVALID_SOCKET;
    int family=0,type=0,protocol=0;std::atomic<int> flags{2};
    std::atomic<int64_t> receive_timeout{0},send_timeout{0};
    Endpoint(std::shared_ptr<Native> n,SOCKET s,int f,int t,int p,int fl):native(std::move(n)),socket(s),family(f),type(t),protocol(p),flags(2|(fl&kNonblock)){}
    ~Endpoint(){if(socket!=INVALID_SOCKET)native->closesocket_call(socket);}
  };
  struct Request {
    State *state=ActiveDescriptorState();int32_t descriptor=-1;WaitOperation operation;
    bool finite=false;int64_t deadline_nanoseconds=0;
    std::shared_ptr<Endpoint> endpoint;std::shared_ptr<void> pipe;
    std::vector<unsigned char> bytes;std::vector<PollFd> polls;
    std::vector<Iovec> vectors;
    addr_t input_address=0;uint64_t input_length=0;
    std::vector<std::shared_ptr<GuestDescriptor>> leases;
    explicit Request(WaitOperation op,int fd):descriptor(fd),operation(op){}
  };
  struct Frame {
    Impl &owner;std::shared_ptr<Request> request;
    Frame(Impl &o,std::shared_ptr<Request> r):owner(o),request(std::move(r)){owner.Observe(request,WaitPhase::Copied);}
    ~Frame(){try{owner.Observe(request,WaitPhase::Returned);}catch(...){std::fputs("socket wait Returned observer failed\n",stderr);std::abort();}}
  };
  struct SocketDescriptor : GuestDescriptor {
    std::weak_ptr<Impl> owner;std::shared_ptr<Endpoint> endpoint;
    SocketDescriptor(std::shared_ptr<Impl> o,std::shared_ptr<Endpoint> e,bool clo=false):GuestDescriptor(Kind::Socket,clo),owner(o),endpoint(std::move(e)){}
    int64_t Read(addr_t p,uint64_t n,int &error)override{auto impl=owner.lock();if(!impl){error=9;return -1;}return impl->Receive(endpoint,ActiveDescriptorNumber(),p,n,0,0,0,nullptr,error);}
    int64_t Write(addr_t p,uint64_t n,int &error)override{auto impl=owner.lock();if(!impl){error=9;return -1;}return impl->Transmit(endpoint,ActiveDescriptorNumber(),p,n,0,0,0,error);}
    std::shared_ptr<GuestDescriptor> Duplicate(int &error)override{auto impl=owner.lock();if(!impl){error=9;return {};}return std::make_shared<SocketDescriptor>(impl,endpoint);}
    int StatusFlags()const override{return endpoint->flags.load();}
    uint64_t Identity()const override{return reinterpret_cast<uint64_t>(endpoint.get());}
    int SetStatusFlags(int flags,int &error)override{if(flags&~(3|kNonblock|0x8000)){error=22;return -1;}endpoint->flags.store(2|(flags&kNonblock));return 0;}
    int Ioctl(uint64_t request,addr_t argument,int &error)override{
      if(request==0x5421){auto value=pm::Read(reinterpret_cast<const int32_t*>(argument));const int old=endpoint->flags.load();endpoint->flags.store(value?old|kNonblock:old&~kNonblock);return 0;}
      if(request==0x541b){u_long value=0;if(endpoint->native->ioctlsocket_call(endpoint->socket,FIONREAD,&value)){error=SocketError(endpoint->native->WSAGetLastError_call());return -1;}pm::Write(reinterpret_cast<int32_t*>(argument),static_cast<int32_t>(std::min<u_long>(value,INT32_MAX)));return 0;}
      error=request==0x8915?95:25;return -1;
    }
  };
  struct PipeState {std::mutex mutex;std::condition_variable changed;std::deque<unsigned char> data;size_t readers=1,writers=1;static constexpr size_t capacity=65536;};
  struct PipeEnd {
    std::shared_ptr<PipeState> pipe;bool reading;std::atomic<int> flags;
    PipeEnd(std::shared_ptr<PipeState> p,bool r):pipe(std::move(p)),reading(r),flags(r?0:1){}
    ~PipeEnd(){std::lock_guard lock(pipe->mutex);if(reading)--pipe->readers;else --pipe->writers;pipe->changed.notify_all();}
  };
  struct PipeDescriptor : GuestDescriptor {
    std::weak_ptr<Impl> owner;std::shared_ptr<PipeEnd> end;
    PipeDescriptor(std::shared_ptr<Impl> o,std::shared_ptr<PipeEnd> e,bool clo=false):GuestDescriptor(e->reading?Kind::PipeRead:Kind::PipeWrite,clo),owner(o),end(std::move(e)){}
    int64_t Read(addr_t p,uint64_t n,int &error)override{
      if(!end->reading){error=9;return -1;}if(!n)return 0;if(n>INT64_MAX){error=22;return -1;}if(!p){error=14;return -1;}
      auto impl=owner.lock();if(!impl){error=9;return -1;}auto &pipe=*end->pipe;std::vector<unsigned char> result;
      auto request=std::make_shared<Request>(WaitOperation::PipeRead,ActiveDescriptorNumber());request->pipe=end;Frame frame(*impl,request);
      std::unique_lock lock(pipe.mutex);
      while(pipe.data.empty()&&pipe.writers){if(end->flags.load()&kNonblock){error=11;return -1;}lock.unlock();if(!impl->BeforeWait(request,error))return -1;lock.lock();pipe.changed.wait_for(lock,std::chrono::milliseconds(50));lock.unlock();if(!impl->AfterWait(request,error))return -1;lock.lock();}
      const size_t count=static_cast<size_t>(std::min<uint64_t>(n,pipe.data.size()));result.reserve(count);
      for(size_t i=0;i<count;++i){result.push_back(pipe.data.front());pipe.data.pop_front();}pipe.changed.notify_all();lock.unlock();
      if(count)recomp::WriteGuestMemory(p,result.data(),count);return static_cast<int64_t>(count);
    }
    int64_t Write(addr_t p,uint64_t n,int &error)override{
      if(end->reading){error=9;return -1;}if(!n)return 0;if(n>INT64_MAX){error=22;return -1;}if(!p){error=14;return -1;}
      auto impl=owner.lock();if(!impl){error=9;return -1;}auto &pipe=*end->pipe;
      auto request=std::make_shared<Request>(WaitOperation::PipeWrite,ActiveDescriptorNumber());request->pipe=end;request->input_address=p;request->input_length=n;
      request->bytes=pm::Bytes(reinterpret_cast<const void*>(p),static_cast<size_t>(std::min<uint64_t>(n,PipeState::capacity)));Frame frame(*impl,request);
      uint64_t total=0;size_t chunk_used=0;
      while(total<n){
        std::unique_lock lock(pipe.mutex);const auto needed=n<=4096?static_cast<size_t>(n):size_t{1};
        while(pipe.readers&&PipeState::capacity-pipe.data.size()<needed){
          if(end->flags.load()&kNonblock){error=11;return total?static_cast<int64_t>(total):-1;}
          lock.unlock();if(!impl->BeforeWait(request,error))return total?static_cast<int64_t>(total):-1;
          lock.lock();pipe.changed.wait_for(lock,std::chrono::milliseconds(50));lock.unlock();
          if(!impl->AfterWait(request,error))return total?static_cast<int64_t>(total):-1;lock.lock();
        }
        if(!pipe.readers){lock.unlock();impl->BrokenPipe();error=32;return total?static_cast<int64_t>(total):-1;}
        auto &bytes=request->bytes;const auto count=std::min(bytes.size()-chunk_used,PipeState::capacity-pipe.data.size());
        pipe.data.insert(pipe.data.end(),bytes.begin()+chunk_used,bytes.begin()+chunk_used+count);pipe.changed.notify_all();lock.unlock();
        total+=count;chunk_used+=count;
        if(total==n||(end->flags.load()&kNonblock))return static_cast<int64_t>(total);
        if(chunk_used==bytes.size()){
          bytes=pm::Bytes(reinterpret_cast<const void*>(p+total),static_cast<size_t>(std::min<uint64_t>(n-total,PipeState::capacity)));chunk_used=0;
        }
      }
      return static_cast<int64_t>(total);
    }
    std::shared_ptr<GuestDescriptor> Duplicate(int &error)override{auto impl=owner.lock();if(!impl){error=9;return {};}return std::make_shared<PipeDescriptor>(impl,end);}
    int StatusFlags()const override{return end->flags.load();}
    uint64_t Identity()const override{return reinterpret_cast<uint64_t>(end->pipe.get());}
    int SetStatusFlags(int flags,int &error)override{if(flags&~(3|kNonblock|0x8000)){error=22;return -1;}end->flags.store((end->reading?0:1)|(flags&kNonblock));return 0;}
    int Ioctl(uint64_t request,addr_t argument,int &error)override{
      if(request==0x5421){const auto value=pm::Read(reinterpret_cast<const int32_t*>(argument));auto flags=end->flags.load();end->flags.store(value?flags|kNonblock:flags&~kNonblock);return 0;}
      if(request==0x541b){std::lock_guard lock(end->pipe->mutex);pm::Write(reinterpret_cast<int32_t*>(argument),static_cast<int32_t>(end->pipe->data.size()));return 0;}
      error=25;return -1;
    }
  };
  FileSystem &files;std::shared_ptr<GuestDescriptors> table;std::shared_ptr<Native> native;
  WaitCheckpoint checkpoint;
  WaitObserver observer;std::function<void(State*)> broken_pipe;
  explicit Impl(FileSystem &f):files(f),table(f.DescriptorTable()),native(std::make_shared<Native>()){}
  int Fail(int error){files.SetError(error);return -1;}
  void Checkpoint(int fd,bool writing){if(checkpoint)checkpoint(WaitContext{ActiveDescriptorState(),fd,writing});}
  void BrokenPipe(){if(broken_pipe)broken_pipe(ActiveDescriptorState());}
  WaitDecision Observe(const std::shared_ptr<Request>&request,WaitPhase phase){if(!observer)return {};return observer(WaitObservation{request->state,request->descriptor,request->operation,phase,request.get(),request,request->finite,request->deadline_nanoseconds});}
  bool Decision(const std::shared_ptr<Request>&request,WaitDecision decision,int &error){if(decision.handled&&(!decision.restart||request->operation==WaitOperation::Poll||request->operation==WaitOperation::Select)){error=4;return false;}return true;}
  bool BeforeWait(const std::shared_ptr<Request>&request,int &error){Checkpoint(request->descriptor,request->operation==WaitOperation::Write||request->operation==WaitOperation::Connect||request->operation==WaitOperation::PipeWrite);return Decision(request,Observe(request,WaitPhase::BeforeNativeWait),error);}
  bool AfterWait(const std::shared_ptr<Request>&request,int &error){return Decision(request,Observe(request,WaitPhase::AfterNativeWait),error);}
  void Deadline(const std::shared_ptr<Request>&request,int64_t nanoseconds){if(nanoseconds>0){request->finite=true;request->deadline_nanoseconds=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count()+nanoseconds;}}
  bool Wait(const std::shared_ptr<Endpoint>&endpoint,int fd,bool writing,int &error,const std::shared_ptr<Request>&request){
    (void)fd;for(;;){if(!BeforeWait(request,error))return false;int delay=50;if(request->finite){auto remaining=request->deadline_nanoseconds-std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count();if(remaining<=0){error=request->operation==WaitOperation::Connect?115:11;return false;}delay=static_cast<int>(std::min<int64_t>(50,(remaining+999999)/1000000));}WSAPOLLFD item{endpoint->socket,static_cast<SHORT>(writing?POLLWRNORM:POLLRDNORM),0};
      const int result=native->WSAPoll_call(&item,1,delay);const int saved_error=result<0?native->WSAGetLastError_call():0;
      if(!AfterWait(request,error))return false;if(result>0)return true;
      if(result<0){error=SocketError(saved_error);return false;}}
  }
  std::shared_ptr<Endpoint> Lookup(int fd,int &error){auto entry=table->Lookup(fd);if(!entry){error=9;return {};}auto socket=std::dynamic_pointer_cast<SocketDescriptor>(entry);if(!socket){error=88;return {};}return socket->endpoint;}
  int Publish(SOCKET socket,int family,int type,int protocol,int flags){
    struct Pending {std::shared_ptr<Native> native;SOCKET value;~Pending(){if(value!=INVALID_SOCKET)native->closesocket_call(value);}} pending{native,socket};
    auto endpoint=std::make_shared<Endpoint>(native,socket,family,type,protocol,flags);pending.value=INVALID_SOCKET;
    u_long one=1;if(native->ioctlsocket_call(socket,FIONBIO,&one))return Fail(SocketError(native->WSAGetLastError_call()));
    if(!SetHandleInformation(reinterpret_cast<HANDLE>(socket),HANDLE_FLAG_INHERIT,0))return Fail(5);
    auto result=table->Allocate(std::make_shared<SocketDescriptor>(shared_from_this(),endpoint,bool(flags&kCloexec)));if(result<0)return Fail(24);return result;
  }
  int64_t Transmit(const std::shared_ptr<Endpoint>&endpoint,int fd,addr_t input,uint64_t length,int flags,addr_t address,uint32_t address_length,int &error){
    if(flags&~(kDontwait|kNoSignal|MSG_OOB|MSG_DONTROUTE)){error=95;return -1;}
    if(length>INT64_MAX||(!input&&length)){error=!input?14:22;return -1;}
    if(endpoint->type==2&&length>65535){error=90;return -1;}
    const auto count=static_cast<size_t>(std::min<uint64_t>(length,endpoint->type==2?65535:65536));auto request=std::make_shared<Request>(WaitOperation::Write,fd);request->endpoint=endpoint;request->bytes=pm::Bytes(reinterpret_cast<const void*>(input),count);Deadline(request,endpoint->send_timeout.load());Frame frame(*this,request);auto &bytes=request->bytes;
    Address destination;if(address&&!InputAddress(address,address_length,destination,error))return -1;
    for(;;){const int native_flags=flags&(MSG_OOB|MSG_DONTROUTE);
      const char *data=count?reinterpret_cast<const char*>(bytes.data()):"";
      int result=address?native->sendto_call(endpoint->socket,data,static_cast<int>(count),native_flags,reinterpret_cast<const sockaddr*>(&destination.value),destination.length):native->send_call(endpoint->socket,data,static_cast<int>(count),native_flags);
      if(result>=0)return result;const int code=native->WSAGetLastError_call();
      if(code!=WSAEWOULDBLOCK||(flags&kDontwait)||(endpoint->flags.load()&kNonblock)){error=code==WSAENOTCONN?(endpoint->type==1?32:89):SocketError(code);if(error==32&&!(flags&kNoSignal))BrokenPipe();return -1;}
      if(!Wait(endpoint,fd,true,error,request))return -1;
    }
  }
  int64_t Receive(const std::shared_ptr<Endpoint>&endpoint,int fd,addr_t output,uint64_t length,int flags,addr_t address,addr_t address_length,int *message_flags,int &error,const std::vector<Iovec> *scatter=nullptr){
    if((flags&~(kDontwait|MSG_PEEK|MSG_OOB|0x100|0x20))||((flags&0x100)&&(flags&MSG_PEEK))||(endpoint->type==1&&(flags&0x20))){error=95;return -1;}
    if(length>INT64_MAX||(!output&&length&&!scatter)){error=!output?14:22;return -1;}
    if(address&&!address_length){error=14;return -1;}
    if(endpoint->type==1&&!length)return 0;
    const bool datagram=endpoint->type==2;uint64_t total=0;auto request=std::make_shared<Request>(WaitOperation::Read,fd);request->endpoint=endpoint;request->bytes.resize(datagram?65536:static_cast<size_t>(std::min<uint64_t>(length,65536)));if(scatter)request->vectors=*scatter;Deadline(request,endpoint->receive_timeout.load());Frame frame(*this,request);
    do{
      const auto capacity=static_cast<size_t>(datagram?65536:std::min<uint64_t>(length-total,65536));auto &bytes=request->bytes;bytes.resize(capacity);
      sockaddr_storage source{};int source_length=sizeof(source);
      int result=datagram?native->recvfrom_call(endpoint->socket,reinterpret_cast<char*>(bytes.data()),static_cast<int>(bytes.size()),flags&(MSG_PEEK|MSG_OOB),reinterpret_cast<sockaddr*>(&source),&source_length):native->recv_call(endpoint->socket,reinterpret_cast<char*>(bytes.data()),static_cast<int>(bytes.size()),flags&(MSG_PEEK|MSG_OOB));
      if(result<0){const int code=native->WSAGetLastError_call();if(code==WSAEWOULDBLOCK&&!(flags&kDontwait)&&!(endpoint->flags.load()&kNonblock)){if(!Wait(endpoint,fd,false,error,request))return total?static_cast<int64_t>(total):-1;continue;}error=SocketError(code);return total?static_cast<int64_t>(total):-1;}
      const auto copied=std::min<uint64_t>(static_cast<uint64_t>(result),length-total);
      if(copied){
        if(!scatter)recomp::WriteGuestMemory(output+total,bytes.data(),copied);
        else{uint64_t offset=total;size_t at=0;for(const auto &vector:request->vectors){if(offset>=vector.length){offset-=vector.length;continue;}const auto part=std::min<uint64_t>(copied-at,vector.length-offset);if(part)recomp::WriteGuestMemory(vector.base+offset,bytes.data()+at,static_cast<size_t>(part));at+=static_cast<size_t>(part);offset=0;if(at==copied)break;}if(at!=copied)throw std::logic_error("recvmsg scatter span changed");}
      }total+=copied;
      if(address){if(datagram)OutputAddress(source,source_length,address,address_length);else pm::Write(reinterpret_cast<uint32_t*>(address_length),uint32_t{0});}
      if(datagram){if(static_cast<uint64_t>(result)>copied&&message_flags)*message_flags|=0x20;return (flags&0x20)?result:static_cast<int64_t>(total);}
      if(!result||!(flags&0x100)||(flags&MSG_PEEK))return static_cast<int64_t>(total);
    }while(total<length);
    return static_cast<int64_t>(total);
  }
  int PollItems(std::vector<PollFd> &output,int timeout,WaitOperation operation=WaitOperation::Poll){
    if(timeout<-1)timeout=-1;const auto end=Clock::now()+std::chrono::milliseconds(timeout<0?0:timeout);
    auto request=std::make_shared<Request>(operation,-1);request->finite=timeout>=0;request->deadline_nanoseconds=request->finite?std::chrono::duration_cast<std::chrono::nanoseconds>(end.time_since_epoch()).count():0;request->polls=output;auto &items=request->polls;auto &leases=request->leases;leases.reserve(items.size());
    for(const auto &item:items)leases.push_back(item.descriptor<0?nullptr:table->Lookup(item.descriptor));Frame frame(*this,request);
    for(;;){int ready=0;std::vector<WSAPOLLFD> sockets;std::vector<size_t> indices;
      for(size_t i=0;i<items.size();++i){auto &item=items[i];item.revents=0;if(item.descriptor<0)continue;
        const auto &entry=leases[i];if(!entry){item.revents=0x20;continue;}
        if(entry->kind==GuestDescriptor::Kind::File){item.revents=item.events&static_cast<int16_t>(0x145);continue;}
        if(auto pipe=std::dynamic_pointer_cast<PipeDescriptor>(entry)){
          std::lock_guard lock(pipe->end->pipe->mutex);const auto &state=*pipe->end->pipe;
          if(pipe->end->reading){if(!state.data.empty()||!state.writers)item.revents|=item.events&0x41;if(!state.writers)item.revents|=0x10;}
          else{if(state.data.size()<PipeState::capacity)item.revents|=item.events&0x104;if(!state.readers)item.revents|=8;}
          continue;
        }
        auto socket=std::dynamic_pointer_cast<SocketDescriptor>(entry);SHORT events=0;
        if(item.events&0x41)events|=POLLRDNORM;if(item.events&0x104)events|=POLLWRNORM;
        // Microsoft's WSAPoll rejects POLLPRI. Probe the real exception set
        // separately for guest urgent/band interest rather than casting flags.
        if(item.events&0x82){fd_set exception{};exception.fd_count=1;exception.fd_array[0]=socket->endpoint->socket;timeval zero{};const int urgent=native->select_call(0,nullptr,nullptr,&exception,&zero);if(urgent<0)return Fail(SocketError(native->WSAGetLastError_call()));if(urgent)item.revents|=item.events&0x82;}
        sockets.push_back(WSAPOLLFD{socket->endpoint->socket,events,0});indices.push_back(i);
      }
      if(!sockets.empty()){
        const int result=native->WSAPoll_call(sockets.data(),static_cast<ULONG>(sockets.size()),0);
        if(result<0)return Fail(SocketError(native->WSAGetLastError_call()));
        for(size_t j=0;j<sockets.size();++j){auto &item=items[indices[j]];const auto events=sockets[j].revents;
          if(events&POLLRDNORM)item.revents|=item.events&0x41;if(events&POLLPRI)item.revents|=item.events&0x82;
          if(events&POLLWRNORM)item.revents|=item.events&0x104;if(events&POLLERR)item.revents|=8;if(events&POLLHUP)item.revents|=0x10;if(events&POLLNVAL)item.revents|=0x20;}
      }
      for(const auto &item:items)if(item.revents)++ready;
      if(ready||timeout==0||(timeout>=0&&Clock::now()>=end)){output=items;return ready;}
      int error=0;if(!BeforeWait(request,error))return Fail(error);auto delay=std::chrono::milliseconds(50);
      if(timeout>=0)delay=std::min(delay,std::chrono::duration_cast<std::chrono::milliseconds>(end-Clock::now()));
      if(delay.count()>0)std::this_thread::sleep_for(delay);if(!AfterWait(request,error))return Fail(error);
    }
  }
};

SocketTransport::SocketTransport(FileSystem &files,addr_t base):impl_(std::make_shared<Impl>(files)),marker_base_(base){if((base&7)||base>UINT64_MAX-std::size(names)*8)throw std::invalid_argument("invalid socket marker base");}
SocketTransport::~SocketTransport()=default;
void SocketTransport::SetWaitCheckpoint(WaitCheckpoint value){if(installed_)throw std::logic_error("socket checkpoint must be set before installation");impl_->checkpoint=std::move(value);}
void SocketTransport::SetWaitObserver(WaitObserver value){if(installed_)throw std::logic_error("socket observer must be set before installation");impl_->observer=std::move(value);}
void SocketTransport::SetBrokenPipeNotification(std::function<void(State*)> value){if(installed_)throw std::logic_error("socket broken-pipe hook must be set before installation");impl_->broken_pipe=std::move(value);}
addr_t SocketTransport::Marker(const std::string &name)const{for(size_t i=0;i<std::size(names);++i)if(name==names[i])return marker_base_+i*8;throw std::invalid_argument("unsupported socket import: "+name);}
int32_t SocketTransport::Socket(int32_t family,int32_t type,int32_t protocol){Environment env;
  if(type&~(0xf|kNonblock|kCloexec))return impl_->Fail(22);
  if(family!=2&&family!=10)return impl_->Fail(97);const int basic=type&0xf;if(basic>=11)return impl_->Fail(22);if(!basic)return impl_->Fail(94);
  if(basic!=1&&basic!=2)return impl_->Fail(95);
  if(protocol<0||protocol>255)return impl_->Fail(22);
  auto socket=impl_->native->socket_call(family==2?AF_INET:AF_INET6,basic,protocol);if(socket==INVALID_SOCKET)return impl_->Fail(SocketError(impl_->native->WSAGetLastError_call()));
  if(family==10){
    // Android 13's Linux profile initializes bindv6only=0. Windows creates
    // IPv6-only sockets by default; set this particular real socket to the
    // declared dual-stack default before it can bind or escape to the guest.
    const int dual_stack=0;
    if(impl_->native->setsockopt_call(socket,IPPROTO_IPV6,IPV6_V6ONLY,reinterpret_cast<const char*>(&dual_stack),sizeof(dual_stack))){const int error=SocketError(impl_->native->WSAGetLastError_call());impl_->native->closesocket_call(socket);return impl_->Fail(error);}
  }
  return impl_->Publish(socket,family,basic,protocol,type);
}
int32_t SocketTransport::Connect(int32_t fd,addr_t pointer,uint32_t length){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);Address address;if(!InputAddress(pointer,length,address,error))return impl_->Fail(error);
  auto request=std::make_shared<Impl::Request>(WaitOperation::Connect,fd);request->endpoint=endpoint;request->bytes.resize(address.length);std::memcpy(request->bytes.data(),&address.value,address.length);impl_->Deadline(request,endpoint->send_timeout.load());Impl::Frame frame(*impl_,request);
  int result=impl_->native->connect_call(endpoint->socket,reinterpret_cast<const sockaddr*>(&address.value),address.length);
  if(!result)return 0;auto code=impl_->native->WSAGetLastError_call();if(code!=WSAEWOULDBLOCK||endpoint->flags.load()&kNonblock)return impl_->Fail(SocketError(code,true));
  if(!impl_->Wait(endpoint,fd,true,error,request))return impl_->Fail(error);int status=0,size=sizeof(status);if(impl_->native->getsockopt_call(endpoint->socket,SOL_SOCKET,SO_ERROR,reinterpret_cast<char*>(&status),&size))return impl_->Fail(SocketError(impl_->native->WSAGetLastError_call()));return status?impl_->Fail(SocketError(status)):0;
}
int32_t SocketTransport::Bind(int32_t fd,addr_t pointer,uint32_t length){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);Address address;if(!InputAddress(pointer,length,address,error))return impl_->Fail(error);const int result=impl_->native->bind_call(endpoint->socket,reinterpret_cast<const sockaddr*>(&address.value),address.length);return result?impl_->Fail(SocketError(impl_->native->WSAGetLastError_call())):0;}
int32_t SocketTransport::Listen(int32_t fd,int32_t backlog){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);const int result=impl_->native->listen_call(endpoint->socket,backlog);return result?impl_->Fail(SocketError(impl_->native->WSAGetLastError_call())):0;}
int32_t SocketTransport::Accept(int32_t fd,addr_t address,addr_t length){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);if(address&&!length)return impl_->Fail(14);
  auto request=std::make_shared<Impl::Request>(WaitOperation::Accept,fd);request->endpoint=endpoint;request->bytes.resize(sizeof(sockaddr_storage));Impl::Frame frame(*impl_,request);
  for(;;){sockaddr_storage source{};int count=sizeof(source);auto socket=impl_->native->accept_call(endpoint->socket,reinterpret_cast<sockaddr*>(&source),&count);
    if(socket!=INVALID_SOCKET){int result=impl_->Publish(socket,endpoint->family,endpoint->type,endpoint->protocol,0);if(result>=0&&address)OutputAddress(source,count,address,length);return result;}
    auto code=impl_->native->WSAGetLastError_call();if(code!=WSAEWOULDBLOCK||endpoint->flags.load()&kNonblock)return impl_->Fail(SocketError(code));if(!impl_->Wait(endpoint,fd,false,error,request))return impl_->Fail(error);}
}
int64_t SocketTransport::Send(int32_t fd,addr_t input,uint64_t length,int32_t flags){return SendTo(fd,input,length,flags,0,0);}
int64_t SocketTransport::Recv(int32_t fd,addr_t output,uint64_t length,int32_t flags){return RecvFrom(fd,output,length,flags,0,0);}
int64_t SocketTransport::SendTo(int32_t fd,addr_t input,uint64_t length,int32_t flags,addr_t address,uint32_t address_length){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);auto result=impl_->Transmit(endpoint,fd,input,length,flags,address,address_length,error);if(result<0)impl_->Fail(error);return result;}
int64_t SocketTransport::RecvFrom(int32_t fd,addr_t output,uint64_t length,int32_t flags,addr_t address,addr_t address_length){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);auto result=impl_->Receive(endpoint,fd,output,length,flags,address,address_length,nullptr,error);if(result<0)impl_->Fail(error);return result;}
int32_t SocketTransport::Name(int32_t fd,addr_t address,addr_t length,bool peer){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);if(!address||!length)return impl_->Fail(14);sockaddr_storage value{};int count=sizeof(value);int result=peer?impl_->native->getpeername_call(endpoint->socket,reinterpret_cast<sockaddr*>(&value),&count):impl_->native->getsockname_call(endpoint->socket,reinterpret_cast<sockaddr*>(&value),&count);if(result)return impl_->Fail(SocketError(impl_->native->WSAGetLastError_call()));OutputAddress(value,count,address,length);return 0;}
int32_t SocketTransport::Shutdown(int32_t fd,int32_t how){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);if(how<0||how>2)return impl_->Fail(22);int result=impl_->native->shutdown_call(endpoint->socket,how);return result?impl_->Fail(SocketError(impl_->native->WSAGetLastError_call())):0;}
int32_t SocketTransport::SetOption(int32_t fd,int32_t level,int32_t option,addr_t pointer,uint32_t length){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);int native_level=0;const auto native_option=NativeOption(level,option,native_level);if(native_option<0)return impl_->Fail(level==1&&option==25?95:92);if(!pointer)return impl_->Fail(14);
  std::array<unsigned char,16> bytes{};int size=4;
  if(level==1&&option==13){if(length<8)return impl_->Fail(22);std::array<int32_t,2> input{};recomp::ReadGuestMemory(input.data(),pointer,8);if(input[1]<0||input[1]>65535)return impl_->Fail(22);
    // Native endpoints stay nonblocking. Winsock can refuse closesocket with
    // WSAEWOULDBLOCK while positive linger is enabled, leaving its handle open.
    // Until blocking close has its own admitted wait, reject this shape before
    // changing the real option. Disabled linger and abortive zero remain real.
    if(input[0]&&input[1]>0)return impl_->Fail(95);
    linger value{static_cast<u_short>(input[0]!=0),static_cast<u_short>(input[1])};std::memcpy(bytes.data(),&value,sizeof(value));size=sizeof(value);}
  else if(level==1&&(option==20||option==21)){if(length<16)return impl_->Fail(22);const auto value=pm::Read(reinterpret_cast<const Timeval*>(pointer));if(value.seconds<0||value.microseconds<0||value.microseconds>=1000000||value.seconds>UINT32_MAX/1000)return impl_->Fail(33);DWORD milliseconds=static_cast<DWORD>(value.seconds*1000+(value.microseconds+999)/1000);std::memcpy(bytes.data(),&milliseconds,sizeof(milliseconds));size=sizeof(milliseconds);}
  else{if(length<4)return impl_->Fail(22);recomp::ReadGuestMemory(bytes.data(),pointer,4);}
  const int result=impl_->native->setsockopt_call(endpoint->socket,native_level,native_option,reinterpret_cast<const char*>(bytes.data()),size);if(result)return impl_->Fail(SocketError(impl_->native->WSAGetLastError_call()));if(level==1&&(option==20||option==21)){DWORD milliseconds=0;std::memcpy(&milliseconds,bytes.data(),sizeof(milliseconds));(option==20?endpoint->receive_timeout:endpoint->send_timeout).store(int64_t(milliseconds)*1000000);}return 0;
}
int32_t SocketTransport::GetOption(int32_t fd,int32_t level,int32_t option,addr_t pointer,addr_t length_pointer){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);if(!pointer||!length_pointer)return impl_->Fail(14);const auto capacity=pm::Read(reinterpret_cast<const uint32_t*>(length_pointer));int native_level=0;const auto native_option=NativeOption(level,option,native_level);if(native_option<0)return impl_->Fail(92);std::array<unsigned char,16> native{};int size=native.size();if(impl_->native->getsockopt_call(endpoint->socket,native_level,native_option,reinterpret_cast<char*>(native.data()),&size))return impl_->Fail(SocketError(impl_->native->WSAGetLastError_call()));std::array<unsigned char,16> output{};uint32_t count=4;
  if(level==1&&option==13){linger value{};std::memcpy(&value,native.data(),sizeof(value));std::array<int32_t,2> guest{int32_t(value.l_onoff),int32_t(value.l_linger)};std::memcpy(output.data(),guest.data(),8);count=8;}
  else if(level==1&&(option==20||option==21)){DWORD milliseconds=0;std::memcpy(&milliseconds,native.data(),sizeof(milliseconds));Timeval value{milliseconds/1000,(milliseconds%1000)*1000};std::memcpy(output.data(),&value,sizeof(value));count=sizeof(value);}
  else{int value=0;std::memcpy(&value,native.data(),std::min<int>(size,4));if(level==1&&option==4)value=SocketError(value);std::memcpy(output.data(),&value,4);}
  recomp::WriteGuestMemory(pointer,output.data(),std::min(capacity,count));pm::Write(reinterpret_cast<uint32_t*>(length_pointer),std::min(capacity,count));return 0;
}
int32_t SocketTransport::Dup2(int32_t source,int32_t target){Environment env;if(target<0)return impl_->Fail(9);if(source==target)return impl_->table->Lookup(source)?target:impl_->Fail(9);
  const auto temporary=impl_->files.Dup(source);if(temporary<0)return -1;if(temporary==target)return target;
  std::shared_ptr<GuestDescriptor> retired;
  {std::lock_guard lock(impl_->table->mutex);auto found=impl_->table->entries.find(temporary);if(found==impl_->table->entries.end())return impl_->Fail(9);auto value=std::move(found->second);impl_->table->entries.erase(found);auto old=impl_->table->entries.find(target);if(old==impl_->table->entries.end())impl_->table->entries.emplace(target,std::move(value));else{retired=std::move(old->second);old->second=std::move(value);}}
  return target;
}
int32_t SocketTransport::Fcntl(int32_t fd,int32_t command,addr_t argument){Environment env;auto entry=impl_->table->Lookup(fd);if(!entry)return impl_->Fail(9);
  const int32_t integer_argument=static_cast<int32_t>(argument);
  if(command==0||command==1030){if(integer_argument<0)return impl_->Fail(22);const int temporary=impl_->files.Dup(fd);if(temporary<0)return -1;std::lock_guard lock(impl_->table->mutex);auto found=impl_->table->entries.find(temporary);if(found==impl_->table->entries.end())return impl_->Fail(9);auto value=found->second;impl_->table->entries.erase(found);value->close_on_exec=command==1030;int result=impl_->table->Allocate(std::move(value),std::max<int>(3,integer_argument));return result<0?impl_->Fail(24):result;}
  if(command==1||command==2){std::lock_guard lock(impl_->table->mutex);auto found=impl_->table->entries.find(fd);if(found==impl_->table->entries.end()||found->second!=entry)return impl_->Fail(9);if(command==1)return entry->close_on_exec?1:0;entry->close_on_exec=bool(integer_argument&1);return 0;}
  if(command==3)return entry->StatusFlags();if(command==4){int error=0;auto result=entry->SetStatusFlags(static_cast<int32_t>(argument),error);return result<0?impl_->Fail(error):result;}return impl_->Fail(22);
}
int32_t SocketTransport::Ioctl(int32_t fd,uint64_t request,addr_t argument){Environment env;auto entry=impl_->table->Lookup(fd);if(!entry)return impl_->Fail(9);if(!argument)return impl_->Fail(14);int error=0;const int result=entry->Ioctl(request,argument,error);return result<0?impl_->Fail(error):result;}
int32_t SocketTransport::Pipe(addr_t output){Environment env;if(!output)return impl_->Fail(14);auto pipe=std::make_shared<Impl::PipeState>();auto read=std::make_shared<Impl::PipeEnd>(pipe,true);auto write=std::make_shared<Impl::PipeEnd>(pipe,false);int descriptors[2]{-1,-1};
  std::lock_guard lock(impl_->table->mutex);descriptors[0]=impl_->table->Allocate(std::make_shared<Impl::PipeDescriptor>(impl_,read));if(descriptors[0]<0)return impl_->Fail(24);
  try{descriptors[1]=impl_->table->Allocate(std::make_shared<Impl::PipeDescriptor>(impl_,write));if(descriptors[1]<0){impl_->table->entries.erase(descriptors[0]);return impl_->Fail(24);}recomp::WriteGuestMemory(output,descriptors,sizeof(descriptors));}
  catch(...){impl_->table->entries.erase(descriptors[0]);if(descriptors[1]>=0)impl_->table->entries.erase(descriptors[1]);throw;}return 0;
}
int32_t SocketTransport::Poll(addr_t pointer,uint32_t count,int32_t timeout){Environment env;if(count>INT32_MAX/sizeof(PollFd))return impl_->Fail(22);std::vector<PollFd> items(count);if(count)recomp::ReadGuestMemory(items.data(),pointer,items.size()*sizeof(PollFd));const int result=impl_->PollItems(items,timeout);if(result<0)return result;for(size_t i=0;i<items.size();++i)recomp::WriteGuestMemory(pointer+i*sizeof(PollFd)+offsetof(PollFd,revents),&items[i].revents,sizeof(items[i].revents));return result;}
int32_t SocketTransport::Select(int32_t count,addr_t reads,addr_t writes,addr_t excepts,addr_t timeout){Environment env;if(count<0||count>1024)return impl_->Fail(22);const size_t bytes=(static_cast<size_t>(count)+63)/64*8;std::array<std::array<uint64_t,16>,3> input{},output{};const addr_t pointers[]{reads,writes,excepts};for(size_t i=0;i<3;++i)if(pointers[i]&&bytes)recomp::ReadGuestMemory(input[i].data(),pointers[i],bytes);
  int milliseconds=-1;Timeval duration{};if(timeout){duration=pm::Read(reinterpret_cast<const Timeval*>(timeout));if(duration.seconds<0||duration.microseconds<0||duration.microseconds>=1000000||duration.seconds>INT32_MAX/1000)return impl_->Fail(22);milliseconds=static_cast<int>(duration.seconds*1000+(duration.microseconds+999)/1000);}
  std::vector<PollFd> items;for(int fd=0;fd<count;++fd){int16_t events=0;if(input[0][fd/64]&(uint64_t{1}<<(fd%64)))events|=1;if(input[1][fd/64]&(uint64_t{1}<<(fd%64)))events|=4;if(input[2][fd/64]&(uint64_t{1}<<(fd%64)))events|=2;if(events){if(!impl_->table->Lookup(fd))return impl_->Fail(9);items.push_back(PollFd{fd,events,0});}}
  const auto start=Clock::now();const int result=impl_->PollItems(items,milliseconds,WaitOperation::Select);if(result<0)return result;int ready=0;
  for(const auto &item:items){const auto bit=uint64_t{1}<<(item.descriptor%64);const auto word=item.descriptor/64;if(item.revents&0x20)return impl_->Fail(9);if((item.events&1)&&(item.revents&(1|8|0x10))){output[0][word]|=bit;++ready;}if((item.events&4)&&(item.revents&(4|8))){output[1][word]|=bit;++ready;}if((item.events&2)&&(item.revents&2)){output[2][word]|=bit;++ready;}}
  for(size_t i=0;i<3;++i)if(pointers[i]&&bytes)recomp::WriteGuestMemory(pointers[i],output[i].data(),bytes);
  if(timeout){const auto elapsed=std::chrono::duration_cast<std::chrono::microseconds>(Clock::now()-start).count();const auto requested=duration.seconds*1000000+duration.microseconds;const auto left=std::max<int64_t>(0,requested-elapsed);pm::Write(reinterpret_cast<Timeval*>(timeout),Timeval{left/1000000,left%1000000});}return ready;
}
int64_t SocketTransport::SendMsg(int32_t fd,addr_t pointer,int32_t flags){Environment env;int error=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);const auto message=pm::Read(reinterpret_cast<const Message*>(pointer));if(message.control_length)return impl_->Fail(95);if(message.vector_count>1024)return impl_->Fail(90);std::vector<Iovec> vectors(message.vector_count);if(!vectors.empty())recomp::ReadGuestMemory(vectors.data(),message.vectors,vectors.size()*sizeof(Iovec));uint64_t length=0;for(const auto &v:vectors){if(v.length>INT64_MAX-length)return impl_->Fail(90);length+=v.length;}if(endpoint->type==2&&length>65535)return impl_->Fail(90);const auto staged=static_cast<size_t>(std::min<uint64_t>(length,65536));std::vector<unsigned char> bytes(staged);size_t at=0;for(const auto &v:vectors){const auto part=std::min<uint64_t>(v.length,staged-at);if(part)recomp::ReadGuestMemory(bytes.data()+at,v.base,static_cast<size_t>(part));at+=static_cast<size_t>(part);if(at==staged)break;}auto result=impl_->Transmit(endpoint,fd,reinterpret_cast<addr_t>(bytes.data()),staged,flags,message.name,message.name_length,error);if(result<0)impl_->Fail(error);return result;}
int64_t SocketTransport::RecvMsg(int32_t fd,addr_t pointer,int32_t flags){Environment env;auto message=pm::Read(reinterpret_cast<const Message*>(pointer));if(message.control_length)return impl_->Fail(95);if(message.vector_count>1024)return impl_->Fail(90);std::vector<Iovec> vectors(message.vector_count);if(!vectors.empty())recomp::ReadGuestMemory(vectors.data(),message.vectors,vectors.size()*sizeof(Iovec));uint64_t length=0;for(const auto &v:vectors){if(v.length>INT64_MAX-length)return impl_->Fail(90);length+=v.length;}uint32_t name_length=message.name_length;int error=0,output_flags=0;auto endpoint=impl_->Lookup(fd,error);if(!endpoint)return impl_->Fail(error);auto result=impl_->Receive(endpoint,fd,0,length,flags,message.name,reinterpret_cast<addr_t>(&name_length),&output_flags,error,&vectors);if(result<0)return impl_->Fail(error);
  recomp::WriteGuestMemory(pointer+offsetof(Message,name_length),&name_length,sizeof(name_length));const uint64_t control=0;recomp::WriteGuestMemory(pointer+offsetof(Message,control_length),&control,sizeof(control));recomp::WriteGuestMemory(pointer+offsetof(Message,flags),&output_flags,sizeof(output_flags));return result;}
const char *SocketTransport::InetNtop(int32_t family,addr_t input,addr_t output,uint32_t length){Environment env;if(family!=2&&family!=10){impl_->Fail(97);return nullptr;}std::array<unsigned char,16> binary{};recomp::ReadGuestMemory(binary.data(),input,family==2?4:16);std::array<char,64> text{};if(!impl_->native->ntop_call(family==2?AF_INET:AF_INET6,binary.data(),text.data(),text.size())){impl_->Fail(SocketError(impl_->native->WSAGetLastError_call()));return nullptr;}
  // Windows may spell IPv6 hex with uppercase; Bionic uses lowercase.
  for(auto &c:text)if(c>='A'&&c<='F')c=static_cast<char>(c+'a'-'A');const auto size=std::strlen(text.data())+1;if(size>length){impl_->Fail(28);return nullptr;}recomp::WriteGuestMemory(output,text.data(),size);return reinterpret_cast<const char*>(output);
}
void SocketTransport::Install(recomp::Runtime &runtime,DescriptorImportInterceptor interceptor){if(installed_)throw std::logic_error("socket provider already installed");
  auto add=[&](const char *name,auto bridge){runtime.AddImport(Marker(name),[name,bridge=std::move(bridge),interceptor](State &state){Environment native;DescriptorImportScope active(&state);try{if(interceptor)interceptor(name,state,[&]{bridge(state);});else bridge(state);}catch(const std::exception &error){std::fprintf(stderr,"socket provider %s: %s\n",name,error.what());std::fflush(stderr);std::abort();}catch(...){std::abort();}});};
  add("socket",recomp::MakeBridge<int32_t(int32_t,int32_t,int32_t)>([this](auto f,auto t,auto p){return Socket(f,t,p);}));
  for(const auto *name:{"connect","bind"})add(name,recomp::MakeBridge<int32_t(int32_t,addr_t,uint32_t)>([this,name](auto fd,auto p,auto n){return std::strcmp(name,"bind")?Connect(fd,p,n):Bind(fd,p,n);}));
  add("listen",recomp::MakeBridge<int32_t(int32_t,int32_t)>([this](auto fd,auto n){return Listen(fd,n);}));
  add("accept",recomp::MakeBridge<int32_t(int32_t,addr_t,addr_t)>([this](auto fd,auto p,auto n){return Accept(fd,p,n);}));
  add("send",recomp::MakeBridge<int64_t(int32_t,addr_t,uint64_t,int32_t)>([this](auto fd,auto p,auto n,auto f){return Send(fd,p,n,f);}));
  add("recv",recomp::MakeBridge<int64_t(int32_t,addr_t,uint64_t,int32_t)>([this](auto fd,auto p,auto n,auto f){return Recv(fd,p,n,f);}));
  add("sendto",recomp::MakeBridge<int64_t(int32_t,addr_t,uint64_t,int32_t,addr_t,uint32_t)>([this](auto fd,auto p,auto n,auto f,auto a,auto l){return SendTo(fd,p,n,f,a,l);}));
  add("recvfrom",recomp::MakeBridge<int64_t(int32_t,addr_t,uint64_t,int32_t,addr_t,addr_t)>([this](auto fd,auto p,auto n,auto f,auto a,auto l){return RecvFrom(fd,p,n,f,a,l);}));
  for(const auto *name:{"getsockname","getpeername"})add(name,recomp::MakeBridge<int32_t(int32_t,addr_t,addr_t)>([this,name](auto fd,auto p,auto n){return Name(fd,p,n,!std::strcmp(name,"getpeername"));}));
  add("setsockopt",recomp::MakeBridge<int32_t(int32_t,int32_t,int32_t,addr_t,uint32_t)>([this](auto fd,auto l,auto o,auto p,auto n){return SetOption(fd,l,o,p,n);}));
  add("getsockopt",recomp::MakeBridge<int32_t(int32_t,int32_t,int32_t,addr_t,addr_t)>([this](auto fd,auto l,auto o,auto p,auto n){return GetOption(fd,l,o,p,n);}));
  add("shutdown",recomp::MakeBridge<int32_t(int32_t,int32_t)>([this](auto fd,auto h){return Shutdown(fd,h);}));
  add("sendmsg",recomp::MakeBridge<int64_t(int32_t,addr_t,int32_t)>([this](auto fd,auto p,auto f){return SendMsg(fd,p,f);}));
  add("recvmsg",recomp::MakeBridge<int64_t(int32_t,addr_t,int32_t)>([this](auto fd,auto p,auto f){return RecvMsg(fd,p,f);}));
  add("dup2",recomp::MakeBridge<int32_t(int32_t,int32_t)>([this](auto s,auto t){return Dup2(s,t);}));
  add("fcntl",recomp::MakeBridge<int32_t(int32_t,int32_t,addr_t)>([this](auto fd,auto c,auto a){return Fcntl(fd,c,a);}));
  add("ioctl",recomp::MakeBridge<int32_t(int32_t,uint32_t,addr_t)>([this](auto fd,auto r,auto a){return Ioctl(fd,r,a);}));
  add("pipe",recomp::MakeBridge<int32_t(addr_t)>([this](auto p){return Pipe(p);}));
  add("poll",recomp::MakeBridge<int32_t(addr_t,uint32_t,int32_t)>([this](auto p,auto n,auto t){return Poll(p,n,t);}));
  add("select",recomp::MakeBridge<int32_t(int32_t,addr_t,addr_t,addr_t,addr_t)>([this](auto n,auto r,auto w,auto e,auto t){return Select(n,r,w,e,t);}));
  add("inet_ntop",recomp::MakeBridge<const char*(int32_t,addr_t,addr_t,uint32_t)>([this](auto f,auto p,auto o,auto n){return InetNtop(f,p,o,n);}));
  installed_=true;
}
}  // namespace bunker::windows

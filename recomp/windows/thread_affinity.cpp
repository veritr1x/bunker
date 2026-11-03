#include <cfenv>
#include "thread_affinity.h"
#include "../whole/bridge.h"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <set>
#include <stdexcept>
#include <vector>
#include <windows.h>
namespace bunker::windows {
namespace {
static_assert(sizeof(addr_t)==8&&sizeof(DWORD_PTR)==8&&sizeof(CPU_SET_INFORMATION_TYPE)==4,"affinity requires Windows64 wire widths");
struct Environment {
 int error=errno;DWORD last=GetLastError();fenv_t fp{};
 Environment(){std::fegetenv(&fp);}
 ~Environment(){std::fesetenv(&fp);errno=error;SetLastError(last);}
};
int NativeError(DWORD e,HANDLE target){
 if(WaitForSingleObject(target,0)==WAIT_OBJECT_0)return 3;
 switch(e){case ERROR_ACCESS_DENIED:return 1;case ERROR_INVALID_HANDLE:return 3;case ERROR_INVALID_PARAMETER:return 22;}
 throw std::runtime_error("unsupported native affinity API failure "+std::to_string(e));
}
[[noreturn]]void TopologyError(const char*name){const auto e=GetLastError();throw std::runtime_error(std::string("unsupported affinity topology query ")+name+" error "+std::to_string(e));}
unsigned Count(uint64_t mask){unsigned n=0;while(mask){mask&=mask-1;++n;}return n;}
int PointerError(addr_t address){
 constexpr uint64_t limit=1ULL<<48,untag=0x00ffffffffffffffULL;
 const auto low=address&untag;
 // Same explicit lower48, untagged software-user profile as private futexes;
 // not an inferred device VA_BITS/TBI or a pointer-alignment requirement.
 if(low>=limit||4>limit-low)return 14;
 if(address!=low)throw std::runtime_error("unsupported affinity tagged-address ABI profile");
 return 0;
}
bool ReadMask(addr_t address,uint32_t &value){
 bool okay=false;uint64_t unsupported=0;
 recomp::WithGuestMemoryRead([&]{
  SIZE_T bytes=0;const BOOL success=ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),&value,sizeof(value),&bytes);
  if(success&&bytes==sizeof(value)){okay=true;return;}
  const auto e=GetLastError();if(e==ERROR_PARTIAL_COPY||e==ERROR_NOACCESS||e==ERROR_INVALID_ADDRESS)return;
  unsupported=e?e:UINT64_MAX;
 });
 if(unsupported)throw std::runtime_error("unsupported affinity native fault-safe read failure "+std::to_string(unsupported));
 return okay;
}
bool ReadKernelWord(addr_t address,uint64_t &value){
 constexpr uint64_t limit=1ULL<<48,untag=0x00ffffffffffffffULL;const auto low=address&untag;
 if(low>=limit||8>limit-low)return false;
 if(address!=low)throw std::runtime_error("unsupported affinity tagged-address ABI profile");
 bool okay=false;DWORD unsupported=0;
 recomp::WithGuestMemoryRead([&]{SIZE_T bytes=0;const BOOL success=ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),&value,8,&bytes);
  if(success&&bytes==8){okay=true;return;}const auto error=GetLastError();
  if(error!=ERROR_PARTIAL_COPY&&error!=ERROR_NOACCESS&&error!=ERROR_INVALID_ADDRESS)unsupported=error?error:0xffffffff;});
 if(unsupported)throw std::runtime_error("unsupported affinity fault-safe kernel-word read "+std::to_string(unsupported));
 return okay;
}
// Native kernel copy respects protection; partial effects remain tracked.
bool WriteMaskBytes(addr_t address,const void *data,size_t size){
 constexpr uint64_t limit=1ULL<<48,untag=0x00ffffffffffffffULL;const auto low=address&untag;
 if(low>=limit||size>limit-low)return false;
 if(address!=low)throw std::runtime_error("unsupported affinity tagged-address ABI profile");
 using NativeWrite=LONG(WINAPI*)(HANDLE,void*,const void*,SIZE_T,SIZE_T*);
 static const NativeWrite copy=[](){auto address=GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"NtWriteVirtualMemory");NativeWrite function{};
  static_assert(sizeof(function)==sizeof(address));std::memcpy(&function,&address,sizeof(function));
  if(!function)throw std::runtime_error("unsupported affinity NtWriteVirtualMemory unavailable");
  return function;}();
 LONG status=0;SIZE_T written=0;
 recomp::WithGuestMemoryWrite(address,size,[&]{status=copy(GetCurrentProcess(),reinterpret_cast<void*>(address),data,size,&written);});
 if(status>=0&&written==size)return true;
 if(uint32_t(status)==0x8000000dU||uint32_t(status)==0xc0000005U)return false;
 throw std::runtime_error("unsupported affinity native fault-safe write status "+std::to_string(uint32_t(status)));
}
using MaskQuery=BOOL(WINAPI*)(HANDLE,PGROUP_AFFINITY,USHORT,PUSHORT);
template<class Function>Function CpuFunction(const char*name){
 auto address=GetProcAddress(GetModuleHandleW(L"kernel32.dll"),name);Function function{};
 static_assert(sizeof(function)==sizeof(address));std::memcpy(&function,&address,sizeof(function));
 if(!function)throw std::runtime_error(std::string("unsupported affinity CPU-set mask API unavailable: ")+name);
 return function;
}
int EmptyCpuSets(HANDLE target){
 using IdQuery=BOOL(WINAPI*)(HANDLE,PULONG,ULONG,PULONG);
 static const auto process_ids=CpuFunction<IdQuery>("GetProcessDefaultCpuSets");
 static const auto thread_ids=CpuFunction<IdQuery>("GetThreadSelectedCpuSets");
 ULONG process_count=0,thread_count=0;
 const BOOL process_ok=process_ids(GetCurrentProcess(),nullptr,0,&process_count);
 const auto process_error=process_ok?0:GetLastError();
 if(!process_ok&&process_error!=ERROR_INSUFFICIENT_BUFFER)throw std::runtime_error("unsupported affinity process CPU-set query "+std::to_string(process_error));
 if(process_count)throw std::runtime_error("unsupported affinity process default CPU sets");
 const BOOL thread_ok=thread_ids(target,nullptr,0,&thread_count);
 const auto thread_error=thread_ok?0:GetLastError();
 if(!thread_ok&&thread_error!=ERROR_INSUFFICIENT_BUFFER){if(WaitForSingleObject(target,0)==WAIT_OBJECT_0)return 3;throw std::runtime_error("unsupported affinity thread CPU-set query "+std::to_string(thread_error));}
 if(thread_count)throw std::runtime_error("unsupported affinity thread selected CPU sets");
 // Query both views, including selections supplied by the newer mask APIs.
 // Missing Windows11 API is an explicit profile boundary, never empty success.
 static const auto process_masks=CpuFunction<MaskQuery>("GetProcessDefaultCpuSetMasks");
 static const auto thread_masks=CpuFunction<MaskQuery>("GetThreadSelectedCpuSetMasks");
 USHORT pn=0,tn=0;
 const BOOL pok=process_masks(GetCurrentProcess(),nullptr,0,&pn);const auto pe=pok?0:GetLastError();
 if(!pok&&pe!=ERROR_INSUFFICIENT_BUFFER)throw std::runtime_error("unsupported affinity process CPU-set mask query "+std::to_string(pe));
 if(pn)throw std::runtime_error("unsupported affinity process default CPU-set masks");
 const BOOL tok=thread_masks(target,nullptr,0,&tn);const auto te=tok?0:GetLastError();
 if(!tok&&te!=ERROR_INSUFFICIENT_BUFFER){if(WaitForSingleObject(target,0)==WAIT_OBJECT_0)return 3;throw std::runtime_error("unsupported affinity thread CPU-set mask query "+std::to_string(te));}
 if(tn)throw std::runtime_error("unsupported affinity thread selected CPU-set masks");
 return 0;
}
void CheckCpuReservations(uint64_t system){
 using Information=BOOL(WINAPI*)(PSYSTEM_CPU_SET_INFORMATION,ULONG,PULONG,HANDLE,ULONG);
 static const auto query=CpuFunction<Information>("GetSystemCpuSetInformation");
 ULONG bytes=0;const BOOL first=query(nullptr,0,&bytes,GetCurrentProcess(),0);
 const auto first_error=first?0:GetLastError();
 if(!first&&first_error!=ERROR_INSUFFICIENT_BUFFER)throw std::runtime_error("unsupported affinity CPU-set information sizing "+std::to_string(first_error));
 if(!bytes||bytes>16*1024*1024)throw std::runtime_error("unsupported affinity CPU-set information extent");
 std::vector<uint8_t> data(bytes);ULONG used=bytes;
 if(!query(reinterpret_cast<PSYSTEM_CPU_SET_INFORMATION>(data.data()),bytes,&used,GetCurrentProcess(),0))TopologyError("CPU-set information");
 if(used>bytes)throw std::runtime_error("malformed native affinity CPU-set information length");
 size_t offset=0;uint64_t observed=0;std::set<DWORD> ids;
 while(offset<used){
  if(used-offset<8)throw std::runtime_error("malformed native affinity CPU-set record header");
  DWORD size=0;CPU_SET_INFORMATION_TYPE type{};std::memcpy(&size,data.data()+offset,4);std::memcpy(&type,data.data()+offset+4,4);
  if(size<8||size>used-offset)throw std::runtime_error("malformed native affinity CPU-set record extent");
  if(type==CpuSetInformation){
   if(size<sizeof(SYSTEM_CPU_SET_INFORMATION))throw std::runtime_error("malformed native affinity CPU-set information record");
   SYSTEM_CPU_SET_INFORMATION record{};std::memcpy(&record,data.data()+offset,sizeof(record));const auto &c=record.CpuSet;
   if(c.Group||c.LogicalProcessorIndex>=64||!ids.insert(c.Id).second)throw std::runtime_error("unsupported affinity CPU-set processor identity");
   const uint64_t bit=1ULL<<c.LogicalProcessorIndex;if(observed&bit)throw std::runtime_error("duplicate native affinity CPU-set processor index");
   // Parked is a power-management state, not an exclusive reservation and
   // not an eligibility filter. Reject allocations/realtime/unknown flags.
   if((c.AllFlags&0xfe)||c.AllocationTag)throw std::runtime_error("unsupported affinity CPU-set reservation/allocation profile");
   observed|=bit;
  }
  offset+=size;
 }
 if(observed!=system)throw std::runtime_error("unsupported affinity CPU-set/system processor mask discrepancy");
}
int Topology(HANDLE target,ThreadAffinities::Observation &o){
 const auto wait=WaitForSingleObject(target,0);if(wait==WAIT_OBJECT_0)return 3;
 if(wait!=WAIT_TIMEOUT)TopologyError("target liveness");
 if(GetActiveProcessorGroupCount()!=1||GetMaximumProcessorGroupCount()!=1)throw std::runtime_error("unsupported affinity multiple processor groups");
 USHORT count=1,group=0xffff;
 if(!GetProcessGroupAffinity(GetCurrentProcess(),&count,&group))TopologyError("process groups");
 if(count!=1||group)throw std::runtime_error("unsupported affinity process group membership");
 DWORD_PTR process=0,system=0;
 if(!GetProcessAffinityMask(GetCurrentProcess(),&process,&system))TopologyError("process masks");
 if(!process||!system||(process&~system))throw std::runtime_error("unsupported affinity native process/system mask profile");
 const auto active=GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
 if(!active||active!=GetActiveProcessorCount(0)||active!=Count(system))throw std::runtime_error("unsupported affinity native online processor count discrepancy");
 GROUP_AFFINITY current{};
 if(!GetThreadGroupAffinity(target,&current)){const auto e=GetLastError();return NativeError(e,target);}
 if(current.Group)throw std::runtime_error("unsupported affinity target processor group");
 if(const auto error=EmptyCpuSets(target))return error;
 CheckCpuReservations(system);
 // Current thread.Mask is deliberately NOT the ceiling: widening is allowed.
 o.process_mask=process;o.system_mask=system;o.effective_mask=uint64_t(o.requested_mask)&process&system;o.topology_valid=true;
 return 0;
}
}
struct ThreadAffinities::Impl {
 Pthreads &threads;addr_t marker;Observer observer;std::function<void(int)> error_sink;std::mutex mutex;bool installed=false;
 Impl(Pthreads&t,addr_t m,Observer o):threads(t),marker(m),observer(std::move(o)){}
 void Observe(Observation &o,Observation::Phase phase){o.phase=phase;if(observer){Environment preserve;observer(o);}}
 int64_t Fail(Observation &o,int error){o.error=error;o.result=-1;error_sink(error);Observe(o,Observation::Phase::Return);return -1;}
 int64_t Call(int64_t number,int32_t pid,uint32_t size,addr_t pointer){
  Environment preserve;
  if(uint32_t(number)!=122)throw std::runtime_error("unsupported affinity syscall low32 number");
  if(size!=4)throw std::runtime_error("unsupported sched_setaffinity cpusetsize profile (only4)");
  if(!error_sink)throw std::logic_error("affinity requires a guest errno sink before operation");
  Observation o;o.pid=pid;o.size=size;o.user_mask=pointer;
  if(const auto error=PointerError(pointer))return Fail(o,error);
  if(!ReadMask(pointer,o.requested_mask))return Fail(o,14);
  o.mask_copied=true;Observe(o,Observation::Phase::MaskCopied);
  // Linux copies before looking up even a negative/nonexistent target PID.
  auto lease=threads.AcquireNativeThread(static_cast<uint32_t>(pid));if(!lease)return Fail(o,3);
  o.target_resolved=true;o.resolved_tid=lease.NativeTid();const auto target=reinterpret_cast<HANDLE>(lease.NativeHandleBits());
  int error=0;
  {
   std::lock_guard lock(mutex);error=Topology(target,o);
   if(!error&&!o.effective_mask)error=22;
   if(!error){
    o.native_set_called=true;
    const auto previous=SetThreadAffinityMask(target,static_cast<DWORD_PTR>(o.effective_mask));
    if(!previous){const auto e=GetLastError();error=NativeError(e,target);}
    else {
     o.previous_mask=previous;GROUP_AFFINITY actual{};
     if(!GetThreadGroupAffinity(target,&actual)){const auto e=GetLastError();throw std::runtime_error("affinity readback failed after actual native mutation "+std::to_string(e));}
     o.readback_mask=actual.Mask;
     if(actual.Group||actual.Mask!=o.effective_mask)throw std::runtime_error("affinity native readback differs from effective mask");
     o.readback_valid=true;
    }
   }
  }
  if(error)return Fail(o,error);
  o.result=0;o.error=0;Observe(o,Observation::Phase::Return);return 0;
 }
 int32_t Set(int32_t pid,uint64_t size,addr_t pointer){
  Environment preserve;if(!error_sink)throw std::logic_error("affinity requires a guest errno sink before operation");
  if(size!=128)throw std::runtime_error("unsupported public sched_setaffinity cpusetsize profile (only128)");
  auto fail=[&](int error){error_sink(error);return int32_t(-1);};uint64_t requested=0;
  // Kernel clamps the supported input to its one64-bit-word mask before
  // target lookup, with no read of the remaining120B public CPU-set tail.
  if(!ReadKernelWord(pointer,requested))return fail(14);
  auto lease=threads.AcquireNativeThread(static_cast<uint32_t>(pid));if(!lease)return fail(3);
  const auto target=reinterpret_cast<HANDLE>(lease.NativeHandleBits());int error=0;
  {std::lock_guard lock(mutex);Observation topology;error=Topology(target,topology);
   const uint64_t effective=requested&topology.process_mask&topology.system_mask;
   if(!error&&!effective)error=22;
   if(!error){const auto previous=SetThreadAffinityMask(target,static_cast<DWORD_PTR>(effective));
    if(!previous){const auto e=GetLastError();error=NativeError(e,target);}
    else {GROUP_AFFINITY actual{};if(!GetThreadGroupAffinity(target,&actual)){const auto e=GetLastError();throw std::runtime_error("public affinity readback failed after actual native mutation "+std::to_string(e));}
     if(actual.Group||actual.Mask!=effective)throw std::runtime_error("public affinity native readback differs from effective mask");}
   }
  }
  if(error)return fail(error);
  return 0;
 }
 int32_t Get(int32_t pid,uint64_t size,addr_t pointer){
  Environment preserve;
  if(!error_sink)throw std::logic_error("affinity requires a guest errno sink before operation");
  auto fail=[&](int error){error_sink(error);return int32_t(-1);};
  // One kernel64 word in the explicit native single-group profile. Public
  // Bionic normalizes its raw positive byte count and zeroes the rest128.
  if(size>UINT32_MAX)throw std::runtime_error("unsupported sched_getaffinity size_t profile");
  if(size<8||(size&7))return fail(22);
  if(size!=128)throw std::runtime_error("unsupported sched_getaffinity cpusetsize profile (only128)");
  auto lease=threads.AcquireNativeThread(static_cast<uint32_t>(pid));if(!lease)return fail(3);
  const auto target=reinterpret_cast<HANDLE>(lease.NativeHandleBits());uint64_t mask=0;int error=0;
  {std::lock_guard lock(mutex);Observation topology;error=Topology(target,topology);
   if(!error){GROUP_AFFINITY actual{};
    if(!GetThreadGroupAffinity(target,&actual)){const auto e=GetLastError();error=NativeError(e,target);}
    else {if(actual.Group||!actual.Mask||(uint64_t(actual.Mask)&~topology.system_mask))throw std::runtime_error("unsupported affinity getter native group/mask profile");
     mask=uint64_t(actual.Mask)&topology.process_mask&topology.system_mask;
     if(!mask)throw std::runtime_error("unsupported affinity getter empty native effective mask");}
   }
  }
  if(error)return fail(error);
  // Target lookup precedes pointer faults. Do not feed old setter observer.
  if(!WriteMaskBytes(pointer,&mask,sizeof(mask)))return fail(14);
  const unsigned char zeros[120]{};
  if(!WriteMaskBytes(pointer+sizeof(mask),zeros,sizeof(zeros)))throw std::runtime_error("sched_getaffinity libc zero-tail memory fault after successful kernel copy");
  return 0;
 }
};
ThreadAffinities::ThreadAffinities(Pthreads&t,Profile p,addr_t marker,Observer observer){
 if(p!=Profile::WindowsSingleGroupNativeIndices||marker%8)throw std::invalid_argument("affinity needs explicit native single-group profile/aligned marker");
 impl_=std::make_shared<Impl>(t,marker,std::move(observer));
}
ThreadAffinities::~ThreadAffinities()=default;
void ThreadAffinities::SetErrorSink(std::function<void(int)>sink){if(impl_->installed)throw std::logic_error("affinity errno sink must be configured before import publication");impl_->error_sink=std::move(sink);}
int64_t ThreadAffinities::Syscall(int64_t n,int32_t p,uint32_t size,addr_t mask,addr_t,addr_t,addr_t){return impl_->Call(n,p,size,mask);}
int32_t ThreadAffinities::Get(int32_t pid,uint64_t size,addr_t pointer){return impl_->Get(pid,size,pointer);}
int32_t ThreadAffinities::Set(int32_t pid,uint64_t size,addr_t pointer){return impl_->Set(pid,size,pointer);}
addr_t ThreadAffinities::Marker(const std::string&name)const {if(name=="sched_getaffinity")return impl_->marker+8;if(name=="sched_setaffinity")return impl_->marker+16;if(name!="syscall")throw std::invalid_argument("unsupported affinity import "+name);return impl_->marker;}
void ThreadAffinities::Install(recomp::Runtime&runtime){
 if(impl_->installed||!impl_->error_sink)throw std::logic_error("affinity import needs exactly one publication and configured errno sink");
 std::weak_ptr<Impl> weak=impl_;
 auto bridge=recomp::MakeBridge<int64_t(int64_t,int32_t,uint32_t,addr_t,addr_t,addr_t,addr_t)>([weak](auto n,auto p,auto size,auto mask,auto,auto,auto){auto self=weak.lock();if(!self)throw std::runtime_error("affinity provider owner expired");return self->Call(n,p,size,mask);});
 runtime.AddImport(impl_->marker,[bridge=std::move(bridge)](State&s){try{bridge(s);}catch(const std::exception&e){std::fprintf(stderr,"thread affinity syscall: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fprintf(stderr,"thread affinity syscall: unknown native exception\n");std::fflush(stderr);std::abort();}});
 auto getter=recomp::MakeBridge<int32_t(int32_t,uint64_t,addr_t)>([weak](auto pid,auto size,auto pointer){auto self=weak.lock();if(!self)throw std::runtime_error("affinity provider owner expired");return self->Get(pid,size,pointer);});
 runtime.AddImport(impl_->marker+8,[getter=std::move(getter)](State&s){try{getter(s);}catch(const std::exception&e){std::fprintf(stderr,"thread affinity sched_getaffinity: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fprintf(stderr,"thread affinity sched_getaffinity: unknown native exception\n");std::fflush(stderr);std::abort();}});
 auto setter=recomp::MakeBridge<int32_t(int32_t,uint64_t,addr_t)>([weak](auto pid,auto size,auto pointer){auto self=weak.lock();if(!self)throw std::runtime_error("affinity provider owner expired");return self->Set(pid,size,pointer);});
 runtime.AddImport(impl_->marker+16,[setter=std::move(setter)](State&s){try{setter(s);}catch(const std::exception&e){std::fprintf(stderr,"thread affinity sched_setaffinity: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fprintf(stderr,"thread affinity sched_setaffinity: unknown native exception\n");std::fflush(stderr);std::abort();}});
 impl_->installed=true;
}
}
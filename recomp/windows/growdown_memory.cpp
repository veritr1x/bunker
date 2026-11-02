#include "growdown_memory.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <stdexcept>
#include <windows.h>

namespace bunker::windows {
namespace {
constexpr uint64_t kPage=4096,kClosed=uint64_t(1)<<63;
constexpr uint32_t kUnused=0,kReserved=1,kLive=2,kRetired=3;
struct Manager;
std::atomic<Manager*> manager{nullptr};
std::atomic<uint64_t> handler_entries{0};
std::mutex allocation_mutex;
static_assert(std::atomic<uint64_t>::is_always_lock_free&&std::atomic<uint32_t>::is_always_lock_free&&std::atomic<Manager*>::is_always_lock_free,"fault state must use native lock-free atomics");
DWORD NativeProtection(int value) noexcept {return value&2?PAGE_READWRITE:value&1?PAGE_READONLY:PAGE_NOACCESS;}
bool Intersects(addr_t a,uint64_t n,addr_t b,uint64_t m) noexcept {return a>=b?a-b<m:b-a<n;}
}
struct GrowdownMemory::Control {
  // Immutable after publication. Records are never reused, even after release.
  Region region{};
  std::atomic<uint32_t> publication{kUnused};
  std::atomic<uint64_t> phase{kClosed},committed{0};
  std::atomic<int> protection{3};
  // Fixed diagnostic state only; no logger/allocator/error-provider in the VEH.
  std::atomic<uint32_t> fault_failure{0};
  std::atomic<addr_t> fault_address{0};
};
namespace {
struct Manager {
  std::mutex creation;
  std::array<GrowdownMemory::Control,GrowdownMemory::kLifetimeLimit> controls{};
  std::array<std::atomic<DWORD>,4096> recursion{};
  std::atomic<uint32_t> lifetime{0},active{0};
  PVOID handler=nullptr;
  static LONG CALLBACK Handler(EXCEPTION_POINTERS *exception) noexcept {
    const auto saved=GetLastError();
    handler_entries.fetch_add(1,std::memory_order_acq_rel);
    auto *self=manager.load(std::memory_order_acquire);
    const auto result=self?self->Handle(exception):EXCEPTION_CONTINUE_SEARCH;
    handler_entries.fetch_sub(1,std::memory_order_release);
    SetLastError(saved);return result;
  }
  Manager(){
    SYSTEM_INFO info{};GetSystemInfo(&info);
    if(info.dwPageSize!=kPage||!info.dwAllocationGranularity||GrowdownMemory::kGap%info.dwAllocationGranularity||GrowdownMemory::kAdditional%info.dwAllocationGranularity)
      throw std::runtime_error("unsupported growdown Windows page/allocation granularity");
    // The trampoline reads this already initialized pointer, never a function
    // local static and never an emutls/get-once/allocation path.
    manager.store(this,std::memory_order_release);
    handler=AddVectoredExceptionHandler(1,&Handler);
    if(!handler){manager.store(nullptr,std::memory_order_release);throw std::runtime_error("native growdown VEH registration failed");}
  }
  ~Manager(){
    manager.store(nullptr,std::memory_order_release);
    if(active.load(std::memory_order_acquire)||handler_entries.load(std::memory_order_acquire)){
      std::fputs("growdown manager destruction without quiescent owners/fault readers\n",stderr);std::abort();
    }
    if(handler&&!RemoveVectoredExceptionHandler(handler))std::abort();
  }
  LONG Handle(EXCEPTION_POINTERS *exception) noexcept {
    if(!exception||!exception->ExceptionRecord)return EXCEPTION_CONTINUE_SEARCH;
    const auto &record=*exception->ExceptionRecord;
    if(record.ExceptionCode!=EXCEPTION_ACCESS_VIOLATION||(record.ExceptionFlags&EXCEPTION_NONCONTINUABLE)||record.NumberParameters<2)return EXCEPTION_CONTINUE_SEARCH;
    const auto access=record.ExceptionInformation[0];
    if(access!=0&&access!=1)return EXCEPTION_CONTINUE_SEARCH;
    // Native TID CAS slots: no C++ thread_local, TlsAlloc/GetValue expansion,
    // CRT key lookup, mutex, wait, heap allocation or per-thread first touch.
    const auto tid=GetCurrentThreadId();size_t slot=recursion.size();
    // Search the complete table before claiming an empty slot: a nested entry
    // must find its outer TID even if an earlier collision slot became empty.
    if(!tid)return EXCEPTION_CONTINUE_SEARCH;
    for(const auto &entry:recursion)if(entry.load(std::memory_order_acquire)==tid)return EXCEPTION_CONTINUE_SEARCH;
    for(size_t n=0;n<recursion.size();++n){auto i=(static_cast<size_t>(tid)*2654435761u+n)&(recursion.size()-1);DWORD expected=0;
      if(recursion[i].compare_exchange_strong(expected,tid,std::memory_order_acq_rel,std::memory_order_relaxed)){slot=i;break;}
      if(expected==tid)return EXCEPTION_CONTINUE_SEARCH;
    }
    if(slot==recursion.size())return EXCEPTION_CONTINUE_SEARCH;
    const auto address=static_cast<addr_t>(record.ExceptionInformation[1]);LONG result=EXCEPTION_CONTINUE_SEARCH;
    const auto count=lifetime.load(std::memory_order_acquire);
    for(uint32_t i=0;i<count;++i){auto &control=controls[i];
      if(control.publication.load(std::memory_order_acquire)!=kLive)continue;
      const auto &r=control.region;
      if(address<r.low||address>=r.initial)continue; // Only original growth capacity.
      auto phase=control.phase.load(std::memory_order_acquire);bool entered=false;
      while(!(phase&kClosed)&&phase<kClosed-1){if(control.phase.compare_exchange_weak(phase,phase+1,std::memory_order_acq_rel,std::memory_order_acquire)){entered=true;break;}}
      // A just-released closed record can briefly precede a newly published
      // owner at the same native address. Never let its tombstone shadow that
      // new generation; no closed control may service an access itself.
      if(!entered)continue;
      const auto protection=control.protection.load(std::memory_order_acquire);
      if((access==1&&!(protection&2))||(access==0&&!(protection&3))){control.fault_address.store(address,std::memory_order_relaxed);control.fault_failure.store(1,std::memory_order_release);}
      else{
        const auto page=address&~(kPage-1);auto previous=control.committed.load(std::memory_order_acquire);
        bool committed=true;
        // Refuse foreign/protection changes instead of recommitting them with
        // this owner's protection. Parallel first commits have the same native
        // allocation and protection, so they remain safe/idempotent here.
        for(auto cursor=page;committed&&cursor<previous;){MEMORY_BASIC_INFORMATION part{};
          if(!VirtualQuery(reinterpret_cast<void*>(cursor),&part,sizeof(part))||part.AllocationBase!=reinterpret_cast<void*>(r.reservation)||
             (part.State!=MEM_RESERVE&&part.State!=MEM_COMMIT)||(part.State==MEM_COMMIT&&((part.Protect&PAGE_GUARD)||(part.Protect&0xff)!=NativeProtection(protection)))){committed=false;break;}
          const auto base=reinterpret_cast<addr_t>(part.BaseAddress);if(cursor<base||cursor-base>=part.RegionSize){committed=false;break;}
          const auto available=part.RegionSize-(cursor-base);cursor+=available<previous-cursor?available:previous-cursor;
        }
        if(committed&&page<previous){
          auto *native=VirtualAlloc(reinterpret_cast<void*>(page),previous-page,MEM_COMMIT,NativeProtection(protection));
          committed=native==reinterpret_cast<void*>(page);
          if(committed){auto current=control.committed.load(std::memory_order_acquire);while(page<current&&!control.committed.compare_exchange_weak(current,page,std::memory_order_acq_rel,std::memory_order_acquire)){} }
        }
        // An overlapping reader may already have satisfied this fault. Actual
        // native page state/protection is checked before resuming either way.
        MEMORY_BASIC_INFORMATION info{};
        if(committed&&VirtualQuery(reinterpret_cast<void*>(address),&info,sizeof(info))&&info.State==MEM_COMMIT&&
           info.AllocationBase==reinterpret_cast<void*>(r.reservation)&&!(info.Protect&PAGE_GUARD)&&
           (info.Protect&0xff)==NativeProtection(protection))result=EXCEPTION_CONTINUE_EXECUTION;
        else{control.fault_address.store(address,std::memory_order_relaxed);control.fault_failure.store(2,std::memory_order_release);}
      }
      control.phase.fetch_sub(1,std::memory_order_release);break;
    }
    recursion[slot].store(0,std::memory_order_release);return result;
  }
};
Manager &Enabled(){static Manager value;return value;}
}
void GrowdownMemory::Enable(){(void)Enabled();}
GrowdownMemory::AllocationGuard::AllocationGuard():lock_(allocation_mutex){}
GrowdownMemory::Control *GrowdownMemory::Reserve(uint64_t size,uint64_t generation,uint32_t &native_error){
  native_error=0;
  auto &state=Enabled();AllocationGuard allocation;std::lock_guard lock(state.creation);
  const auto index=state.lifetime.load(std::memory_order_relaxed);
  if(state.active.load(std::memory_order_acquire)>=kActiveLimit)throw std::runtime_error("unsupported growdown active-owner budget exhausted (128)");
  if(index>=kLifetimeLimit)throw std::runtime_error("unsupported growdown lifetime-control budget exhausted (4096)");
  if(!size||size%kPage||size>SIZE_MAX-kGap-kAdditional-kPage)throw std::runtime_error("unsupported growdown reservation size overflow");
  const auto total=kGap+kAdditional+size+kPage;
  auto *native=VirtualAlloc(nullptr,total,MEM_RESERVE,PAGE_NOACCESS);if(!native){native_error=GetLastError();return nullptr;}
  auto base=reinterpret_cast<addr_t>(native),low=base+kGap,initial=low+kAdditional,high=initial+size;
  if(VirtualAlloc(reinterpret_cast<void*>(initial),size,MEM_COMMIT,PAGE_READWRITE)!=reinterpret_cast<void*>(initial)){
    native_error=GetLastError();if(!VirtualFree(native,0,MEM_RELEASE)){std::fputs("growdown initial-commit rollback failed\n",stderr);std::abort();}return nullptr;
  }
  auto &control=state.controls[index];control.region={base,total,low,high,initial,initial,generation};
  control.committed.store(initial,std::memory_order_relaxed);control.protection.store(3,std::memory_order_relaxed);control.phase.store(kClosed,std::memory_order_relaxed);control.publication.store(kReserved,std::memory_order_release);
  state.active.fetch_add(1,std::memory_order_release);state.lifetime.store(index+1,std::memory_order_release);return &control;
}
GrowdownMemory::Region GrowdownMemory::Inspect(const Control *control) noexcept {auto result=control->region;result.committed=control->committed.load(std::memory_order_acquire);return result;}
void GrowdownMemory::Publish(Control *control) noexcept {control->phase.store(0,std::memory_order_release);control->publication.store(kLive,std::memory_order_release);}
bool GrowdownMemory::HasFaultReaders(const Control *control) noexcept {return (control->phase.load(std::memory_order_acquire)&~kClosed)!=0;}
void GrowdownMemory::Close(Control *control){uint64_t expected=0;if(!control->phase.compare_exchange_strong(expected,kClosed,std::memory_order_acq_rel,std::memory_order_acquire))throw std::runtime_error("unsupported growdown mutation concurrent with native fault reader");}
void GrowdownMemory::Reopen(Control *control) noexcept {control->phase.store(0,std::memory_order_release);}
bool GrowdownMemory::ProtectClosed(Control *control,int protection) noexcept {
  auto r=Inspect(control);DWORD old=0;
  if(!VirtualProtect(reinterpret_cast<void*>(r.committed),r.high-r.committed,NativeProtection(protection),&old))return false;
  control->protection.store(protection,std::memory_order_release);return true;
}
bool GrowdownMemory::ReleaseClosed(Control *control,uint32_t *native_error) noexcept {
  AllocationGuard allocation;
  if(!VirtualFree(reinterpret_cast<void*>(control->region.reservation),0,MEM_RELEASE)){if(native_error)*native_error=GetLastError();return false;}
  control->publication.store(kRetired,std::memory_order_release);manager.load(std::memory_order_acquire)->active.fetch_sub(1,std::memory_order_release);return true;
}
GrowdownMemory::Collision GrowdownMemory::FixedCollision(addr_t address,uint64_t size) noexcept {
  auto *state=manager.load(std::memory_order_acquire);if(!state||!size)return Collision::None;bool reserved=false;
  auto count=state->lifetime.load(std::memory_order_acquire);
  for(uint32_t i=0;i<count;++i){auto &control=state->controls[i];const auto publication=control.publication.load(std::memory_order_acquire);if(publication!=kLive&&publication!=kReserved)continue;const auto &r=control.region;
    if(!Intersects(address,size,r.reservation,r.reservation_size))continue;
    const auto low=control.committed.load(std::memory_order_acquire);if(Intersects(address,size,low,r.high-low))return Collision::Committed;reserved=true;
  }
  return reserved?Collision::Reserved:Collision::None;
}
}

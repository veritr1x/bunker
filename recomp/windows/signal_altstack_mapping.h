#pragma once
#include "signal_host.h"
#include <atomic>
#include <map>
#include <mutex>
#include <stdexcept>
#ifdef _WIN32
#include "filesystem.h"
#else
#include <sys/mman.h>
#endif
// Component owner backend. Windows uses the production FileSystem lease;
// Linux physically owns mmap allocations and serializes every mutator with pin.
class AltMappings {
 public:
#ifdef _WIN32
  bunker::windows::FileSystem files;
  addr_t Map(uint64_t size,addr_t at=0){auto p=files.Mmap(at,size,3,at?0x100022:0x22,-1,0);if(p==UINT64_MAX)throw std::runtime_error("test mmap failed");return p;}
  void Unmap(addr_t p,uint64_t size){if(files.Munmap(p,size))throw std::runtime_error("test munmap failed");}
  void Protect(addr_t p,uint64_t size,bool writable){if(files.Mprotect(p,size,writable?3:1))throw std::runtime_error("test mprotect failed");}
  std::optional<bunker::windows::SignalHost::StackRegion> Region(addr_t p,size_t size){auto r=files.MappingRegion(p,size,true);if(!r)return {};return bunker::windows::SignalHost::StackRegion{r->base,r->base+r->size,r->generation};}
  std::optional<bunker::windows::SignalHost::StackLease> Acquire(addr_t p,size_t size,uint64_t generation){auto use=files.AcquireMappingUse(p,size,true);if(!use||use->region.generation!=generation)return {};return bunker::windows::SignalHost::StackLease{{use->region.base,use->region.base+use->region.size,use->region.generation},use->lease};}
#else
  struct Control {std::atomic<unsigned> uses{0};};
  struct Mapping {size_t size;uint64_t generation;bool writable;std::shared_ptr<Control> control;};
  std::mutex mutex;std::map<addr_t,Mapping> mappings;uint64_t next_generation=1;
  ~AltMappings(){for(auto &[p,m]:mappings){if(m.control->uses.load())std::abort();::munmap(reinterpret_cast<void*>(p),m.size);}}
  addr_t Map(uint64_t size,addr_t at=0){std::lock_guard lock(mutex);size=(size+4095)&~uint64_t(4095);void *p=::mmap(reinterpret_cast<void*>(at),size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|(at?MAP_FIXED_NOREPLACE:0),-1,0);if(p==MAP_FAILED)throw std::runtime_error("test mmap failed");auto address=reinterpret_cast<addr_t>(p);recomp::InvalidateGuestMemory(address,size);mappings.emplace(address,Mapping{size,next_generation++,true,std::make_shared<Control>()});return address;}
  void Unmap(addr_t p,uint64_t size){std::lock_guard lock(mutex);size=(size+4095)&~uint64_t(4095);auto i=mappings.find(p);if(i==mappings.end()||i->second.size!=size)throw std::runtime_error("test unknown munmap");if(i->second.control->uses.load())throw std::runtime_error("active mapping use prevents munmap");recomp::WithGuestMemoryWrite(p,size,[&]{if(::munmap(reinterpret_cast<void*>(p),size))throw std::runtime_error("test munmap failed");});mappings.erase(i);}
  void Protect(addr_t p,uint64_t size,bool writable){std::lock_guard lock(mutex);size=(size+4095)&~uint64_t(4095);for(auto &[base,m]:mappings)if(p>=base&&p<=base+m.size&&size<=base+m.size-p){if(m.control->uses.load())throw std::runtime_error("active mapping use prevents mprotect");if(::mprotect(reinterpret_cast<void*>(p),size,writable?PROT_READ|PROT_WRITE:PROT_READ))throw std::runtime_error("test mprotect failed");m.writable=writable;return;}throw std::runtime_error("test unknown mprotect");}
  std::optional<bunker::windows::SignalHost::StackRegion> Region(addr_t p,size_t size){std::lock_guard lock(mutex);for(auto &[base,m]:mappings)if(m.writable&&p>=base&&p<=base+m.size&&size<=base+m.size-p)return bunker::windows::SignalHost::StackRegion{base,base+m.size,m.generation};return {};}
  std::optional<bunker::windows::SignalHost::StackLease> Acquire(addr_t p,size_t size,uint64_t generation){std::lock_guard lock(mutex);for(auto &[base,m]:mappings)if(m.writable&&m.generation==generation&&p>=base&&p<=base+m.size&&size<=base+m.size-p){
    struct Pin {std::shared_ptr<Control> control;explicit Pin(std::shared_ptr<Control> c):control(std::move(c)){++control->uses;}~Pin(){--control->uses;}};
    return bunker::windows::SignalHost::StackLease{{base,base+m.size,m.generation},std::make_shared<Pin>(m.control)};}return {};}
#endif
};

#include "filesystem.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <map>
#include <memory>
#include <string>
#include <thread>
#include <vector>
#include <windows.h>
namespace {
using bunker::windows::FileSystem;
using namespace bunker::windows::linux_flags;
constexpr uint64_t kPage=4096,kGrowth=8u<<20,kGap=1u<<20,kInitial=0x40000;
constexpr int kFlags=0x20122;
std::atomic<unsigned long long> checks{0};
FileSystem *resolve_files;
void Check(bool condition,const char *why){if(!condition)throw std::runtime_error(why);++checks;}
void *Resolve(const char *name){return reinterpret_cast<void*>(resolve_files->Marker(name));}
bool Boundary(const std::function<void()> &call,const char *needle){try{call();}catch(const std::runtime_error &e){return std::string(e.what()).find(needle)!=std::string::npos;}return false;}
MEMORY_BASIC_INFORMATION Query(addr_t address){MEMORY_BASIC_INFORMATION m{};Check(VirtualQuery(reinterpret_cast<void*>(address),&m,sizeof(m))==sizeof(m),"real VirtualQuery succeeds");return m;}
struct Owner {addr_t initial,low,high,reservation;uint64_t generation,size;};
Owner Identify(FileSystem &files,addr_t p,uint64_t n){auto region=files.MappingRegion(p,n,true);Check(region&&region->base==p-kGrowth&&region->size==kGrowth+((n+kPage-1)&~(kPage-1))&&region->generation,"valid initial span exposes fixed usable owner bounds and generation");return {p,region->base,region->base+region->size,region->base-kGap,region->generation,n};}
void Identity(FileSystem &files,const Owner &o,addr_t address,uint64_t size,bool writable=true){auto r=files.MappingRegion(address,size,writable);Check(r&&r->base==o.low&&r->base+r->size==o.high&&r->generation==o.generation,"growth/protection preserves complete owner identity and generation");}
addr_t CurrentLow(const Owner &o){
  // VirtualQuery describes forward from the queried page; querying initial P
  // cannot reveal an earlier committed prefix. Walk the known usable window.
  for(auto cursor=o.low;cursor<=o.initial;){auto q=Query(cursor);Check(q.AllocationBase==reinterpret_cast<void*>(o.reservation),"current span belongs to original native reservation");if(q.State==MEM_COMMIT)return cursor;const auto next=reinterpret_cast<addr_t>(q.BaseAddress)+q.RegionSize;Check(q.State==MEM_RESERVE&&next>cursor&&next<=o.initial,"reserved prefix has exact forward native bounds");cursor=next;}
  throw std::runtime_error("initial committed page disappeared");
}
void Guards(const Owner &o){for(auto address:{o.reservation,o.low-1,o.high}){auto q=Query(address);Check(q.AllocationBase==reinterpret_cast<void*>(o.reservation)&&q.State==MEM_RESERVE&&q.Protect==0,"permanent gap/top guard remains reserved and inaccessible");}}
struct Guest {
  FileSystem &files;recomp::Runtime runtime,bridges;elf_image image{};
  explicit Guest(FileSystem &f,bool production=false):files(f){
    resolve_files=&f;Check(!elf_load(GROWTH_LIBRARY,0x7b000000,Resolve,&image),"actual NDK growth fixture maps");if(production){f.Install(runtime);}else{f.Install(bridges);
    // Unsupported native APIs stop at the actual import boundary. Never let a
    // C++ diagnostic unwind through a lifted nounwind runtime intrinsic.
    for(const char *name:{"mmap","munmap","mprotect","__errno"}){auto marker=f.Marker(name);runtime.AddImport(marker,[this,marker,name](State &state){try{bridges.Dispatch(state,marker,nullptr);}catch(const std::exception &e){std::fprintf(stderr,"growth fixture %s: %s\n",name,e.what());std::fflush(stderr);std::abort();}});}
    }runtime.AddTraces(kTraces,std::size(kTraces));
  }
  addr_t Run(const char *name,std::initializer_list<addr_t> args={}){
    alignas(16)std::array<uint8_t,65536> stack{};State state{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t i=0;for(auto a:args)(state.gpr.*r[i++]).qword=a;
    const auto high=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.sp.qword=high;state.gpr.x30.qword=0xfeedffff;state.gpr.x20.qword=0x123456789abcdef0ULL;
    runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,name)));
    Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==high&&state.gpr.x20.qword==0x123456789abcdef0ULL,"NDK faulting caller preserves real PC/SP/callee-saved state");return state.gpr.x0.qword;
  }
  addr_t Map(uint64_t size=kInitial){auto p=Run("growth_map",{size,kFlags});Check(p!=UINT64_MAX,"actual original-shape NDK mmap succeeds only after explicit opt-in");return p;}
  uint64_t Read(addr_t p){return Run("growth_read",{p});}
  void Write(addr_t p,uint64_t value){Run("growth_write",{p,value});}
};
void RawWrite(addr_t p,uint64_t value){*reinterpret_cast<volatile uint64_t*>(p)=value;}
int Budgets(const std::string &mode){
  FileSystem a,b;a.EnableGrowdownMappings();b.EnableGrowdownMappings();
  if(mode=="--active-budget"){
    std::vector<std::pair<FileSystem*,Owner>> owners;
    for(unsigned i=0;i<128;++i){auto &f=i&1?b:a;auto p=f.Mmap(0,kPage,3,kFlags,-1,0);Check(p!=UINT64_MAX,"real active-budget reservation succeeds");owners.push_back({&f,Identify(f,p,kPage)});}
    b.SetError(73);Check(Boundary([&]{b.Mmap(0,kPage,3,kFlags,-1,0);},"active-owner budget exhausted (128)")&&b.Error()==73,"process-wide active budget is explicit and preserves errno");
    auto removed=owners.back();owners.pop_back();Check(!removed.first->Munmap(removed.second.initial,kPage),"retirement returns one actual active budget slot");auto p=b.Mmap(0,kPage,3,kFlags,-1,0);Check(p!=UINT64_MAX,"other filesystem can use released global active slot");Check(!b.Munmap(p,kPage),"replacement active slot retires");for(auto &[f,o]:owners)Check(!f->Munmap(o.initial,kPage),"all active reservations retire");
  }else{
    uint64_t previous=0;for(unsigned i=0;i<4096;++i){auto p=a.Mmap(0,kPage,3,kFlags,-1,0);Check(p!=UINT64_MAX,"real lifetime-budget reservation succeeds");auto o=Identify(a,p,kPage);Check(o.generation>previous,"each real lifetime has a fresh generation");previous=o.generation;Check(!a.Munmap(p,kPage),"lifetime record retires without being reused");}
    a.SetError(79);Check(Boundary([&]{a.Mmap(0,kPage,3,kFlags,-1,0);},"lifetime-control budget exhausted (4096)")&&a.Error()==79,"process lifetime-control limit is explicit after real4096 retirements");auto ordinary=a.Mmap(0,kPage,3,map_private|map_anonymous,-1,0);Check(ordinary!=UINT64_MAX&&!a.Munmap(ordinary,kPage),"growth budget does not disable ordinary mappings");
  }
  std::printf("PASS %s checks=%llu; fresh process and real reserved owners\n",mode.c_str(),checks.load());return 0;
}
int Negative(const std::string &mode,bool production=false){
  if(mode=="--active-budget"||mode=="--lifetime-budget")return Budgets(mode);
  auto files=std::make_unique<FileSystem>();if(mode!="--default-disabled")files->EnableGrowdownMappings();Guest guest(*files,production);
  if(mode=="--default-disabled"){guest.Map();throw std::runtime_error("disabled growth unexpectedly returned");}
  const auto p=guest.Map();auto owner=Identify(*files,p,kInitial);
  // BEGIN PRODUCTION PINNED TRANSPORT
  if(mode=="--pinned-unmap"||mode=="--pinned-protect"){guest.Write(p-kPage,23);auto pin=files->AcquireMappingUse(p,kInitial,true);Check(pin&&pin->lease,"production negative holds a real physical growth pin");auto low=CurrentLow(owner);if(mode=="--pinned-unmap")guest.Run("growth_unmap",{low,owner.high-low});else guest.Run("growth_protect",{low,owner.high-low,1});throw std::runtime_error("pinned production mutation unexpectedly returned");}
  // END PRODUCTION PINNED TRANSPORT
  if(mode=="--destroy-pinned"){auto pin=files->AcquireMappingUse(p,kInitial,true);Check(pin&&pin->lease,"real growth owner pin exists");files.reset();return 98;}
  if(mode=="--partial-unmap"){guest.Write(p-kPage,5);guest.Run("growth_unmap",{p,kInitial});return 97;}
  if(mode=="--partial-protect"){guest.Write(p-kPage,5);guest.Run("growth_protect",{p,kInitial,1});return 96;}
  if(mode=="--reserved-noreplace"){guest.Run("growth_map_at",{owner.low,kPage,3,uint64_t(map_private|map_anonymous|map_fixed_no_replace)});return 95;}
  addr_t fault=0;
  if(mode=="--lower-guard")fault=owner.low-kPage;
  else if(mode=="--limit-beyond-gap")fault=owner.reservation;
  else if(mode=="--upper-guard")fault=owner.high;
  else if(mode=="--ro-write"||mode=="--ro-growth-write"){if(mode=="--ro-write")guest.Write(p-kPage,17);const auto current=CurrentLow(owner);Check(!files->Mprotect(current,owner.high-current,1),"actual owner becomes read-only");fault=p-kPage;}
  else if(mode=="--noaccess-read"){guest.Write(p-kPage,19);Check(!files->Mprotect(p-kPage,kInitial+kPage,0),"actual grown owner becomes inaccessible");fault=p-kPage;}
  else if(mode=="--foreign-fault"){fault=reinterpret_cast<addr_t>(VirtualAlloc(nullptr,65536,MEM_RESERVE,PAGE_NOACCESS));Check(fault,"foreign native reservation exists outside provider ownership");}
  else if(mode=="--retired-fault"){
    Check(!files->Munmap(p,kInitial),"real owner retires before stale access");auto native=VirtualAlloc(reinterpret_cast<void*>(owner.reservation),kGap+kGrowth+kInitial+kPage,MEM_RESERVE,PAGE_NOACCESS);Check(native==reinterpret_cast<void*>(owner.reservation),"same exact physical address is re-reserved without a provider owner");fault=p-kPage;
  }else if(mode=="--execute-fault"){
    std::fprintf(stderr,"EXPECTED native instruction-fetch AV on committed non-executable RW owner address=%#llx\n",(unsigned long long)p);std::fflush(stderr);reinterpret_cast<void(*)()>(p)();return 94;
  }else throw std::runtime_error("unknown negative mode");
  auto q=Query(fault);std::fprintf(stderr,"EXPECTED native AV mode=%s address=%#llx state=%#lx protection=%#lx; no repair permitted\n",mode.c_str(),(unsigned long long)fault,q.State,q.Protect);std::fflush(stderr);
  if(mode=="--noaccess-read")guest.Read(fault);else guest.Write(fault,0x55);return 93;
}
// BEGIN PRODUCTION NORMAL TRANSPORT
int ProductionNormal(){
  FileSystem files;files.EnableGrowdownMappings();Guest guest(files,true);files.SetError(43);
  auto p=guest.Run("growth_map_at",{0,8192,3,uint64_t(map_private|map_anonymous)});Check(p!=UINT64_MAX&&guest.Run("growth_errno")==43,"actual production mmap success preserves guest errno");guest.Write(p,0xabcd1234);
  Check(!guest.Run("growth_protect",{p,8192,1})&&guest.Read(p)==0xabcd1234&&!files.MappingRegion(p,8192,true)&&guest.Run("growth_errno")==43,"actual production mprotect returns real RO state/data/errno");
  Check(!guest.Run("growth_protect",{p,8192,3})&&!guest.Run("growth_unmap",{p,8192})&&guest.Run("growth_errno")==43,"actual production full unmap and RW restore preserve ABI/errno");
  Check(guest.Run("growth_map_at",{1,kPage,3,uint64_t(map_private|map_anonymous|map_fixed_no_replace)})==UINT64_MAX&&guest.Run("growth_errno")==22,"actual production invalid request returns MAP_FAILED and genuine guest EINVAL");
  auto g=guest.Map(8192);Check(guest.Run("growth_errno")==22,"actual production enabled original-shape mmap does not invent errno reset");
  Check(!guest.Run("growth_protect",{g,8192,1})&&!guest.Run("growth_protect",{g,8192,3})&&!guest.Run("growth_unmap",{g,8192})&&guest.Run("growth_errno")==22,"actual production growth-owner API transport preserves normal return/errno");
  std::printf("PASS production FS.Install normal transport: %llu checks; real NDK mmap/mprotect/munmap/errno, no fixture import forwarding fence\n",checks.load());return 0;
}
// END PRODUCTION NORMAL TRANSPORT
}
int main(int argc,char **argv){try{
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
  // BEGIN PRODUCTION MODE DISPATCH
  if(argc>1&&std::string(argv[1])=="--production-normal")return ProductionNormal();
  if(argc>1&&std::string(argv[1]).rfind("--production-",0)==0)return Negative("--"+std::string(argv[1]).substr(13),true);
  // END PRODUCTION MODE DISPATCH
  if(argc>1)return Negative(argv[1]);
  FileSystem files;files.EnableGrowdownMappings();Guest guest(files);const auto p=guest.Map();auto owner=Identify(files,p,kInitial);Guards(owner);
  Check(CurrentLow(owner)==p&&Query(owner.low).State==MEM_RESERVE&&!files.MappingRegion(owner.low,8,true),"extra capacity is genuinely reserved, not precommitted or reported readable");
  const uint64_t first=0x0123456789abcdefULL,last=0xfedcba9876543210ULL;guest.Write(p,first);guest.Write(owner.high-8,last);
  SetLastError(0x51715171);const auto native_zero=*reinterpret_cast<volatile uint64_t*>(p-kPage);const auto error=GetLastError();Check(!native_zero&&error==0x51715171,"real raw read AV grows zero page and preserves native LastError");Identity(files,owner,p-kPage,kPage);Check(CurrentLow(owner)==p-kPage,"first actual AV extends exactly one page");
  auto pin=files.AcquireMappingUse(p,kInitial,true);Check(pin&&pin->lease&&pin->region.base==owner.low&&pin->region.generation==owner.generation,"lease pins entire fixed growth owner");guest.Write(p-2*kPage,0x2222);Check(guest.Read(p-2*kPage)==0x2222,"translated Runtime write/read AV works while whole-owner lease is active");
  Check(guest.Run("growth_exclusive",{p-3*kPage,0x3333})==0&&guest.Read(p-3*kPage)==0x3333,"real NDK LDAXR/STLXR first-touch fault succeeds under Runtime memory lock");
  auto reservation=bunker::test::ReserveAcrossOperation(p,8,[&]{Check(guest.Read(p-4*kPage)==0,"different native worker grows through actual translated read");});Check(reservation.status==0&&reservation.loaded==first,"growth commits do not invalidate an unrelated existing guest exclusive reservation");
  const auto low=CurrentLow(owner);files.SetError(83);Check(Boundary([&]{files.Munmap(low,owner.high-low);},"active mapping use")&&Boundary([&]{files.Mprotect(low,owner.high-low,1);},"active mapping use")&&files.Error()==83,"real physical lease prevents destructive native mutation without errno changes");pin.reset();
  Check(Boundary([&]{files.Munmap(p,kInitial);},"partial munmap")&&Boundary([&]{files.Mprotect(p,kInitial,1);},"partial mprotect"),"original256KiB cleanup cannot free/protect a grown partial logical span");Identity(files,owner,p,kInitial);
  files.SetError(89);Check(Boundary([&]{files.Mmap(owner.low,kPage,3,map_private|map_anonymous|map_fixed_no_replace,-1,0);},"reserved-only")&&files.Error()==89,"reserved-only capacity is a named NOREPLACE boundary, not fake EEXIST");
  Check(files.Mmap(p,kPage,3,map_private|map_anonymous|map_fixed_no_replace,-1,0)==UINT64_MAX&&files.Error()==17&&guest.Read(p)==first,"real committed overlap gives genuine EEXIST and preserves bytes");
  std::map<addr_t,uint64_t> values{{p-kPage,0},{p-2*kPage,0x2222},{p-3*kPage,0x3333},{p-4*kPage,0}};addr_t previous=CurrentLow(owner);
  for(uint64_t depth:{uint64_t(65536),uint64_t(524288),uint64_t(2u<<20),kGrowth}){
    constexpr unsigned count=16;std::array<addr_t,count> addresses{};std::atomic<unsigned> ready{0};std::atomic<bool> go{false};std::vector<std::thread> workers;
    for(unsigned i=0;i<count;++i){addresses[i]=p-depth+(i%8)*kPage+(i/8)*8;values[addresses[i]]=0xc0000000+i+depth;workers.emplace_back([&,i]{++ready;while(!go.load(std::memory_order_acquire))SwitchToThread();if(i&1)RawWrite(addresses[i],0xc0000000+i+depth);else guest.Write(addresses[i],0xc0000000+i+depth);});}
    while(ready.load(std::memory_order_acquire)!=count){SwitchToThread();}
    go.store(true,std::memory_order_release);for(auto &worker:workers)worker.join();
    const auto now=CurrentLow(owner);Check(now==p-depth,"concurrent actual native/translated faults commit complete overlapping prefixes");
    for(addr_t a=now;a<previous;a+=8){auto found=values.find(a);auto expected=found==values.end()?0:found->second;if(*reinterpret_cast<const uint64_t*>(a)!=expected)throw std::runtime_error("new prefix was not zero outside actual concurrent stores");}++checks;
    for(const auto &[a,value]:values)Check(guest.Read(a)==value,"all previous and concurrent fault-page canaries survive overlapping commit");
    Check(guest.Read(p)==first&&guest.Read(owner.high-8)==last,"all initial committed-byte canaries survive repeated overlap");Identity(files,owner,now,owner.high-now);Guards(owner);previous=now;
  }
  Check(CurrentLow(owner)==owner.low,"full configured8MiB additional limit is genuinely usable");
  Check(!guest.Run("growth_protect",{owner.low,owner.high-owner.low,1})&&!files.MappingRegion(p,kInitial,true)&&files.MappingRegion(p,kInitial,false).has_value(),"full current-span RO change affects real writable query without losing identity");Identity(files,owner,p,kInitial,false);Check(guest.Read(p)==first&&Query(p).Protect==PAGE_READONLY,"real RO page remains readable and retains existing bytes");
  Check(!guest.Run("growth_protect",{owner.low,owner.high-owner.low,3}),"full current span restores RW");
  auto old_generation=owner.generation;reservation=bunker::test::ReserveAcrossOperation(p,8,[&]{Check(!files.Munmap(owner.low,owner.high-owner.low),"exact full-current-span unmap retires complete native reservation");});Check(reservation.status==1,"real unmap invalidates existing guest reservation before stale STXR");Check(!files.MappingRegion(p,kInitial,false)&&Query(owner.reservation).State==MEM_FREE,"retired owner is absent and entire physical reservation/gaps are freed");
  auto replacement=files.Mmap(p,kInitial,3,map_private|map_anonymous|map_fixed_no_replace,-1,0);Check(replacement==p,"same original pointer acquires a new actual ordinary mapped lifetime");auto fresh=files.MappingRegion(replacement,kInitial,true);Check(fresh&&fresh->generation!=old_generation&&fresh->base==p,"same-address reuse has distinct generation and cannot retain stale growth ownership");Check(!files.Munmap(replacement,kInitial),"replacement owner retires normally");
  // Read-only growth uses real read faults, while writes stay fatal in separate processes.
  auto q=guest.Map(8192);auto ro=Identify(files,q,8192);guest.Write(q,0x9911);Check(!files.Mprotect(q,8192,1),"fresh owner is made RO before growth");Check(!guest.Read(q-kPage)&&Query(q-kPage).Protect==PAGE_READONLY&&guest.Read(q)==0x9911,"read AV grows a genuinely RO prefix without healing write protection or losing bytes");Identity(files,ro,q-kPage,kPage,false);Check(!files.MappingRegion(q-kPage,kPage,true)&&!files.Munmap(q-kPage,ro.high-(q-kPage)),"RO growth full-current cleanup remains exact");
  addr_t retired_base=0;{FileSystem scoped;scoped.EnableGrowdownMappings();auto a=scoped.Mmap(0,kPage,3,kFlags,-1,0);auto o=Identify(scoped,a,kPage);retired_base=o.reservation;RawWrite(a-kPage,11);Check(*reinterpret_cast<uint64_t*>(a-kPage)==11,"scoped real owner actually faults before destructor retirement");}Check(Query(retired_base).State==MEM_FREE,"FileSystem destructor safely retires live growth owner and reservation");
  std::printf("PASS real growdown: %llu checks; actual native AV and strict NDK Runtime read/write/LDAXR-STLXR, concurrent overlap, zero/canaries, ownership/protection/pins/retirement; no game/frame/GC claim\n",checks.load());return 0;
}catch(const std::exception &e){std::fprintf(stderr,"growdown test: %s\n",e.what());return 1;}}

#include "signal_delivery.h"
#include "signal_altstack_fixture.h"
#include "signal_altstack_mapping.h"
#include "../whole/bridge.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <future>
#include <thread>
using namespace bunker::windows;
namespace {
constexpr uint64_t kSize=0x40000;constexpr addr_t kErrno=0x7ffc48000000ULL,kDispatch=kErrno+8,kNested=kErrno+16,kGuards=kErrno+24;
unsigned checks=0;thread_local int guest_error;SignalHost *resolver_model;
void Check(bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;}
bool Executable(addr_t p){for(auto &t:kTraces)if(t.address==p)return true;return false;}
void *Resolve(const char *n){if(!std::strcmp(n,"__errno"))return reinterpret_cast<void*>(kErrno);if(!std::strcmp(n,"TEST_alt_dispatch"))return reinterpret_cast<void*>(kDispatch);if(!std::strcmp(n,"TEST_alt_nested"))return reinterpret_cast<void*>(kNested);if(!std::strcmp(n,"TEST_alt_lease_guards"))return reinterpret_cast<void*>(kGuards);return reinterpret_cast<void*>(resolver_model->Marker(n));}
template<class T>void Put(T &out,const T &value){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&out),&value,sizeof(value));}
struct Harness {
  AltMappings maps;SignalHost *self=nullptr;bool provide_lease=true,reentrant=true;unsigned resolves=0,acquires=0;addr_t guard_stack=0;uint64_t guard_size=kSize;
  SignalHost model{ {},0x7ff600100000ULL,[this](addr_t p,size_t size){++resolves;if(self&&reentrant){Check(bool(self->Lookup(1)),"mapping resolver reenters model outside policy lock");}return maps.Region(p,size);},[this](addr_t p,size_t size,uint64_t gen)->std::optional<SignalHost::StackLease>{++acquires;if(self&&reentrant)Check(bool(self->Lookup(1)),"lease acquire reenters model outside policy lock");return provide_lease?maps.Acquire(p,size,gen):std::nullopt;} };
  recomp::Runtime runtime;elf_image image{};alignas(16)std::array<uint8_t,131072> normal{};SignalDelivery *delivery=nullptr;std::string failure;
  Harness(){self=&model;resolver_model=&model;Check(!model.RegisterThread(1)&&!model.BindCurrent(1),"live native current virtual thread bound");model.SetErrorSink([](int e){Put(guest_error,e);});
    model.Install(runtime,[]{return uint64_t(1);},[this](const SignalHost::Delivery&d){return delivery->Deliver(d);});runtime.AddTraces(kTraces,std::size(kTraces));
    runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
    auto dispatch=[this](int signal){try{Check(!model.Queue(1,signal),"controlled TEST signal queued");auto r=model.DispatchOne(1,[this](auto &d){return delivery->Deliver(d);});Check(!r.error&&r.handled,"controlled TEST frame returns normally");}catch(const std::exception&e){failure=e.what();}};
    runtime.AddImport(kDispatch,[dispatch](State&){dispatch(30);});runtime.AddImport(kNested,[dispatch](State&){dispatch(24);});
    runtime.AddImport(kGuards,[this](State&s){unsigned bits=0;try{maps.Unmap(guard_stack,guard_size);}catch(const std::runtime_error&){bits|=1;}try{maps.Protect(guard_stack,guard_size,false);}catch(const std::runtime_error&){bits|=2;}s.gpr.x0.qword=bits;});
    Check(!elf_load(ALT_LIBRARY,0x76000000,Resolve,&image),"real NDK altstack/handler ELF mapped");
  }
  addr_t Low(){return reinterpret_cast<addr_t>(normal.data());}addr_t High(){return Low()+normal.size();}
  addr_t Symbol(const char *n){auto p=reinterpret_cast<addr_t>(elf_symbol(&image,n));Check(Executable(p),"actual NDK symbol has translated trace");return p;}
  State Run(const char *n,std::initializer_list<addr_t> args={}){State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t i=0;for(auto a:args)(s.gpr.*r[i++]).qword=a;s.gpr.sp.qword=High();s.gpr.x30.qword=0xfeedffff;s.gpr.x20.qword=0x123456789abcdef0ULL;uint64_t v[]={0x1111222233334444ULL,0x5555666677778888ULL};std::memcpy(&s.simd.v[31],v,16);s.fpcr.rmode=kFPURoundUpInf;s.sr.ioc=1;auto entry=Symbol(n);runtime.Run(s,entry);Check(s.gpr.sp.qword==High()&&s.gpr.pc.qword==0xfeedffff,"actual NDK caller preserves normal SP/return");return s;}
  uint64_t Call(const AndroidSignalStack *set,AndroidSignalStack *old){return Run("alt_call",{reinterpret_cast<addr_t>(set),reinterpret_cast<addr_t>(old)}).gpr.x0.qword;}
};
}
int main(int argc,char **argv){
  Harness h;AndroidSignalStack old{},a{},b{},off{0,2,0,0};
  if(argc>1){
    a={h.maps.Map(kSize),0,0,kSize};std::string mode=argv[1];
    if(mode=="--autodisarm")a.flags=int32_t(0x80000000u);
    if(mode=="--onstack-input")a.flags=1;
    if(mode=="--unowned")a.pointer=0x1000;
    AndroidSignalStack *output=nullptr;
    if(mode=="--partial-output"){auto p=h.maps.Map(8192);h.maps.Protect(p+4096,4096,false);output=reinterpret_cast<AndroidSignalStack*>(p+4096-8);}
    h.Call(&a,output);throw std::runtime_error("expected altstack boundary returned");
  }
  auto ok=[&](uint64_t result){Check(uint32_t(result)==0&&uint32_t(result>>32)==71,"actual NDK success preserves errno");};
  auto fail=[&](uint64_t result,unsigned e){Check(uint32_t(result)==UINT32_MAX&&uint32_t(result>>32)==e,"actual NDK POSIX error/errno mapping");};
  Check(h.model.AltStack(999,0,nullptr,&old)==3,"unknown virtual token rejected");Check(!h.model.RegisterThread(3)&&h.model.AltStack(3,0,nullptr,&old)==1,"unbound virtual token rejected");std::atomic<int> foreign{0};std::thread wrong([&]{foreign=h.model.AltStack(1,0,nullptr,&old);});wrong.join();Check(foreign==1,"foreign native worker cannot inspect bound stack");Check(!h.model.DropThread(3),"unused virtual lifetime retired");
  struct Guard {uint64_t before;AndroidSignalStack value;uint64_t after;} wire;std::memset(&wire,0xa5,sizeof(wire));
  ok(h.Call(nullptr,&wire.value));Check(wire.value.pointer==0&&wire.value.flags==2&&wire.value.size==0&&wire.value.padding==0,"fresh disabled query writes all24zero-padded NDK bytes");Check(wire.before==0xa5a5a5a5a5a5a5a5ULL&&wire.after==wire.before,"query output guards unchanged");Check(h.resolves==0,"query never consults mapping resolver");
  a={h.maps.Map(kSize),0,0,kSize};b={h.maps.Map(kSize),0,0,kSize};h.guard_stack=a.pointer;
  ok(h.Call(&a,&old));Check(old.flags==2&&old.pointer==0&&old.size==0,"install returns real prior disabled state");Check(h.acquires==0,"installation takes snapshot only, not active-use lease");
  ok(h.Call(nullptr,&old));Check(old.pointer==a.pointer&&old.flags==0&&old.size==kSize,"query returns actual installed tuple");
  auto alias=b;ok(h.Call(&alias,&alias));Check(alias.pointer==a.pointer&&alias.flags==0&&alias.size==kSize,"new input snapshot precedes overlapping old output");ok(h.Call(nullptr,&old));Check(old.pointer==b.pointer,"aliased operation installed original input B");
  AndroidSignalStack tiny{a.pointer,0,0,5119},invalid{a.pointer,4,0,0};std::memset(&wire.value,0xa5,24);auto sentinel=wire.value;fail(h.Call(&tiny,&wire.value),12);Check(!std::memcmp(&sentinel,&wire.value,24),"ENOMEM leaves old output untouched");fail(h.Call(&invalid,&wire.value),22);Check(!std::memcmp(&sentinel,&wire.value,24),"EINVAL leaves old output untouched");
  const auto before_resolve=h.resolves;Check(h.model.AltStack(1,b.pointer+b.size,&invalid,&old)==1,"actual on-stack EPERM precedes invalid flags");Check(h.model.AltStack(1,b.pointer+b.size,&tiny,&old)==1,"on-stack EPERM precedes minimum size");Check(h.resolves==before_resolve,"priority errors never call owner resolver");Check(!h.model.AltStack(1,b.pointer,nullptr,&old)&&old.flags==0&&!h.model.AltStack(1,b.pointer+1,nullptr,&old)&&old.flags==1&&!h.model.AltStack(1,b.pointer+b.size,nullptr,&old)&&old.flags==1,"downward stack low-exclusive/high-inclusive query flags");
  ok(h.Call(&a,nullptr));ok(h.Call(&off,&old));Check(old.pointer==a.pointer,"disable returns prior actual tuple");ok(h.Call(nullptr,&old));Check(!old.pointer&&old.flags==2&&!old.size,"disable normalizes pointer/size");
  fail(h.Call(&a,reinterpret_cast<AndroidSignalStack*>(1)),14);ok(h.Call(nullptr,&old));Check(old.pointer==a.pointer,"invalid old output reports EFAULT after real installation commit");
  const auto before_input=h.resolves;fail(h.Call(reinterpret_cast<AndroidSignalStack*>(1),&old),14);Check(h.resolves==before_input,"bad new input fails before model/configuration work");
  Check(!h.model.RegisterThread(2,1),"child virtual lifetime registered from parent");std::atomic<bool> child_disabled{false};std::thread child([&]{AndroidSignalStack s{};child_disabled=!h.model.BindCurrent(2)&&!h.model.AltStack(2,0,nullptr,&s)&&s.flags==2&&!s.pointer&&!s.size;});child.join();Check(child_disabled,"new thread starts disabled despite enabled parent");Check(!h.model.DropThread(2)&&h.model.AltStack(2,0,nullptr,&old)==3,"dead token cannot query retired alternate state");
  ok(h.Call(&b,&old));ok(h.Call(&old,nullptr));h.maps.Unmap(b.pointer,kSize);ok(h.Call(nullptr,&old));Check(old.pointer==a.pointer,"valid A to B to saved A restoration survives unmap B");b={h.maps.Map(kSize),0,0,kSize};
  ok(h.Call(&off,nullptr));AndroidSignalStack prior{};ok(h.Call(nullptr,&prior));auto temporary=AndroidSignalStack{h.maps.Map(kSize),0,0,kSize};ok(h.Call(&temporary,nullptr));prior.flags=0;fail(h.Call(&prior,nullptr),12);h.maps.Unmap(temporary.pointer,kSize);
  const auto query_count=h.resolves;ok(h.Call(nullptr,&old));Check(old.pointer==temporary.pointer&&old.flags==0&&old.size==kSize&&h.resolves==query_count,"original restore ENOMEM then munmap preserves stale query without resolver/auto-clear");
  AltReport report{};h.Run("alt_handlers",{reinterpret_cast<addr_t>(&report),1});SignalDelivery boundary(h.runtime,Executable,h.Symbol("alt_return_boundary"),{h.Low(),h.High()},h.model,1);h.delivery=&boundary;
  h.Run("alt_entry");Check(!h.failure.empty()&&!report.outer_sp,"stale mapping delivery stops before guest handler/frame use");
  const auto stale_snapshot=h.model.AlternateStack(1);auto reused=h.maps.Map(kSize,temporary.pointer);Check(reused==temporary.pointer&&h.maps.Region(reused,kSize)->generation!=stale_snapshot.region->generation,"actual unmapped address reused with distinct physical allocation generation");
  std::vector<uint8_t> bytes(kSize,0x5a),after(kSize);recomp::WriteGuestMemory(reused,bytes.data(),bytes.size());h.failure.clear();h.Run("alt_entry");recomp::ReadGuestMemory(after.data(),reused,after.size());Check(!h.failure.empty()&&after==bytes&&!report.outer_sp,"same-address reused allocation rejects stale registered generation before frame writes");
  ok(h.Call(&a,nullptr));h.maps.Unmap(reused,kSize);h.provide_lease=false;h.failure.clear();recomp::WriteGuestMemory(a.pointer,bytes.data(),bytes.size());h.Run("alt_entry");recomp::ReadGuestMemory(after.data(),a.pointer,after.size());Check(h.failure.find("lease")!=std::string::npos&&after==bytes&&!report.outer_sp,"missing real lease rejects enabled delivery before frame writes");h.provide_lease=true;
  Put(report,AltReport{});h.failure.clear();h.guard_stack=a.pointer;h.guard_size=kSize;h.Run("alt_handlers",{reinterpret_cast<addr_t>(&report),1});auto resumed=h.Run("alt_entry");
  Check(h.failure.empty(),"leased outer/nested delivery completes");Check(report.outer_sp>a.pointer&&report.outer_sp<a.pointer+kSize&&report.nested_sp>=a.pointer&&report.nested_sp<report.outer_sp,"actual SA_ONSTACK switch and nested handler below current alternate SP");
  Check(report.outer_saved_sp>=h.Low()&&report.outer_saved_sp<=h.High()&&report.nested_saved_sp>a.pointer&&report.nested_saved_sp<report.outer_frame,"normal and alternate interrupted bounds are restored separately");
  Check(report.outer_raw_flags==0&&report.nested_raw_flags==0&&report.outer_query_flags==1&&report.nested_query_flags==1,"uc_stack raw configuration differs from live query SS_ONSTACK");
  Check(report.onstack_result==UINT32_MAX&&report.onstack_errno==1&&report.onstack_old_unchanged&&report.nested_onstack_result==UINT32_MAX&&report.nested_onstack_errno==1&&report.nested_old_unchanged,"actual NDK on-stack EPERM precedence and untouched error output");
  Check(report.nested_count==1&&report.lease_guards==3,"physical active mapping owner rejects both unmap and protection while frames run");
  uint64_t vectors[2];std::memcpy(vectors,&resumed.simd.v[31],16);Check(report.root==0x123456789abcdef0ULL&&resumed.gpr.x20.qword==report.root&&vectors[0]==0x1111222233334444ULL&&vectors[1]==0x5555666677778888ULL&&resumed.fpcr.rmode==kFPURoundUpInf&&resumed.sr.ioc,"actual GPR/SIMD/FP state preserved through alternate and nested normal returns");
  ok(h.Call(nullptr,&old));Check(old.pointer==a.pointer&&old.flags==0,"nested return preserves unchanged registration without public on-stack replacement");
  Put(report,AltReport{});report.mode=1;report.replacement=b.pointer;report.replacement_size=kSize;h.Run("alt_handlers",{reinterpret_cast<addr_t>(&report),0});h.failure.clear();h.Run("alt_entry");Check(h.failure.empty()&&report.outer_sp>=h.Low()&&report.outer_sp<h.High()&&report.outer_query_flags==0,"non-SA_ONSTACK handler stays on actual normal stack");Check(report.changed_result==0&&report.changed_query==b.pointer&&report.lease_guards==3,"normal-stack handler can install B while saved A remains truly pinned");ok(h.Call(nullptr,&old));Check(old.pointer==a.pointer&&old.flags==0,"normal return coherently restores saved uc_stack A rather than retaining handler B");
  h.maps.Protect(a.pointer,kSize,false);Put(report,AltReport{});h.Run("alt_handlers",{reinterpret_cast<addr_t>(&report),1});h.failure.clear();h.Run("alt_entry");Check(h.failure.find("writable")!=std::string::npos&&!report.outer_sp,"registered but nonwritable storage stops before frame/handler use");h.maps.Protect(a.pointer,kSize,true);
  auto small=AndroidSignalStack{h.maps.Map(5120),0,0,5120};ok(h.Call(&small,nullptr));h.guard_stack=small.pointer;h.guard_size=5120;Put(report,AltReport{});h.Run("alt_handlers",{reinterpret_cast<addr_t>(&report),1});h.failure.clear();h.Run("alt_entry");Check(h.failure.find("does not fit")!=std::string::npos&&report.outer_sp&&report.nested_count==0,"nested frame capacity is checked before out-of-range write; minimum alone is not arbitrary handler capacity");
  ok(h.Call(&off,nullptr));h.maps.Unmap(small.pointer,5120);h.maps.Unmap(a.pointer,kSize);h.maps.Unmap(b.pointer,kSize);Check(!h.model.DropThread(1),"real virtual-thread lifetime retires configured state");
  std::printf("Alternate signal stack: %u checks passed; real NDK wire/install/query, physical mapping leases, alternate/nested delivery and restoration; no production GC\n",checks);
}

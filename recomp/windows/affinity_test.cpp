#include <cfenv>
#include "thread_affinity.h"
#include "affinity_fixture.h"
#include "../whole/bridge.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <windows.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <stdexcept>
#include <vector>
using namespace bunker::windows;
static thread_local int guest_error;
static std::atomic<unsigned> checks{0},ndk_records{0};
static void Check(bool yes,const char*why){++checks;if(!yes)throw std::runtime_error(why);}
template<class F>static void Reject(F f,const char*needle){bool caught=false;try{f();}catch(const std::exception&e){caught=std::strstr(e.what(),needle)!=nullptr;}Check(caught,needle);}
static bool Translated(addr_t address){for(const auto&t:kTraces)if(t.address==address)return true;return false;}
struct Harness;static Harness *current;static void *Resolve(const char*);
static GROUP_AFFINITY NativeGroup(HANDLE handle){GROUP_AFFINITY g{};Check(GetThreadGroupAffinity(handle,&g)!=0,"real native group query");return g;}
static uint64_t ProcessMask(){DWORD_PTR mask=0,system=0;Check(GetProcessAffinityMask(GetCurrentProcess(),&mask,&system)!=0,"real native process/system masks");Check(mask&&system,"actual nonempty allowed CPU masks");return uint64_t(mask)&uint64_t(system);}
struct Harness {
 recomp::Runtime runtime,provider;Pthreads threads{runtime,Translated};
 ThreadAffinities affinity{threads,ThreadAffinities::Profile::WindowsSingleGroupNativeIndices,0x7ff600600000ULL,[this](const auto&o){observations.push_back(o);errno=882;SetLastError(883);std::fesetround(FE_UPWARD);std::feraiseexcept(FE_INVALID);}};
 elf_image image{};std::mutex mutex;std::condition_variable condition;bool entered=false,released=false;
 uint32_t tid=0;uint64_t token=0;GROUP_AFFINITY initial{};
 std::vector<std::array<uint64_t,7>> raw_arguments;std::vector<ThreadAffinities::Observation> observations;
 Harness(){
  current=this;runtime.AddTraces(kTraces,std::size(kTraces));threads.Self();threads.Install();affinity.SetErrorSink([](int e){guest_error=e;});affinity.Install(provider);
  runtime.AddImport(affinity.Marker("syscall"),[this](State&s){raw_arguments.push_back({s.gpr.x0.qword,s.gpr.x1.qword,s.gpr.x2.qword,s.gpr.x3.qword,s.gpr.x4.qword,s.gpr.x5.qword,s.gpr.x6.qword});provider.Dispatch(s,affinity.Marker("syscall"),nullptr);});
  runtime.AddImport(0x7ffc76000000ULL,recomp::MakeBridge<addr_t()>([]{return reinterpret_cast<addr_t>(&guest_error);}));
  runtime.AddImport(0x7ffc76000008ULL,recomp::MakeBridge<void(addr_t)>([this](addr_t p){AffinityWorker record{};recomp::ReadGuestMemory(&record,p,sizeof(record));Check(record.tid==GetCurrentThreadId()&&record.tid==uint32_t(threads.GetTid())&&record.token==threads.Self(),"actual translated owned worker identity");initial=NativeGroup(GetCurrentThread());std::unique_lock lock(mutex);tid=record.tid;token=record.token;entered=true;condition.notify_all();condition.wait(lock,[&]{return released;});}));
  Check(!elf_load(AFFINITY_LIBRARY,0x5c000000,Resolve,&image),"actual NDK shared object loaded");
 }
 ~Harness(){threads.Shutdown();threads.ReleaseCurrent();if(image.base){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(image.base),image.span);VirtualFree(image.base,0,MEM_RELEASE);std::free(const_cast<uint8_t*>(image.file));}}
 addr_t Entry(const char *name){auto p=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(p!=0,"actual NDK symbol");return p;}
 addr_t Run(const char*name,std::initializer_list<addr_t>args){return threads.Run(Entry(name),args);}
 void Record(const AffinityRecord&r,int64_t value,int error){Check(r.before==0x1122334455667788ULL&&r.after==0x8877665544332211ULL&&r.padding==0x55aacc33&&r.value==value&&r.error==error,"strict NDK long64/errno/canary record");++ndk_records;}
 void Probe(unsigned id,int32_t target,addr_t mask,int64_t value,int error){for(int form=0;form<2;++form){AffinityRecord r{};Run("affinity_probe",{122,uint32_t(target),4,mask,static_cast<addr_t>(form),reinterpret_cast<addr_t>(&r)});Record(r,value,error);Check(raw_arguments.back()[0]==122&&uint32_t(raw_arguments.back()[1])==uint32_t(target)&&raw_arguments.back()[2]==4&&raw_arguments.back()[3]==mask&&raw_arguments.back()[4]==UINT64_MAX&&raw_arguments.back()[5]==0xbabe&&raw_arguments.back()[6]==UINT64_MAX,"actual seven GP syscall registers/tails");std::printf("WINDOWS-AFFINITY %u form=%d value=%lld errno=%d\n",id,form,(long long)r.value,r.error);}}
};
static void *Resolve(const char *name){if(!std::strcmp(name,"syscall"))return reinterpret_cast<void*>(current->affinity.Marker(name));if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffc76000000ULL);if(!std::strcmp(name,"affinity_stage"))return reinterpret_cast<void*>(0x7ffc76000008ULL);return reinterpret_cast<void*>(current->threads.Marker(name));}
struct Worker {
 Harness &h;AffinityWorker record{};uint64_t token=0;Pthreads::NativeThreadLease lease;GROUP_AFFINITY original{};
 explicit Worker(Harness&host):h(host){Check(!h.threads.Create(&token,nullptr,h.Entry("affinity_worker"),reinterpret_cast<addr_t>(&record)),"actual translated owned worker create");try{std::unique_lock lock(h.mutex);Check(h.condition.wait_for(lock,std::chrono::seconds(10),[&]{return h.entered;}),"actual worker reaches native pause");lock.unlock();lease=h.threads.AcquireNativeThread(record.tid);Check(bool(lease)&&lease.NativeTid()==record.tid,"owned real native handle lease");original=NativeGroup(Handle());Check(original.Group==0&&original.Mask==h.initial.Mask&&uint64_t(original.Mask)<=UINT32_MAX,"actual initial group0 mask fits guest4B profile");uint32_t mask=uint32_t(original.Mask);recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&record.initial_mask),&mask,4);}catch(...){Release();h.threads.Join(token,nullptr);token=0;throw;}}
 HANDLE Handle()const{return reinterpret_cast<HANDLE>(lease.NativeHandleBits());}
 void Release(){{std::lock_guard lock(h.mutex);h.released=true;}h.condition.notify_all();}
 void Restore(){Check(SetThreadAffinityMask(Handle(),original.Mask)!=0,"restore actual owned worker affinity");auto g=NativeGroup(Handle());Check(g.Group==original.Group&&g.Mask==original.Mask,"actual full original affinity restored");}
 void Finish(){Restore();Release();uint64_t result=0;Check(!h.threads.Join(token,&result)&&result==0x12345678,"actual native/guest normal return and join");token=0;h.Record(record.self_direct,0,731);h.Record(record.self_indirect,0,731);}
 ~Worker(){if(token){if(lease&&original.Mask)SetThreadAffinityMask(Handle(),original.Mask);Release();h.threads.Join(token,nullptr);}}
};
struct GuardedMask {unsigned char *base=nullptr;GuardedMask(){base=static_cast<unsigned char*>(VirtualAlloc(nullptr,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(base!=nullptr,"real two-page fixture mapping");DWORD old=0;Check(VirtualProtect(base+4096,4096,PAGE_NOACCESS,&old)!=0,"real guard page");}~GuardedMask(){if(base){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(base),8192);VirtualFree(base,0,MEM_RELEASE);}}};
static void Readback(Worker&w,uint64_t expected){auto group=NativeGroup(w.Handle());Check(group.Group==0&&group.Mask==expected,"independent actual native affinity readback");}
static void Environment(Harness&h,Worker&w,uint32_t *mask){fenv_t fp{};std::fegetenv(&fp);std::feclearexcept(FE_ALL_EXCEPT);std::fesetround(FE_DOWNWARD);std::feraiseexcept(FE_INEXACT);errno=611;SetLastError(612);guest_error=713;Check(h.affinity.Syscall(122,int32_t(w.record.tid),4,reinterpret_cast<addr_t>(mask),UINT64_MAX,0xbabe,UINT64_MAX)==0&&guest_error==713,"actual native method success preserves guest errno");Check(errno==611&&GetLastError()==612&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_INEXACT,"native errno/LastError/fenv survive operation and diagnostic observer");std::fesetenv(&fp);}
static void BridgeState(Harness&h,Worker&w,uint32_t *mask){State s{};std::memset(&s.gpr,0x5a,sizeof(s.gpr));std::memset(&s.simd,0xa5,sizeof(s.simd));s.gpr.x0.qword=122;s.gpr.x1.qword=w.record.tid;s.gpr.x2.qword=4;s.gpr.x3.qword=reinterpret_cast<addr_t>(mask);s.gpr.pc.qword=0x1234;s.gpr.x30.qword=0xfeedffff;auto expected=s;expected.gpr.x0.qword=0;expected.gpr.pc.qword=expected.gpr.x30.qword;h.provider.Dispatch(s,h.affinity.Marker("syscall"),nullptr);Check(!std::memcmp(&s,&expected,sizeof(s)),"typed long bridge preserves full State except X0/normal PC");}
int main(int argc,char **argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);try{
 Harness h;
 if(argc==2){uint32_t mask=1;AffinityRecord r{};if(!std::strcmp(argv[1],"length"))h.Run("affinity_probe",{122,0,8,reinterpret_cast<addr_t>(&mask),0,reinterpret_cast<addr_t>(&r)});else if(!std::strcmp(argv[1],"number"))h.Run("affinity_probe",{123,0,4,reinterpret_cast<addr_t>(&mask),0,reinterpret_cast<addr_t>(&r)});else if(!std::strcmp(argv[1],"unowned"))h.Run("affinity_probe",{122,0x7ffffffe,4,reinterpret_cast<addr_t>(&mask),0,reinterpret_cast<addr_t>(&r)});throw std::runtime_error("negative unexpectedly returned");}
 Check(GetActiveProcessorGroupCount()==1,"actual single group profile; no group mutation");const auto caller=NativeGroup(GetCurrentThread());uint64_t process_before=ProcessMask();Check(process_before<=UINT32_MAX&&process_before!=UINT32_MAX,"fixture has actual allowed and unavailable low32 CPUs");uint32_t allowed=uint32_t(process_before),one=allowed&(~allowed+1u),unavailable=~allowed;unavailable&=(~unavailable+1u);
 Worker w(h);std::printf("WINDOWS-CPU actual_allowed_low32=%#x selected=%#x tid=%u\n",allowed,one,w.record.tid);
 uint32_t saved_one=one;h.Probe(0,int32_t(w.record.tid),reinterpret_cast<addr_t>(&one),0,731);Check(one==saved_one,"mask input is read-only");Readback(w,one);
 h.Probe(1,int32_t(w.record.tid),reinterpret_cast<addr_t>(&allowed),0,731);Readback(w,allowed);
 uint32_t mixed=one|unavailable;h.Probe(2,int32_t(w.record.tid),reinterpret_cast<addr_t>(&mixed),0,731);Readback(w,one);
 GuardedMask pages;std::memcpy(pages.base+4092,&one,4);h.Probe(3,int32_t(w.record.tid),reinterpret_cast<addr_t>(pages.base+4092),0,731);Readback(w,one);
 std::memcpy(pages.base+4091,&one,4);h.Probe(4,int32_t(w.record.tid),reinterpret_cast<addr_t>(pages.base+4091),0,731);Readback(w,one);
 DWORD old=0;Check(VirtualProtect(pages.base,4096,PAGE_READONLY,&old)!=0,"actual read-only input page");h.Probe(9,int32_t(w.record.tid),reinterpret_cast<addr_t>(pages.base+4091),0,731);Readback(w,one);
 uint32_t zero=0;h.Probe(5,int32_t(w.record.tid),reinterpret_cast<addr_t>(&zero),-1,22);h.Probe(6,-1,reinterpret_cast<addr_t>(&one),-1,3);h.Probe(7,-1,1,-1,14);h.Probe(8,int32_t(w.record.tid),1,-1,14);
 h.Probe(10,int32_t(w.record.tid),reinterpret_cast<addr_t>(&unavailable),-1,22);Readback(w,one);
 const uint64_t nr[]={0xabcdef010000007aULL,0xffffabcd0000007aULL,122,122};const uint64_t pid[]={w.record.tid,w.record.tid,0x1234567800000000ULL|w.record.tid,0x12345678ffffffffULL};const uint64_t size[]={4,0xabcdef0100000004ULL,0xffffffff00000004ULL,4};
 for(unsigned i=0;i<4;++i){AffinityRecord r{};h.Run("affinity_poison",{nr[i],pid[i],size[i],reinterpret_cast<addr_t>(&one),reinterpret_cast<addr_t>(&r)});h.Record(r,i==3?-1:0,i==3?3:731);const auto &raw=h.raw_arguments.back();Check(raw[0]==nr[i]&&raw[1]==pid[i]&&raw[2]==size[i]&&raw[4]==UINT64_MAX&&raw[5]==0xbabe&&raw[6]==UINT64_MAX,"actual raw high-register poison preserved before bridge narrowing");std::printf("WINDOWS-AFFINITY-POISON %u value=%lld errno=%d\n",i,(long long)r.value,r.error);}
 Environment(h,w,&one);BridgeState(h,w,&one);Readback(w,one);
 Check(!h.observations.empty(),"real mask/native result observations");bool actual=false;for(const auto &o:h.observations)if(o.phase==ThreadAffinities::Observation::Phase::Return&&o.result==0){Check(o.mask_copied&&o.target_resolved&&o.topology_valid&&o.native_set_called&&o.readback_valid&&o.readback_mask==o.effective_mask,"successful native observation validity/readback");actual=true;}Check(actual,"at least one real successful set/readback observed");
 w.Finish();Check(WaitForSingleObject(w.Handle(),0)==WAIT_OBJECT_0,"retained duplicate remains actual retired native object");h.Probe(11,int32_t(w.record.tid),reinterpret_cast<addr_t>(&one),-1,3);h.Probe(12,int32_t(w.record.tid),1,-1,14);
 const auto after=NativeGroup(GetCurrentThread());Check(after.Group==caller.Group&&after.Mask==caller.Mask&&ProcessMask()==process_before,"caller/process affinity never mutated");
 Check(ndk_records==32,"all strict NDK Windows records executed");std::printf("AFFINITY-WINDOWS-SUCCESS checks=%u records=%u canonical=22; only owned disposable worker mutated and restored\n",checks.load(),ndk_records.load());return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"affinity fixture: %s\n",e.what());return 1;}}

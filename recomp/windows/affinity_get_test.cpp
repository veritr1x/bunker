#include <cfenv>
#include "thread_affinity.h"
#include "affinity_get_fixture.h"
#include "../whole/bridge.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <windows.h>
#include <atomic>
#include <cerrno>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <stdexcept>
using namespace bunker::windows;
static thread_local int guest_error;static unsigned checks=0,records=0;static uint64_t setter_observations=0;
static void Check(bool yes,const char*name){++checks;if(!yes)throw std::runtime_error(name);}
template<class F>static void Reject(F fn,const char*needle){bool caught=false;try{fn();}catch(const std::exception&e){caught=std::strstr(e.what(),needle)!=nullptr;}Check(caught,needle);}
static bool Translated(addr_t p){for(const auto&t:kTraces)if(t.address==p)return true;return false;}
struct Harness;static Harness*current;static void*Resolve(const char*);
static GROUP_AFFINITY Group(HANDLE h){GROUP_AFFINITY g{};Check(GetThreadGroupAffinity(h,&g)!=0,"native group query");return g;}
struct Harness{
 recomp::Runtime runtime,bridges;Pthreads threads{runtime,Translated};ThreadAffinities affinity{threads,ThreadAffinities::Profile::WindowsSingleGroupNativeIndices,0x7ff600600000ULL,[](const auto&){++setter_observations;}};
 elf_image image{};std::mutex mutex;std::condition_variable cv;bool entered=false,released=false;uint32_t tid=0;
 Harness(){current=this;threads.Self();threads.Install();affinity.SetErrorSink([](int e){guest_error=e;});affinity.Install(bridges);runtime.AddTraces(kTraces,std::size(kTraces));
  runtime.AddImport(affinity.Marker("sched_getaffinity"),[this](State&s){bridges.Dispatch(s,affinity.Marker("sched_getaffinity"),nullptr);});
  runtime.AddImport(affinity.Marker("sched_setaffinity"),[this](State&s){bridges.Dispatch(s,affinity.Marker("sched_setaffinity"),nullptr);});
  runtime.AddImport(0x7ffc76010000ULL,recomp::MakeBridge<addr_t()>([]{return reinterpret_cast<addr_t>(&guest_error);}));
  runtime.AddImport(0x7ffc76010008ULL,recomp::MakeBridge<void(uint64_t)>([this](uint64_t observed){Check(observed==GetCurrentThreadId()&&observed==uint32_t(threads.GetTid()),"real owned worker TID");std::unique_lock lock(mutex);tid=uint32_t(observed);entered=true;cv.notify_all();cv.wait(lock,[&]{return released;});}));
  Check(!elf_load(AFFINITY_GET_LIBRARY,0x5c100000,Resolve,&image),"NDK getter library");
 }
 ~Harness(){threads.Shutdown();threads.ReleaseCurrent();if(image.base){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(image.base),image.span);VirtualFree(image.base,0,MEM_RELEASE);std::free(const_cast<uint8_t*>(image.file));}}
 addr_t Entry(const char*n){auto p=reinterpret_cast<addr_t>(elf_symbol(&image,n));Check(p!=0,"NDK exported symbol");return p;}
 void Probe(unsigned id,int32_t pid,uint64_t size,addr_t mask,int value,int error){for(int form=0;form<2;++form){AffinityGetRecord r{};threads.Run(Entry("affinity_get_probe"),{uint32_t(pid),size,mask,addr_t(form),reinterpret_cast<addr_t>(&r)});Check(r.before==0x1122334455667788ULL&&r.after==0x8877665544332211ULL&&r.value==value&&r.error==error,"NDK int32 result/errno/guard");++records;std::printf("GET-AFFINITY %u form=%d rc=%d errno=%d\n",id,form,r.value,r.error);}}
 void SetProbe(unsigned id,int32_t pid,addr_t mask,int value,int error){for(int form=0;form<2;++form){AffinityGetRecord r{};threads.Run(Entry("affinity_set_probe"),{uint32_t(pid),128,mask,addr_t(form),reinterpret_cast<addr_t>(&r)});Check(r.before==0x1122334455667788ULL&&r.after==0x8877665544332211ULL&&r.value==value&&r.error==error,"NDK setter result/errno/guard");++records;std::printf("SET-AFFINITY %u form=%d rc=%d errno=%d\n",id,form,r.value,r.error);}}
};
static void*Resolve(const char*n){if(!std::strcmp(n,"sched_setaffinity"))return reinterpret_cast<void*>(current->affinity.Marker(n));if(!std::strcmp(n,"sched_getaffinity"))return reinterpret_cast<void*>(current->affinity.Marker(n));if(!std::strcmp(n,"__errno"))return reinterpret_cast<void*>(0x7ffc76010000ULL);if(!std::strcmp(n,"affinity_get_stage"))return reinterpret_cast<void*>(0x7ffc76010008ULL);return reinterpret_cast<void*>(current->threads.Marker(n));}
struct Worker{Harness&h;uint64_t token=0;Pthreads::NativeThreadLease lease;GROUP_AFFINITY initial{};
 explicit Worker(Harness&host):h(host){Check(!h.threads.Create(&token,nullptr,h.Entry("affinity_get_worker"),0),"disposable translated worker create");std::unique_lock lock(h.mutex);Check(h.cv.wait_for(lock,std::chrono::seconds(10),[&]{return h.entered;}),"worker parked");lock.unlock();lease=h.threads.AcquireNativeThread(h.tid);Check(bool(lease),"owned duplicate handle lease");initial=Group(Handle());}
 HANDLE Handle(){return reinterpret_cast<HANDLE>(lease.NativeHandleBits());}
 void Finish(){Check(SetThreadAffinityMask(Handle(),initial.Mask)!=0,"restore disposable worker mask");{std::lock_guard lock(h.mutex);h.released=true;}h.cv.notify_all();uint64_t result=0;Check(!h.threads.Join(token,&result)&&result==0x12345678,"worker real join");token=0;}
 ~Worker(){if(token){SetThreadAffinityMask(Handle(),initial.Mask);{std::lock_guard lock(h.mutex);h.released=true;}h.cv.notify_all();h.threads.Join(token,nullptr);}}
};
struct Pages{unsigned char*base=static_cast<unsigned char*>(VirtualAlloc(nullptr,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Pages(){Check(base!=nullptr,"guard allocation");DWORD old;Check(VirtualProtect(base+4096,4096,PAGE_NOACCESS,&old)!=0,"guard protection");}~Pages(){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(base),8192);VirtualFree(base,0,MEM_RELEASE);}};
static void Output(const unsigned char*p,uint64_t mask){uint64_t word=0;std::memcpy(&word,p,8);Check(word==mask,"native sparse affinity mask exact");for(unsigned i=8;i<128;++i)Check(!p[i],"public Bionic zero tail exact");}
int main(){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);try{Harness h;Worker w(h);const auto caller=Group(GetCurrentThread());DWORD_PTR process=0,system=0;Check(GetProcessAffinityMask(GetCurrentProcess(),&process,&system)!=0,"process masks");unsigned char data[130];std::memset(data,0xa5,sizeof(data));
 h.Probe(0,int32_t(h.tid),128,reinterpret_cast<addr_t>(data+1),0,731);Output(data+1,w.initial.Mask&process&system);Check(data[0]==0xa5&&data[129]==0xa5,"unaligned exact128 canaries");
 Pages pages;h.Probe(1,0,128,reinterpret_cast<addr_t>(pages.base+3968),0,731);Output(pages.base+3968,caller.Mask&process&system);
 h.Probe(2,-1,128,1,-1,3);h.Probe(3,0,128,1,-1,14);std::memset(pages.base,0xa5,128);DWORD old=0;Check(VirtualProtect(pages.base,4096,PAGE_READONLY,&old)!=0,"RO output");h.Probe(4,0,128,reinterpret_cast<addr_t>(pages.base),-1,14);for(unsigned i=0;i<128;++i)Check(pages.base[i]==0xa5,"RO output unchanged");Check(VirtualProtect(pages.base,4096,PAGE_READWRITE,&old)!=0,"restore RW");
 h.Probe(5,-1,0,1,-1,22);h.Probe(6,-1,4,1,-1,22);h.Probe(7,-1,129,1,-1,22);
 Check(setter_observations==0,"getter never calls historical setter observer");
 const uint32_t one=uint32_t(w.initial.Mask)&(~uint32_t(w.initial.Mask)+1u);Check(one!=0&&w.initial.Mask<=UINT32_MAX,"disposable worker low32 setter profile");Check(h.affinity.Syscall(122,int32_t(h.tid),4,reinterpret_cast<addr_t>(&one),0,0,0)==0,"old setter remains usable");auto observed=setter_observations;
 h.Probe(8,int32_t(h.tid),128,reinterpret_cast<addr_t>(data+1),0,731);Output(data+1,one);Check(Group(w.Handle()).Mask==one&&setter_observations==observed,"getter observes narrowing without mutation or setter event");
 fenv_t saved{};std::fegetenv(&saved);std::feclearexcept(FE_ALL_EXCEPT);std::fesetround(FE_DOWNWARD);std::feraiseexcept(FE_INEXACT);errno=611;SetLastError(612);guest_error=713;Check(!h.affinity.Get(int32_t(h.tid),128,reinterpret_cast<addr_t>(data+1))&&guest_error==713,"public success preserves guest errno");Check(errno==611&&GetLastError()==612&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_INEXACT,"native environment preserved");std::fesetenv(&saved);
 State s{};std::memset(&s.gpr,0xa5,sizeof(s.gpr));std::memset(&s.simd,0x5a,sizeof(s.simd));s.gpr.x0.qword=0xabcdef0000000000ULL|h.tid;s.gpr.x1.qword=128;s.gpr.x2.qword=reinterpret_cast<addr_t>(data+1);s.gpr.x30.qword=0xfeedffff;auto expected=s;expected.gpr.x0.qword=0;expected.gpr.pc.qword=s.gpr.x30.qword;h.bridges.Dispatch(s,h.affinity.Marker("sched_getaffinity"),nullptr);Check(!std::memcmp(&s,&expected,sizeof(s)),"getter bridge low32pid/fullsize/fullState preservation");
 Reject([&]{h.affinity.Get(0,8,reinterpret_cast<addr_t>(data));},"cpusetsize profile");Reject([&]{h.affinity.Get(0,0x100000080ULL,reinterpret_cast<addr_t>(data));},"size_t profile");Reject([&]{h.affinity.Get(0,128,reinterpret_cast<addr_t>(data)|0x0100000000000000ULL);},"tagged-address");Reject([&]{h.affinity.Get(0x7ffffffe,128,1);},"owned thread catalog");
 Pages native_pages;std::memset(native_pages.base+4080,0xa5,16);
 using NativeWrite=LONG(WINAPI*)(HANDLE,void*,const void*,SIZE_T,SIZE_T*);NativeWrite native_write{};auto address=GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"NtWriteVirtualMemory");static_assert(sizeof(native_write)==sizeof(address));std::memcpy(&native_write,&address,sizeof(address));Check(native_write!=nullptr,"independent native copy export");SIZE_T native_written=999;uint64_t actual_word=caller.Mask&process&system;const auto native_status=native_write(GetCurrentProcess(),native_pages.base+4092,&actual_word,8,&native_written);Check(native_status<0&&native_written<=4,"same-size native guarded failure");
 std::memset(pages.base+4080,0xa5,16);guest_error=731;Check(h.affinity.Get(0,128,reinterpret_cast<addr_t>(pages.base+4092))==-1&&guest_error==14,"guarded kernel-word copy is EFAULT");Check(!std::memcmp(pages.base+4080,native_pages.base+4080,16),"same-size native partial effects retained exactly");std::printf("NATIVE-WRITE8 status=%08lx written=%llu exact_effects=1\n",(unsigned long)native_status,(unsigned long long)native_written);
 std::memset(pages.base+4080,0xa5,16);Reject([&]{h.affinity.Get(0,128,reinterpret_cast<addr_t>(pages.base+4088));},"libc zero-tail memory fault");Check(!std::memcmp(pages.base+4088,&caller.Mask,8),"kernel word written before fatal libc tail");
 uint64_t selected=one;h.SetProbe(0,int32_t(h.tid),reinterpret_cast<addr_t>(&selected),0,731);Check(Group(w.Handle()).Mask==selected,"public setter actual narrow/readback");uint64_t zero=0;h.SetProbe(1,int32_t(h.tid),reinterpret_cast<addr_t>(&zero),-1,22);h.SetProbe(2,-1,reinterpret_cast<addr_t>(&zero),-1,3);h.SetProbe(3,-1,1,-1,14);h.SetProbe(4,0,1,-1,14);
 std::memcpy(pages.base+4088,&selected,8);Check(!h.affinity.Set(int32_t(h.tid),128,reinterpret_cast<addr_t>(pages.base+4088)),"public setter ignores inaccessible120B tail");Check(Group(w.Handle()).Mask==selected,"public tail-unread real effect");
 uint64_t mixed=selected|(1ULL<<63);Check(!h.affinity.Set(int32_t(h.tid),128,reinterpret_cast<addr_t>(&mixed))&&Group(w.Handle()).Mask==selected,"public64 requested mask intersects actual process/system ceiling");
 const uint64_t self_one=uint64_t(caller.Mask)&(~uint64_t(caller.Mask)+1);Check(!h.affinity.Set(0,128,reinterpret_cast<addr_t>(&self_one))&&Group(GetCurrentThread()).Mask==self_one,"public current-owned caller actual narrow");uint64_t restore=caller.Mask;Check(!h.affinity.Set(0,128,reinterpret_cast<addr_t>(&restore))&&Group(GetCurrentThread()).Mask==caller.Mask,"public current-owned caller actual restoration");
 Reject([&]{h.affinity.Set(0,4,reinterpret_cast<addr_t>(&selected));},"cpusetsize profile");Check(setter_observations==observed,"public APIs never reuse old setter observer labels");
 w.Finish();guest_error=731;Check(h.affinity.Get(int32_t(h.tid),128,1)==-1&&guest_error==3,"retired owned target ESRCH precedes bad pointer");Check(Group(GetCurrentThread()).Mask==caller.Mask,"caller affinity unchanged");
 std::printf("GET-AFFINITY-WINDOWS-PASS checks=%u records=%u native_mask=%llx setter_observations=%llu public_bytes=128 kernel_profile_bytes=8\n",checks,records,(unsigned long long)caller.Mask,(unsigned long long)setter_observations);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"getter fixture: %s\n",e.what());return 1;}}

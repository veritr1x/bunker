#include "thread_priority.h"
#include "android_process.h"
#include "priority_fixture.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <windows.h>
#include <array>
#include <atomic>
#include <cfenv>
#include <cerrno>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <stdexcept>
using namespace bunker::windows;
static thread_local int guest_error;
static std::atomic<unsigned> checks{0};
static void Check(bool yes,const char *why){++checks;if(!yes)throw std::runtime_error(why);}
template<class F>static void Reject(F f,const char *needle){bool caught=false;try{f();}catch(const std::exception &e){caught=std::strstr(e.what(),needle)!=nullptr;}Check(caught,needle);}
static bool Translated(addr_t p){for(const auto &t:kTraces)if(t.address==p)return true;return false;}
struct Harness;
static Harness *current;
static void *Resolve(const char*);
struct Harness {
 recomp::Runtime runtime;
 recomp::Runtime provider;
 Pthreads threads{runtime,Translated};
 ThreadPriorities priorities{threads,ThreadPriorities::Profile::UnityNormalClass};
 bunker::jni::Host host{Translated};
 std::unique_ptr<AndroidProcess> process;
 elf_image image{};
 std::mutex mutex;std::condition_variable condition;
 bool entered=false,released=false;
 uint32_t observed_tid=0;uint64_t observed_token=0;
 std::vector<std::pair<uint64_t,uint64_t>> raw_getter_arguments;
 std::vector<AndroidProcess::Observation> observations;
 Harness(){
  current=this;runtime.AddTraces(kTraces,std::size(kTraces));threads.Self();threads.Install();
  priorities.SetErrorSink([](int value){guest_error=value;});priorities.Install(provider);runtime.AddImport(priorities.Marker("getpriority"),[this](State &s){raw_getter_arguments.emplace_back(uint64_t(s.gpr.x0.qword),uint64_t(s.gpr.x1.qword));provider.Dispatch(s,priorities.Marker("getpriority"),nullptr);});host.Install(runtime);process=std::make_unique<AndroidProcess>(host,priorities,[this](const auto &event){observations.push_back(event);errno=882;SetLastError(883);std::fesetround(FE_UPWARD);std::feraiseexcept(FE_INVALID);});
  runtime.AddImport(0x7ffc75000000ULL,recomp::MakeBridge<addr_t()>([]{return reinterpret_cast<addr_t>(&guest_error);}));
  runtime.AddImport(0x7ffc75000008ULL,recomp::MakeBridge<void(addr_t,int32_t)>([this](addr_t p,int32_t phase){
   Check(phase==0,"actual single worker observation");PriorityWorker r{};recomp::ReadGuestMemory(&r,p,sizeof(r));
   Check(r.tid==GetCurrentThreadId()&&r.tid==static_cast<uint32_t>(threads.GetTid())&&r.token==threads.Self(),"actual guest/native owned worker identity");
   auto *s=recomp::CurrentExecutionState();AndroidThreadAttr attr{};Check(s&&!threads.GetAttr(r.token,&attr)&&s->gpr.sp.qword>=attr.stack_base&&s->gpr.sp.qword<=attr.stack_base+attr.stack_size,"actual translated child owned stack");
   std::unique_lock lock(mutex);observed_tid=r.tid;observed_token=r.token;entered=true;condition.notify_all();condition.wait(lock,[&]{return released;});
  }));
  Check(!elf_load(PRIORITY_LIBRARY,0x5d000000,Resolve,&image),"actual NDK shared object load");
 }
 ~Harness(){threads.Shutdown();threads.ReleaseCurrent();if(image.base){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(image.base),image.span);VirtualFree(image.base,0,MEM_RELEASE);std::free(const_cast<uint8_t*>(image.file));}}
 addr_t Entry(const char *name){auto p=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(p!=0,"real NDK symbol");return p;}
 addr_t Run(const char *name,std::initializer_list<addr_t> args){return threads.Run(Entry(name),args);}
 addr_t Call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
 addr_t Class(){static constexpr char name[]="android/os/Process";return Call(6,reinterpret_cast<addr_t>(name));}
 addr_t Method(addr_t owner){static constexpr char name[]="setThreadPriority",sig[]="(II)V";return Call(113,owner,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig));}
 void Probe(uint32_t who,int nice){for(int form=0;form<2;++form){PriorityRecord r{};Run("priority_probe",{0,who,static_cast<addr_t>(form),reinterpret_cast<addr_t>(&r)});Check(r.before==0x1122334455667788ULL&&r.after==0x8877665544332211ULL&&r.value==nice&&r.error==731,"actual NDK direct/indirect getter results, errno and canaries");std::printf("WINDOWS-GET who=%u form=%d nice=%d errno=%d\n",who,form,r.value,r.error);}}
 void JNI(addr_t owner,addr_t method,uint32_t who,int nice,int form){auto start=observations.size();auto r=Run("priority_jni",{host.EnvAddress(),owner,method,who,static_cast<uint32_t>(nice),static_cast<addr_t>(form)});Check(r==0x7135abcddcba5317ULL,"strict direct/V/A argument bits, padding and canaries");Check(observations.size()==start+2&&observations[start].phase==AndroidProcess::Observation::Phase::Enter&&observations[start+1].phase==AndroidProcess::Observation::Phase::Return&&observations[start].tid==who&&observations[start].nice==nice&&observations[start+1].tid==who&&observations[start+1].nice==nice,"real typed observer phases and arguments");}
};
static void *Resolve(const char *name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffc75000000ULL);if(!std::strcmp(name,"priority_stage"))return reinterpret_cast<void*>(0x7ffc75000008ULL);if(!std::strcmp(name,"getpriority"))return reinterpret_cast<void*>(current->priorities.Marker(name));return reinterpret_cast<void*>(current->threads.Marker(name));}
struct Worker {
 Harness &h;PriorityWorker record{};uint64_t token=0;Pthreads::NativeThreadLease lease;int original=THREAD_PRIORITY_NORMAL;
 explicit Worker(Harness &host):h(host){Check(!h.threads.Create(&token,nullptr,h.Entry("priority_worker"),reinterpret_cast<addr_t>(&record)),"real translated worker creation");std::unique_lock lock(h.mutex);Check(h.condition.wait_for(lock,std::chrono::seconds(10),[&]{return h.entered;}),"actual translated worker reaches pause");Check(record.token==token&&record.tid==h.observed_tid,"published guest worker identity");lock.unlock();lease=h.threads.AcquireNativeThread(record.tid);Check(bool(lease)&&lease.NativeTid()==record.tid,"real native handle lease");original=::GetThreadPriority(reinterpret_cast<HANDLE>(lease.NativeHandleBits()));Check(original==THREAD_PRIORITY_NORMAL,"actual child begins NORMAL level");}
 void Finish(){if(!token)return;Check(::SetThreadPriority(reinterpret_cast<HANDLE>(lease.NativeHandleBits()),original)!=0,"restore only actual owned worker level");{std::lock_guard lock(h.mutex);h.released=true;}h.condition.notify_all();uint64_t result=0;Check(!h.threads.Join(token,&result)&&result==0x12345678,"real normal child return/join");token=0;}
 ~Worker(){if(token){::SetThreadPriority(reinterpret_cast<HANDLE>(lease.NativeHandleBits()),original);{std::lock_guard lock(h.mutex);h.released=true;}h.condition.notify_all();h.threads.Join(token,nullptr);}}
};
static void Environment(Harness &h,uint32_t who){
 const int prior_round=std::fegetround();std::feclearexcept(FE_ALL_EXCEPT);std::fesetround(FE_DOWNWARD);std::feraiseexcept(FE_INVALID|FE_INEXACT);errno=614;SetLastError(585);
 Check(h.priorities.GetPriority(0,who)==0,"native priority environment query");Check(errno==614&&GetLastError()==585&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==(FE_INVALID|FE_INEXACT),"get preserves native errno/LastError/fenv");
 Check(h.priorities.SetThreadPriority(who,0)==0,"equal priority shortcut");Check(errno==614&&GetLastError()==585&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==(FE_INVALID|FE_INEXACT),"set preserves native errno/LastError/fenv");
 {auto lease=h.threads.AcquireNativeThread(who);Check(bool(lease),"second real duplicated lease");}Check(errno==614&&GetLastError()==585&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==(FE_INVALID|FE_INEXACT),"lease acquisition/release preserves native environment");std::feclearexcept(FE_ALL_EXCEPT);std::fesetround(prior_round);
}
static void ObserverEnvironment(Harness &h,addr_t owner,addr_t method){
 fenv_t original{};std::fegetenv(&original);std::feclearexcept(FE_ALL_EXCEPT);std::fesetround(FE_TOWARDZERO);std::feraiseexcept(FE_INEXACT);errno=911;SetLastError(912);guest_error=671;
 std::array<uint64_t,2> args{};auto count=h.observations.size();h.Call(143,owner,method,reinterpret_cast<addr_t>(args.data()));
 Check(h.observations.size()==count+2&&h.observations.back().error==0&&guest_error==671&&h.host.PendingException().empty(),"actual same-level platform callback and observer result");Check(errno==911&&GetLastError()==912&&std::fegetround()==FE_TOWARDZERO&&std::fetestexcept(FE_ALL_EXCEPT)==FE_INEXACT,"diagnostic observer cannot leak native errno/LastError/fenv mutations");std::fesetenv(&original);
}
static void BridgeState(Harness &h){
 State s{};std::memset(&s.gpr,0x5a,sizeof(s.gpr));std::memset(&s.simd,0xa5,sizeof(s.simd));s.gpr.x0.qword=0;s.gpr.x1.qword=0;s.gpr.pc.qword=0x1234;s.gpr.x30.qword=0xfeedffff;State expected=s;expected.gpr.x0.qword=0;expected.gpr.pc.qword=expected.gpr.x30.qword;h.provider.Dispatch(s,h.priorities.Marker("getpriority"),nullptr);Check(std::memcmp(&s,&expected,sizeof(s))==0,"typed priority bridge preserves complete State except W0/normal return PC");
}
static void Bindings(Harness &h){
 using Args=bunker::jni::Host::MethodArguments;auto body=[](addr_t,const Args&){};
 const char *sig="(II)V";h.host.DefineClass("PriorityPlatform",{{"platform",sig,true,true},{"guest",sig,true,true},{"ordinary",sig,true,false},{"instance",sig,false,true}},"java/lang/Object",true);
 h.host.BindPlatformNativeStaticVoidMethod("PriorityPlatform","platform",sig,body);
 Check(h.host.NativeCount("PriorityPlatform")==0,"platform body is not a fabricated translated native entry");
 Reject([&]{h.host.BindPlatformNativeStaticVoidMethod("PriorityPlatform","platform",sig,body);},"unowned");
 Reject([&]{h.host.BindPlatformNativeStaticVoidMethod("PriorityPlatform","ordinary",sig,body);},"unowned");
 Reject([&]{h.host.BindPlatformNativeStaticVoidMethod("PriorityPlatform","instance",sig,body);},"unowned");
 Reject([&]{h.host.BindPlatformNativeStaticVoidMethod("PriorityPlatform","absent",sig,body);},"unowned");
 h.host.BindStaticVoidMethod("PriorityPlatform","ordinary",sig,body);
 auto ordinary_owner=h.Call(6,reinterpret_cast<addr_t>("PriorityPlatform"));auto ordinary_method=h.Call(113,ordinary_owner,reinterpret_cast<addr_t>("ordinary"),reinterpret_cast<addr_t>(sig));
 for(unsigned form=0;form<3;++form){Check(h.Run("priority_jni",{h.host.EnvAddress(),ordinary_owner,ordinary_method,0x12345678,static_cast<uint32_t>(-2),form})==0x7135abcddcba5317ULL&&h.host.PendingException().empty(),"old nonnative static void binding direct/V/A remains valid");}
 h.host.DefineClass("PriorityApplication",{{"platform",sig,true,true}});h.host.MarkClassInitialized("PriorityApplication");Reject([&]{h.host.BindPlatformNativeStaticVoidMethod("PriorityApplication","platform",sig,body);},"bootstrap");
 auto clazz=h.Call(6,reinterpret_cast<addr_t>("PriorityPlatform"));auto target=h.Entry("priority_native");
 bunker::jni::NativeMethod rows[]={{reinterpret_cast<addr_t>("guest"),reinterpret_cast<addr_t>(sig),target},{reinterpret_cast<addr_t>("platform"),reinterpret_cast<addr_t>(sig),target}};
 Check(static_cast<int32_t>(h.Call(215,clazz,reinterpret_cast<addr_t>(rows),2))==-1&&!h.host.PendingException().empty()&&h.host.NativeCount("PriorityPlatform")==0,"mixed registration conflict is transactional");h.host.ClearException();
 Check(h.Call(215,clazz,reinterpret_cast<addr_t>(rows),1)==0&&h.host.NativeCount("PriorityPlatform")==1&&h.host.NativeEntry("PriorityPlatform","guest",sig)==target,"real translated guest registration remains supported");
 Reject([&]{h.host.BindPlatformNativeStaticVoidMethod("PriorityPlatform","guest",sig,body);},"unowned");
 Check(static_cast<int32_t>(h.Call(216,clazz))==-1&&!h.host.PendingException().empty()&&h.host.NativeCount("PriorityPlatform")==1&&h.host.NativeEntry("PriorityPlatform","guest",sig)==target,"mixed unregister preserves guest registration on platform ownership conflict");h.host.ClearException();
}
static void SecurityCatalog(Harness &h){
 auto security=h.Call(6,reinterpret_cast<addr_t>("java/lang/SecurityException"));auto runtime=h.Call(6,reinterpret_cast<addr_t>("java/lang/RuntimeException"));auto throwable=h.Call(6,reinterpret_cast<addr_t>("java/lang/Throwable"));
 Check(security&&runtime&&throwable&&h.host.PendingException().empty()&&h.Call(11,security,runtime)&&h.Call(11,security,throwable),"SecurityException is actual declared RuntimeException/Throwable hierarchy");
 h.host.ThrowException("java/lang/SecurityException",u"TEST permission exception catalog");Check(h.host.PendingException()=="java/lang/SecurityException: TEST permission exception catalog","real framework SecurityException roundtrip");auto exception=h.Call(15);Check(exception&&h.Call(32,exception,security),"actual pending SecurityException object identity/type");h.host.ClearException();h.host.DeleteLocalReference(exception);
}
int main(int argc,char **argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);try{
 Harness h;auto owner=h.Class(),method=h.Method(owner);Check(owner&&method&&h.host.PendingException().empty(),"real initialized framework class/static method");
 if(argc==2){if(!std::strcmp(argv[1],"group")){PriorityRecord r{};h.Run("priority_probe",{1,0,0,reinterpret_cast<addr_t>(&r)});}else if(!std::strcmp(argv[1],"unowned")){PriorityRecord r{};h.Run("priority_probe",{0,0x7ffffffe,0,reinterpret_cast<addr_t>(&r)});}else if(!std::strcmp(argv[1],"expired")){h.process.reset();h.JNI(owner,method,0,0,0);}throw std::runtime_error("negative unexpectedly returned");}
 Check(GetPriorityClass(GetCurrentProcess())==NORMAL_PRIORITY_CLASS,"explicit real NORMAL process class; no class mutation");h.Probe(0,0);h.Probe(static_cast<uint32_t>(h.threads.GetTid()),0);
 const uint64_t which[]={0xabcdef0100000000ULL,0x11223344ffffffffULL,0x1122334400000000ULL},who[]={0x5566778800000000ULL,0,0xdeadbeefffffffffULL};const int values[]={0,-1,-1},errors[]={731,22,3};
 for(unsigned i=0;i<3;++i){PriorityRecord r{};h.Run("priority_poison",{which[i],who[i],reinterpret_cast<addr_t>(&r)});Check(h.raw_getter_arguments.back()==std::make_pair(which[i],who[i])&&r.value==values[i]&&r.error==errors[i]&&r.before==0x1122334455667788ULL&&r.after==0x8877665544332211ULL,"actual raw upper32 register poison and typed low32 normalization");std::printf("WINDOWS-POISON %u value=%d errno=%d\n",i,r.value,r.error);}
 Bindings(h);SecurityCatalog(h);
 ObserverEnvironment(h,owner,method);BridgeState(h);
 Worker w(h);Check(w.record.direct.value==0&&w.record.direct.error==731&&w.record.indirect.value==0&&w.record.indirect.error==731,"actual worker direct/indirect queries");Environment(h,w.record.tid);
 const int nice[]={10,1,0,-2};const int native[]={THREAD_PRIORITY_LOWEST,THREAD_PRIORITY_BELOW_NORMAL,THREAD_PRIORITY_NORMAL,THREAD_PRIORITY_ABOVE_NORMAL};
 for(int form=0;form<3;++form)for(unsigned i=0;i<4;++i){guest_error=912;h.JNI(owner,method,w.record.tid,nice[i],form);Check(h.host.PendingException().empty()&&guest_error==0,"changed JNI setter clears guest errno");Check(::GetThreadPriority(reinterpret_cast<HANDLE>(w.lease.NativeHandleBits()))==native[i],"independent real native remote setter readback");h.Probe(w.record.tid,nice[i]);guest_error=913;h.JNI(owner,method,w.record.tid,nice[i],form);Check(h.host.PendingException().empty()&&guest_error==913,"equal JNI setter preserves guest errno");std::printf("WINDOWS-SET form=%d nice=%d native=%d\n",form,nice[i],native[i]);}
 Check(::SetThreadPriority(reinterpret_cast<HANDLE>(w.lease.NativeHandleBits()),THREAD_PRIORITY_HIGHEST)!=0,"test owns level mutation");Reject([&]{h.priorities.GetPriority(0,w.record.tid);},"native thread level");Check(::SetThreadPriority(reinterpret_cast<HANDLE>(w.lease.NativeHandleBits()),THREAD_PRIORITY_NORMAL)!=0,"restore supported level");
 Reject([&]{h.priorities.SetThreadPriority(w.record.tid,5);},"unsupported nice");Reject([&]{h.priorities.GetPriority(2,0);},"namespace");Reject([&]{h.priorities.GetPriority(0,0x7ffffffe);},"owned thread catalog");
 for(int which:{-1,3}){guest_error=914;Check(h.priorities.GetPriority(which,0)==-1&&guest_error==22,"invalid which returns Android EINVAL");}
 for(int form=0;form<2;++form){PriorityRecord r{};h.Run("priority_probe",{0,UINT32_MAX,static_cast<addr_t>(form),reinterpret_cast<addr_t>(&r)});Check(r.value==-1&&r.error==3,"actual NDK negative Android tid returns ESRCH");}
 for(int form=0;form<3;++form){h.JNI(owner,method,UINT32_MAX,0,form);Check(h.host.PendingException().find("IllegalArgumentException: Given thread -1 does not exist")!=std::string::npos&&guest_error==3,"exact JNI negative-tid exception and errno");h.host.ClearException();}
 Reject([&]{h.host.BindStaticVoidMethod("android/os/Process","setThreadPriority","(II)V",[](addr_t,const bunker::jni::Host::MethodArguments&){});},"native");
 std::atomic<unsigned> live{0},retired{0},bad{0};std::atomic<bool> stop{false};std::thread racing([&]{try{while(!stop.load()){guest_error=771;auto value=h.priorities.GetPriority(0,w.record.tid);if(value==0&&guest_error==771)++live;else if(value==-1&&guest_error==3)++retired;else ++bad;std::this_thread::yield();}for(unsigned i=0;i<64;++i){guest_error=771;if(h.priorities.GetPriority(0,w.record.tid)==-1&&guest_error==3)++retired;else ++bad;}}catch(...){++bad;}});
 struct RaceJoin {std::atomic<bool> &stop;std::thread &thread;~RaceJoin(){stop=true;if(thread.joinable())thread.join();}} race_join{stop,racing};
 while(!live.load()&&!bad.load()){std::this_thread::yield();}
 w.Finish();stop=true;racing.join();Check(live&&retired>=64&&!bad,"real native handle query/retirement race permits live result or ESRCH");std::printf("WINDOWS-RETIRE-RACE live=%u retired=%u\n",live.load(),retired.load());Check(WaitForSingleObject(reinterpret_cast<HANDLE>(w.lease.NativeHandleBits()),0)==WAIT_OBJECT_0&&w.lease.NativeTid()==w.record.tid,"retained duplicate is actual retired native object");Check(!h.threads.AcquireNativeThread(w.record.tid),"retired native target does not alias a replacement");guest_error=915;Check(h.priorities.GetPriority(0,w.record.tid)==-1&&guest_error==3,"known retired getter ESRCH");h.JNI(owner,method,w.record.tid,0,2);Check(h.host.PendingException().find("does not exist")!=std::string::npos,"retired JNI setter exception");h.host.ClearException();
 std::function<int(uint32_t,int32_t)> expired;{ThreadPriorities temporary(h.threads,ThreadPriorities::Profile::UnityNormalClass);expired=temporary.Setter();}Reject([&]{expired(0,0);},"owner expired");
 std::puts("PRIORITY-WINDOWS-SUCCESS native-owned-only no-game-no-CFS-equivalence");std::printf("PRIORITY-CHECKS %u\n",checks.load());return 0;
 }catch(const std::exception &e){std::fprintf(stderr,"priority fixture: %s\n",e.what());return 1;}}

// The complete accepted untimed fixture is compiled unchanged as a regression.
#define main UntimedHost
#include "futex_test.cpp"
#undef main
struct RelativeTime{int64_t seconds,nanoseconds;};
static_assert(sizeof(RelativeTime)==16,"Android LP64 timespec");
namespace {
constexpr addr_t kOverrunProtocol=0x7ffe52000000ULL;static_assert(kOverrunProtocol!=kErrno&&kOverrunProtocol!=kReadonlyProbe);
struct OverrunContext{SignalFutexes*service;Harness*host;RelativeTime*timeout;uint32_t*word;int64_t result=99;};
thread_local OverrunContext*overrun_context=nullptr;
Memory*OverrunTrace(State&s,addr_t pc,Memory*memory){s.gpr.pc.qword=pc;auto&c=*overrun_context;const auto high=s.gpr.sp.qword;SignalDelivery frame(c.host->runtime,Executable,c.host->normal,{high-131072,high});active_delivery=&frame;c.result=c.service->Syscall(98,reinterpret_cast<addr_t>(c.word),0x80,0,reinterpret_cast<addr_t>(c.timeout),0,0);active_delivery=nullptr;s.gpr.pc.qword=s.gpr.x30.qword;return memory;}
int64_t TimedCall(Harness&h,uintptr_t address,uint64_t expected,uintptr_t timeout,unsigned mode,int*error){auto a=Args(address,UINT64_C(0x100000080),expected,mode);a.timeout=timeout;a.nr=mode?UINT64_C(0xffffffff00000062):UINT64_C(0x100000062);return h.Run(a,error);}
std::unique_ptr<Job>TimedStart(Harness&h,uintptr_t address,RelativeTime*timeout,unsigned mode){auto job=std::make_unique<Job>();job->token=h.next_token++;job->call=Args(address,0x80,0,mode);job->call.timeout=reinterpret_cast<addr_t>(timeout);Check(!h.signals.RegisterThread(job->token,1),"timed child captures real creator mask");Job*j=job.get();job->thread=std::thread([&h,j]{current_token=j->token;Check(!h.signals.BindCurrent(current_token),"timed actual same-worker owner");j->started=true;j->result=h.Run(j->call,&j->error);Check(!h.signals.DropThread(current_token),"timed retirement after real call");j->done=true;});return job;}
struct Pages{
 unsigned char*base=nullptr;size_t length;
 explicit Pages(size_t n):length(n){
#ifdef _WIN32
  base=static_cast<unsigned char*>(VirtualAlloc(nullptr,n,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(base!=nullptr,"actual timed fixture allocation");
#else
  base=static_cast<unsigned char*>(mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));Check(base!=MAP_FAILED,"actual timed fixture allocation");
#endif
 }
 void Protect(size_t offset,size_t size,bool readable){
#ifdef _WIN32
  DWORD old=0;Check(VirtualProtect(base+offset,size,readable?PAGE_READONLY:PAGE_NOACCESS,&old),"actual timeout protection");
#else
  Check(!mprotect(base+offset,size,readable?PROT_READ:PROT_NONE),"actual timeout protection");
#endif
 }
 ~Pages(){
#ifdef _WIN32
  VirtualFree(base,0,MEM_RELEASE);
#else
  munmap(base,length);
#endif
 }
};
}
int main(int argc,char**argv){
 if(argc>1)return UntimedHost(argc,argv);
 Check(!UntimedHost(argc,argv),"unchanged old private futex23 regression completes");Deadline watchdog;Harness h;
 alignas(64)uint32_t word=0;RelativeTime zero{0,0},negative{-1,0},bad_nsec{0,1000000000},negative_nsec{0,-1},long_time{10,0};
 Pages partial(8192),readonly(4096);partial.Protect(4096,4096,false);std::memcpy(readonly.base,&zero,16);readonly.Protect(0,4096,true);
 unsigned char unaligned[18];std::memset(unaligned,0xa5,sizeof(unaligned));std::memcpy(unaligned+1,&zero,16);RelativeTime alias{0,0};unsigned records=0;int error=0;
 for(unsigned mode=0;mode<2;++mode){
  const char*names[]={"timefault-before-align","negative-sec-before-align","bad-nsec-before-address","negative-nsec","mismatch-zero","match-zero","mismatch-long","partial-timefault","wordfault-validtime","align-validtime","readonly-time","unaligned-time","alias-zero"};
  uintptr_t addresses[]={UINT64_MAX,UINT64_MAX,0,reinterpret_cast<uintptr_t>(&word),reinterpret_cast<uintptr_t>(&word),reinterpret_cast<uintptr_t>(&word),reinterpret_cast<uintptr_t>(&word),reinterpret_cast<uintptr_t>(&word),reinterpret_cast<uintptr_t>(partial.base+4096),UINT64_MAX,reinterpret_cast<uintptr_t>(&word),reinterpret_cast<uintptr_t>(&word),reinterpret_cast<uintptr_t>(&alias)};
  uintptr_t times[]={reinterpret_cast<uintptr_t>(partial.base+4096),reinterpret_cast<uintptr_t>(&negative),reinterpret_cast<uintptr_t>(&bad_nsec),reinterpret_cast<uintptr_t>(&negative_nsec),reinterpret_cast<uintptr_t>(&zero),reinterpret_cast<uintptr_t>(&zero),reinterpret_cast<uintptr_t>(&long_time),reinterpret_cast<uintptr_t>(partial.base+4096-8),reinterpret_cast<uintptr_t>(&zero),reinterpret_cast<uintptr_t>(&zero),reinterpret_cast<uintptr_t>(readonly.base),reinterpret_cast<uintptr_t>(unaligned+1),reinterpret_cast<uintptr_t>(&alias)};
  int errors[]={14,22,22,22,11,110,11,14,14,22,110,110,110};
  for(unsigned i=0;i<13;++i){auto value=(i==4||i==6)?UINT64_C(0x100000001):UINT64_C(0x100000000);auto result=TimedCall(h,addresses[i],value,times[i],mode,&error);Check(result==-1&&error==errors[i],names[i]);std::printf("TIMED mode=%u case=%s result=%lld errno=%d\n",mode,names[i],(long long)result,error);++records;}
 }
 Check(unaligned[0]==0xa5&&unaligned[17]==0xa5&&!std::memcmp(unaligned+1,&zero,16)&&!std::memcmp(readonly.base,&zero,16)&&!std::memcmp(&alias,&zero,16),"timed exact input/canary preservation");
 for(unsigned mode=0;mode<2;++mode){
  RelativeTime duration{0,30000000};Check(!h.Call(reinterpret_cast<uintptr_t>(&word),0x81,1,0,&error),"prior timed wake no saved credits");auto begin=std::chrono::steady_clock::now();auto result=TimedCall(h,reinterpret_cast<uintptr_t>(&word),0,reinterpret_cast<uintptr_t>(&duration),mode,&error);auto elapsed=std::chrono::steady_clock::now()-begin;Check(result==-1&&error==110&&elapsed>=std::chrono::milliseconds(25)&&elapsed<std::chrono::seconds(5),"finite real monotonic expiry");std::printf("TIMING mode=%u expiry_ns=%lld\n",mode,(long long)std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count());std::printf("TIMED-DEADLINE mode=%u result=-1 errno=110\n",mode);++records;
  Check(!h.Call(reinterpret_cast<uintptr_t>(&word),0x81,1,0,&error),"expired timed ticket no ghost wake");auto j=TimedStart(h,reinterpret_cast<uintptr_t>(&word),&long_time,mode);h.Enrolled(*j);Check(h.PositiveWake(reinterpret_cast<uintptr_t>(&word),1,mode)==1,"actual finite queued WAKE selected1");h.Join(*j);Check(!j->result&&j->error==731,"finite selected returns0 preserves actual guest errno");std::printf("TIMED-WAKE mode=%u result=0 errno=731 wake=1\n",mode);++records;
 }
 for(unsigned mode=0;mode<2;++mode){RelativeTime max_milliseconds{4294967,295000000};auto j=TimedStart(h,reinterpret_cast<uintptr_t>(&word),&max_milliseconds,mode);h.Enrolled(*j);Check(h.PositiveWake(reinterpret_cast<uintptr_t>(&word),1,mode)==1,"UINT32_MAX milliseconds finite selected wake");h.Join(*j);Check(!j->result&&j->error==731,"large finite timeout does not become DWORD infinite");std::printf("TIMED-LONGWAKE mode=%u result=0 errno=731 wake=1\n",mode);++records;}
 for(unsigned i=0;i<16;++i){RelativeTime duration{0,3000000};auto j=TimedStart(h,reinterpret_cast<uintptr_t>(&word),&duration,i&1);Until([&]{return h.admissions[j->token].load()||j->done.load();},"finite race actual owner entered");std::this_thread::sleep_for(std::chrono::milliseconds(3));auto wake=h.Call(reinterpret_cast<uintptr_t>(&word),0x81,1,i&1,&error);h.Join(*j);Check(error==731&&((wake==1&&!j->result&&j->error==731)||(wake==0&&j->result==-1&&j->error==110)),"timeout/wake single linearized winner count");std::printf("TIMED-RACE %u result=%lld errno=%d wake=%lld\n",i,(long long)j->result,j->error,(long long)wake);}
 for(unsigned restart=0;restart<2;++restart)for(unsigned huge=0;huge<2;++huge){
  h.Action(restart!=0);h.Handler(reinterpret_cast<uintptr_t>(&word),false);RelativeTime timeout=huge?RelativeTime{INT64_MAX,999999999}:RelativeTime{2,0};auto j=TimedStart(h,reinterpret_cast<uintptr_t>(&word),&timeout,restart);h.Enrolled(*j);Check(!h.signals.Queue(j->token,10),"finite actual caught signal after enrollment");h.Join(*j);Check(j->result==-1&&j->error==4&&h.Read<uint32_t>(h.count)==1&&h.Read<int64_t>(h.handler_wake)==0,"finite EINTR even SA_RESTART/ktime saturation; handler sees withdrawn ticket");std::printf("TIMED-SIGNAL restart=%u huge=%u result=-1 errno=4 nested-wake=0\n",restart,huge);++records;
 }
 // Explicit C++ Runtime protocol, not an ISA trace: a real SignalDelivery
 // boundary takes100ms after interrupt selection, with the actual NDK handler.
 const recomp::Trace protocol{kOverrunProtocol,OverrunTrace};h.runtime.AddTraces(&protocol,1);
 for(unsigned restart=0;restart<2;++restart){h.Action(restart!=0);h.Handler(reinterpret_cast<uintptr_t>(&word),false);SignalFutexes slow(h.signals,[]{return current_token;},[](const auto&d){Check(active_delivery!=nullptr,"real owned overrun SignalDelivery frame");std::this_thread::sleep_for(std::chrono::milliseconds(100));return active_delivery->Deliver(d);},[](uint64_t){return SignalHost::Bit(10);});slow.SetErrorSink([](int e){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&e,sizeof(e));});RelativeTime timeout{0,50000000};OverrunContext context{&slow,&h,&timeout,&word};overrun_context=&context;alignas(16)std::array<uint8_t,131072>stack{};State s{};s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;Check(!h.signals.Queue(1,10),"real overrun pending before protocol");auto begin=std::chrono::steady_clock::now();h.runtime.Run(s,protocol.address);auto elapsed=std::chrono::steady_clock::now()-begin;overrun_context=nullptr;Check(context.result==-1&&guest_error==4&&h.Read<uint32_t>(h.count)==1&&elapsed>=std::chrono::milliseconds(90)&&s.gpr.pc.qword==0xfeedffff,"selected interrupt survives100ms delivery-scope overrun");std::printf("OVERRUN-TIMING restart=%u elapsed_ns=%lld protocol=labelled-Cpp\n",restart,(long long)std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count());std::printf("TIMED-OVERRUN restart=%u result=-1 errno=4\n",restart);++records;}
 // Typed production observation is outside provider locks, after the one true
 // copy/deadline. Mutate the source and native environment; neither can rearm it.
 RelativeTime snapshot{0,30000000};unsigned copied=0,returned=0;const auto address=reinterpret_cast<addr_t>(&snapshot);
 h.futex.SetWaitObserver([&](const SignalFutexes::WaitObservation&o){Check(o.timeout_pointer==address,"actual timeout observation identity");if(o.phase==SignalFutexes::WaitPhase::Copied){++copied;Check(o.copied&&o.deadline_valid&&o.seconds==0&&o.nanoseconds==30000000,"copied original timeout/deadline");snapshot={0,0};}else{++returned;Check(o.result==-1&&o.error==110,"actual finite timeout return observation");}errno=999;std::fesetround(FE_UPWARD);std::feraiseexcept(FE_INVALID);});
 errno=88;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);auto begin=std::chrono::steady_clock::now();auto result=h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x80,0,address,0,0);auto elapsed=std::chrono::steady_clock::now()-begin;Check(result==-1&&guest_error==110&&elapsed>=std::chrono::milliseconds(25)&&elapsed<std::chrono::seconds(5)&&copied==1&&returned==1,"one original snapshot/fixed real deadline despite observer source mutation");Check(errno==88&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"observer preserves exact native errno/fenv");h.futex.SetWaitObserver({});std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);
 h.Action(false);uint64_t bit=SignalHost::Bit(10);Check(!h.signals.Mask(1,0,&bit,nullptr),"timed blocked child mask snapshot");RelativeTime blocked_duration{0,30000000};auto blocked=TimedStart(h,reinterpret_cast<uintptr_t>(&word),&blocked_duration,0);Check(!h.signals.Mask(1,1,&bit,nullptr),"timed creator mask restored");h.Enrolled(*blocked);Check(!h.signals.Queue(blocked->token,10),"actual blocked signal during timed wait");h.signals.Wake(blocked->token)->Notify();h.Join(*blocked);Check(blocked->result==-1&&blocked->error==110,"blocked pending/spurious notify cannot fake success/EINTR");
 // Model a bounded native preemption delay in the read-only admission policy.
 // A real producer queues a signal while this actual worker computes; expiry
 // before selection must leave it pending rather than consume a handler.
 h.Action(false);h.Handler(reinterpret_cast<uintptr_t>(&word),false);std::atomic<bool>inside{false};h.policy=[&](uint64_t){inside=true;const auto until=std::chrono::steady_clock::now()+std::chrono::milliseconds(80);while(std::chrono::steady_clock::now()<until)std::atomic_signal_fence(std::memory_order_seq_cst);return SignalHost::Bit(10);};std::thread producer([&]{Until([&]{return inside.load();},"delayed admission actually entered");Check(!h.signals.Queue(1,10),"actual pending during admission native delay");});RelativeTime delayed{0,30000000};result=h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x80,0,reinterpret_cast<addr_t>(&delayed),0,0);producer.join();h.policy={};Check(result==-1&&guest_error==110&&SignalHost::NeedsPoll(h.signals.Lookup(1))&&h.Read<uint32_t>(h.count)==0,"deadline after admission retires before consuming pending handler");Check(!h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x81,1,0,0,0),"postadmission timeout no ghost wake");
 Check(!h.signals.DropThread(1),"timed main real retirement");std::printf("FUTEX-TIMED-HOST-SUCCESS records=%u checks=%u\n",records,checks.load());return 0;
}

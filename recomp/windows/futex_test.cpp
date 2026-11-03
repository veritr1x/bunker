#include <cfenv>
#include "signal_futex.h"
#include "signal_delivery.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "futex_fixture.h"
#include <array>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};thread_local uint64_t current_token;thread_local int guest_error;thread_local SignalDelivery* active_delivery;SignalFutexes*provider;
constexpr addr_t kErrno=0x7ffe50000000ULL,kReadonlyProbe=0x7ffe51000000ULL;static_assert(kErrno!=kReadonlyProbe);std::atomic<unsigned>readonly_probes{0};
void Check(bool okay,const char*message){if(!okay){std::fprintf(stderr,"futex check:%s\n",message);std::abort();}++checks;}
struct Deadline{std::mutex mutex;std::condition_variable cv;bool done=false;std::thread worker;Deadline():worker([this]{std::unique_lock lock(mutex);if(!cv.wait_for(lock,std::chrono::seconds(35),[this]{return done;})){std::fputs("futex component watchdog\n",stderr);std::_Exit(98);}}){}~Deadline(){{std::lock_guard lock(mutex);done=true;}cv.notify_all();worker.join();}};
template<class Test>void Until(Test test,const char*message){auto limit=std::chrono::steady_clock::now()+std::chrono::seconds(5);while(!test()){Check(std::chrono::steady_clock::now()<limit,message);std::this_thread::sleep_for(std::chrono::milliseconds(1));}}
bool Executable(addr_t address){for(auto&t:kTraces)if(t.address==address)return true;return false;}
void*Resolve(const char*name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(kErrno);return reinterpret_cast<void*>(provider->Marker(name));}
FutexCall Args(uintptr_t address,uint64_t operation,uint64_t value,unsigned mode){return{98,address,operation,value,(operation&0xffffffff)==0x81?UINT64_MAX:0,UINT64_MAX,UINT64_MAX,mode};}
Memory* ReadonlyEpochProbe(State&s,addr_t,Memory*memory){++readonly_probes;auto*word=reinterpret_cast<uint64_t*>(s.gpr.x0.qword);const auto expected=*word;Check(__remill_aarch64_load_exclusive(s,reinterpret_cast<addr_t>(word),8,0)==expected,"active protocol reservation before readonly scope");uint64_t copied=0;recomp::WithGuestMemoryRead([&]{std::memcpy(&copied,word,8);});Check(copied==expected&&__remill_aarch64_store_exclusive(s,reinterpret_cast<addr_t>(word),expected,8,0)==0,"readonly scope creates no epoch invalidation");s.gpr.pc.qword=s.gpr.x30.qword;return memory;}
struct Job{uint64_t token;FutexCall call;int error=0;int64_t result=99;std::atomic<bool>started{false},done{false};std::thread thread;};
struct Harness{
 recomp::Runtime runtime;SignalHost signals;std::array<std::atomic<unsigned>,256>admissions{};std::atomic<uint64_t>allowed{SignalHost::Bit(10)};std::function<uint64_t(uint64_t)>policy;SignalFutexes futex;elf_image image{};std::atomic<unsigned>delivered{0},observations{0};std::atomic<bool>number_positive{false},number_negative{false};uint64_t next_token=2;addr_t normal=0,handler=0,count=0,mode=0,word_pointer=0,handler_wake=0;
 Harness():futex(signals,[]{return current_token;},[this](const auto&delivery){Check(active_delivery!=nullptr,"actual same-worker SignalDelivery binding");++delivered;return active_delivery->Deliver(delivery);},[this](auto token){Check(token<admissions.size(),"bounded actual test token");++admissions[token];return policy?policy(token):allowed.load();}){
  current_token=1;Check(!signals.RegisterThread(1)&&!signals.BindCurrent(1),"main real bound owner");provider=&futex;futex.SetErrorSink([](int error){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&error,sizeof(error));});futex.Install(runtime,[this](const State&s,uint64_t token){Check(token==current_token&&s.gpr.sp.qword%16==0,"sevenarg observer actual owner/SP");++observations;if(s.gpr.x0.qword==UINT64_C(0x100000062))number_positive=true;if(s.gpr.x0.qword==UINT64_C(0xffffffff00000062))number_negative=true;});runtime.AddTraces(kTraces,std::size(kTraces));runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});Check(!elf_load(FUTEX_LIBRARY,0x5c000000,Resolve,&image),"same actual NDK object loaded");normal=Symbol("futex_return");handler=Symbol("futex_handler");count=Data("futex_handler_count");mode=Data("futex_handler_mode");word_pointer=Data("futex_handler_word");handler_wake=Data("futex_handler_wake");Action(false);
 }
 ~Harness(){
#ifdef _WIN32
  VirtualFree(image.base,0,MEM_RELEASE);
#else
  munmap(image.base,image.span);
#endif
  std::free(const_cast<uint8_t*>(image.file));
 }
 addr_t Symbol(const char*name){auto a=Data(name);Check(Executable(a),"real translated entry");return a;}
 addr_t Data(const char*name){auto a=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(a!=0,"actual guest export");return a;}
 template<class T>T Read(addr_t a){T value{};recomp::ReadGuestMemory(&value,a,sizeof(value));return value;}
 template<class T>void Write(addr_t a,T value){recomp::WriteGuestMemory(a,&value,sizeof(value));}
 void Action(bool restart){AndroidSignalAction action{};action.handler=handler;action.flags=restart?0x10000000:0;Check(!signals.Action(10,&action,nullptr),"real caught disposition");}
 void Handler(uintptr_t word,bool change){Write<uint32_t>(count,0);Write<uint32_t>(mode,change?1:0);Write<uint64_t>(word_pointer,word);Write<int64_t>(handler_wake,-99);}
 int64_t Run(const FutexCall&call,int*error){alignas(16)std::array<uint8_t,131072>stack{};State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(&call);s.gpr.x1.qword=reinterpret_cast<addr_t>(error);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;for(unsigned reg=19;reg<30;++reg){uint64_t value=UINT64_C(0x1100000000000000)+reg;std::memcpy(reinterpret_cast<uint8_t*>(&s.gpr.x0)+16*reg,&value,8);}SignalDelivery frame(runtime,Executable,normal,{reinterpret_cast<addr_t>(stack.data()),s.gpr.sp.qword});active_delivery=&frame;runtime.Run(s,Symbol("guest_futex"));active_delivery=nullptr;Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"real NDK long/SP/PC return");for(unsigned reg=19;reg<30;++reg){uint64_t value;std::memcpy(&value,reinterpret_cast<uint8_t*>(&s.gpr.x0)+16*reg,8);Check(value==UINT64_C(0x1100000000000000)+reg,"preserved actual NDK calleeGPR");}return int64_t(s.gpr.x0.qword);}
 int64_t Call(uintptr_t address,uint64_t op,uint64_t value,unsigned m,int*error){return Run(Args(address,op,value,m),error);}
 std::unique_ptr<Job>Start(uintptr_t address,unsigned m){auto job=std::make_unique<Job>();job->token=next_token++;job->call=Args(address,0x80,0,m);Check(!signals.RegisterThread(job->token,1),"creator registers actual child mask");Job*j=job.get();job->thread=std::thread([this,j]{current_token=j->token;Check(!signals.BindCurrent(current_token),"same-worker bound child");j->started=true;j->result=Run(j->call,&j->error);Check(!signals.DropThread(current_token),"actual child retirement after call");j->done=true;});return job;}
 void Enrolled(Job&job,unsigned n=1){Until([&]{return admissions[job.token].load()>=n||job.done.load();},"real post-enrollment Admission witness");Check(admissions[job.token].load()>=n&&!job.done,"still actual waiter after enrollment witness");}
 void Join(Job&job){Until([&]{return job.done.load();},"bounded waiter normal completion");job.thread.join();}
 int64_t PositiveWake(uintptr_t address,uint64_t value,unsigned m){int64_t result=0;Until([&]{int error=0;result=Call(address,0x81,value,m,&error);Check(result>=0&&error==731,"actual private wake/errno");return result!=0;},"bounded matching wake");return result;}
};
}
int main(int argc,char**argv){
#ifdef _WIN32
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
 std::setvbuf(stdout,nullptr,_IOLBF,0);Deadline watchdog;Harness h;alignas(64)uint32_t word=0;int error=0;
 if(argc>1){std::string mode=argv[1];FutexCall a=Args(reinterpret_cast<uintptr_t>(&word),0x80,0,0);if(mode=="unsupported")a.nr=99;else{h.allowed=0;Check(!h.signals.Queue(1,10),"real excluded pending");}h.Run(a,&error);return 2;}
 void*guard=nullptr;void*retired=nullptr;
#ifdef _WIN32
 guard=VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_NOACCESS);retired=VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);Check(guard&&retired&&VirtualFree(retired,0,MEM_RELEASE),"actual protected/unmapped keys");
#else
 guard=mmap(nullptr,4096,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);retired=mmap(nullptr,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);Check(guard!=MAP_FAILED&&retired!=MAP_FAILED&&!munmap(retired,4096),"actual protected/unmapped keys");
#endif
 unsigned records=0;
 for(unsigned m=0;m<2;++m){const char*names[]={"mismatch","align-before-range","wait-read-fault","wake-null-poison","wake-guard-zero","wake-guard-negative","wake-unmapped","wake-outside-user"};uintptr_t addresses[]={reinterpret_cast<uintptr_t>(&word),UINT64_MAX,reinterpret_cast<uintptr_t>(guard),0,reinterpret_cast<uintptr_t>(guard),reinterpret_cast<uintptr_t>(guard),reinterpret_cast<uintptr_t>(retired),UINT64_C(0x00fffffffffffffc)};uint64_t ops[]={0x80,0x80,0x80,UINT64_C(0x100000081),0x81,0x81,0x81,0x81},values[]={UINT64_C(0x100000001),0,0,UINT64_C(0x100000001),0,UINT64_C(0x1ffffffff),1,1};int64_t expected[]={-1,-1,-1,0,0,0,0,-1};int errors[]={11,22,14,731,731,731,731,14};for(unsigned i=0;i<8;++i){FutexCall a=Args(addresses[i],ops[i],values[i],m);if(i==0)a.nr=UINT64_C(0x100000062);if(i==3)a.nr=UINT64_C(0xffffffff00000062);int64_t result=h.Run(a,&error);Check(result==expected[i]&&error==errors[i],names[i]);std::printf("PROBE mode=%u case=%s result=%lld errno=%d\n",m,names[i],(long long)result,error);++records;}}
 Check(h.number_positive&&h.number_negative,"actual raw upperX0 signed64 poisons reach bridge");
 {std::vector<std::unique_ptr<Job>>jobs;for(unsigned i=0;i<3;++i)jobs.push_back(h.Start(reinterpret_cast<uintptr_t>(&word),i&1));for(auto&j:jobs)h.Enrolled(*j);Check(h.Call(reinterpret_cast<uintptr_t>(&word),0x81,2,1,&error)==2&&error==731,"wake2 selects exactly2 real enrolled tickets");Check(h.PositiveWake(reinterpret_cast<uintptr_t>(&word),2,0)==1,"remaining real ticket1");for(auto&j:jobs){h.Join(*j);Check(j->result==0&&j->error==731,"selected waiter return0");}std::puts("GROUP requested2 total3 returns3");++records;}
 {auto a=h.Start(reinterpret_cast<uintptr_t>(&word),0),b=h.Start(reinterpret_cast<uintptr_t>(&word),1);h.Enrolled(*a);h.Enrolled(*b);Check(h.Call(reinterpret_cast<uintptr_t>(&word),0x81,0,0,&error)==1,"zero count selects1 actual queued ticket");Check(h.PositiveWake(reinterpret_cast<uintptr_t>(&word),UINT64_C(0x1ffffffff),1)==1,"negative low32 selects1 actual ticket");h.Join(*a);h.Join(*b);Check(!a->result&&!b->result&&a->error==731&&b->error==731,"count quirk return/errno");std::puts("GROUP zero1 negative1 returns2");++records;}
 {Check(!h.Call(reinterpret_cast<uintptr_t>(&word),0x81,1,0,&error),"no wake credits before wait");auto j=h.Start(reinterpret_cast<uintptr_t>(&word),1);h.Enrolled(*j);h.signals.Wake(j->token)->Notify();std::this_thread::sleep_for(std::chrono::milliseconds(15));Check(!j->done,"spurious notification and priorWake store no credits");Check(h.PositiveWake(reinterpret_cast<uintptr_t>(&word),1,0)==1,"later selected wake required");h.Join(*j);Check(j->result==0&&j->error==731,"later selected return0");std::puts("GROUP no-credit later-wake1");++records;}
 for(unsigned i=0;i<64;++i){h.Write<uint32_t>(reinterpret_cast<addr_t>(&word),0);auto j=h.Start(reinterpret_cast<uintptr_t>(&word),i&1);h.Write<uint32_t>(reinterpret_cast<addr_t>(&word),1);auto wake=h.Call(reinterpret_cast<uintptr_t>(&word),0x81,1,(i+1)&1,&error);h.Join(*j);Check(error==731&&((wake==1&&j->result==0&&j->error==731)||(wake==0&&j->result==-1&&j->error==11)),"atomic compare/enroll wake race only0-or-EAGAIN");std::printf("RACE %u result=%lld errno=%d wake=%lld\n",i,(long long)j->result,j->error,(long long)wake);}std::puts("RACES count=64 permitted-wake-or-EAGAIN");++records;
 for(unsigned scenario=0;scenario<3;++scenario){bool restart=scenario!=0,change=scenario!=2;h.Write<uint32_t>(reinterpret_cast<addr_t>(&word),0);h.Action(restart);h.Handler(reinterpret_cast<uintptr_t>(&word),change);auto j=h.Start(reinterpret_cast<uintptr_t>(&word),scenario&1);h.Enrolled(*j);Check(!h.signals.Queue(j->token,10),"actual caught signal queued after ticket enrollment");if(!change){h.Enrolled(*j,2);Check(h.Read<uint32_t>(h.count)==1&&h.Read<int64_t>(h.handler_wake)==0,"real nested handler wake0 while ticket withdrawn");Check(h.PositiveWake(reinterpret_cast<uintptr_t>(&word),1,0)==1,"restart requires fresh real selected wake");}h.Join(*j);Check(h.Read<uint32_t>(h.count)==1&&h.Read<int64_t>(h.handler_wake)==0,"handler executes outside providerlocks after withdrawal");Check((!restart&&j->result==-1&&j->error==4)||(restart&&change&&j->result==-1&&j->error==11)||(restart&&!change&&!j->result&&j->error==901),"SA_RESTART original expected/re-enrollment, not automatic zero");std::printf("SIGNAL restart=%d change=%d result=%lld errno=%d nested-wake=0\n",restart,change,(long long)j->result,j->error);++records;}
 // Blocked signals and pure notifications do not become fake futex success.
 h.Action(false);h.Write<uint32_t>(reinterpret_cast<addr_t>(&word),0);uint64_t mask=SignalHost::Bit(10);Check(!h.signals.Mask(1,0,&mask,nullptr),"block creator before actual child mask capture");auto blocked=h.Start(reinterpret_cast<uintptr_t>(&word),0);Check(!h.signals.Mask(1,1,&mask,nullptr),"restore creator mask");h.Enrolled(*blocked);Check(!h.signals.Queue(blocked->token,10),"real blocked pending");std::this_thread::sleep_for(std::chrono::milliseconds(10));Check(!blocked->done,"blocked signal not futex success/EINTR");Check(h.PositiveWake(reinterpret_cast<uintptr_t>(&word),1,1)==1,"real wake releases blocked-signal waiter");h.Join(*blocked);Check(!blocked->result&&blocked->error==731,"blocked pending leaves success errno");
 // Excluded/throwing admission removes its real ticket without consuming info.
 h.allowed=0;SignalHost::Info info{};info[20]=0x73;Check(!h.signals.Queue(1,10,&info),"real excluded info");errno=88;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);bool denied=false;try{h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x80,0,0,0,0);}catch(const std::runtime_error&e){denied=std::strstr(e.what(),"outside admitted")!=nullptr;}Check(denied&&errno==88&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO&&SignalHost::NeedsPoll(h.signals.Lookup(1)),"excluded decision preserves hostenv+pending");Check(h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x81,1,0,0,0)==0,"excluded ticket fully unlinked");auto inspected=h.signals.DispatchOneAllowed(1,SignalHost::Bit(10),[&](const auto&d)->std::optional<uint64_t>{Check(d.info[20]==0x73,"excluded siginfo retained exact");return{};});Check(inspected.handled&&!inspected.error,"explicit TEST inspection only after excluded assertion");h.policy=[](uint64_t)->uint64_t{errno=999;std::fesetround(FE_UPWARD);std::feraiseexcept(FE_INVALID);throw std::runtime_error("test admission throw");};bool threw=false;try{h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x80,0,0,0,0);}catch(const std::runtime_error&){threw=true;}Check(threw&&errno==88&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"policy throw preserves env/removes ticket");h.policy={};Check(h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x81,1,0,0,0)==0,"throw leaves no stranded ticket");std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);
 // A readonly memory callback does not change reservation epochs; an actual
 // Runtime syscall import retains the already-qualified import-clear policy.
 alignas(64)uint64_t reservation_word=0x123456789abcdef0ULL;State reservation{};reservation.gpr.x0.qword=reinterpret_cast<addr_t>(&reservation_word);reservation.gpr.x30.qword=0xfeedffff;const recomp::Trace protocol{kReadonlyProbe,ReadonlyEpochProbe};h.runtime.AddTraces(&protocol,1);h.runtime.Run(reservation,protocol.address);Check(reservation.gpr.pc.qword==0xfeedffff&&readonly_probes==1,"labelled C++ protocol probe actually completes in active Runtime frame");{alignas(16)std::array<uint8_t,65536>stack{};State s{};int64_t result=99;uint32_t status=99;s.gpr.x1.qword=reinterpret_cast<addr_t>(&reservation_word);s.gpr.x2.qword=reinterpret_cast<addr_t>(&result);s.gpr.x3.qword=reinterpret_cast<addr_t>(&status);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;h.runtime.Run(s,h.Symbol("futex_exclusive"));Check(result==0&&status==1&&reservation_word==0x123456789abcdef0ULL,"actual NDK import clears LDXR/STXR without word modification");}
 std::thread foreign([&]{current_token=1;bool rejected=false;try{h.futex.Syscall(98,0,0x81,1,0,0,0);}catch(const std::runtime_error&){rejected=true;}Check(rejected,"foreign actual native owner rejected");});foreign.join();
 // Retirement wakes a direct provider wait and withdraws its ticket before throw.
 uint64_t token=h.next_token++;Check(!h.signals.RegisterThread(token,1),"retire test actual child registration");std::atomic<bool>retirement_finished{false};std::thread retire_worker([&]{current_token=token;Check(!h.signals.BindCurrent(token),"retire same-owner binding");try{h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x80,0,0,0,0);}catch(const std::runtime_error&){retirement_finished=true;}});Until([&]{return h.admissions[token].load()>0;},"actual retire-ticket enrolled");Check(!h.signals.DropThread(token),"real explicit lifetime retirement");Until([&]{return retirement_finished.load();},"retired owner exits wait by named boundary");retire_worker.join();Check(h.futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x81,1,0,0,0)==0,"retired wait leaves no ticket");Check(!h.signals.DropThread(1),"main actual lifetime teardown");bool stale=false;try{h.futex.Syscall(98,0,0x81,1,0,0,0);}catch(const std::runtime_error&){stale=true;}Check(stale,"stale owner rejected");
#ifdef _WIN32
 Check(VirtualFree(guard,0,MEM_RELEASE),"guard cleanup");
#else
 Check(!munmap(guard,4096),"guard cleanup");
#endif
 std::printf("FUTEX-HOST-SUCCESS records=%u checks=%u real-tickets/signals/restart/readonly-epochs\n",records,checks.load());return 0;
}

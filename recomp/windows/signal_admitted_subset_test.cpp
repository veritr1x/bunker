#include "signal_host.h"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <future>
#include <map>
#include <stdexcept>
#include <thread>
using bunker::windows::SignalHost;
using bunker::windows::AndroidSignalAction;
static unsigned checks=0;
static void Check(bool yes,const char*why){if(!yes)throw std::runtime_error(why);++checks;}
static constexpr uint64_t admitted=(uint64_t{1}<<29)|(uint64_t{1}<<23);
static SignalHost::Info Info(int signal,unsigned tag){SignalHost::Info info{};for(size_t n=0;n<info.size();++n)info[n]=uint8_t(tag+n);const uint32_t value=uint32_t(signal);std::memcpy(info.data(),&value,4);return info;}
struct Fixture {
 std::atomic<unsigned> notifications{0};SignalHost host;uint64_t token=0x7ffa00000123ULL;
 SignalHost::ThreadRef thread;std::map<int,SignalHost::Info> expected;
 Fixture():host([this](uint64_t t){if(t!=token)throw std::runtime_error("notify wrong owner");++notifications;}){
  Check(host.RegisterThread(token)==0&&host.BindCurrent(token)==0,"actual registered/bound model owner");thread=host.Lookup(token);
  for(int signal:{30,24,12}){AndroidSignalAction a{};a.handler=0x1000+uint64_t(signal)*4;a.flags=0x10000004;a.mask=SignalHost::Bit(14);Check(host.Action(signal,&a,nullptr)==0,"real supported model disposition");}
 }
 uint64_t Mask(){uint64_t mask=0;Check(host.Mask(token,0,nullptr,&mask)==0,"query actual current mask");return mask;}
 void Queue(int signal,unsigned tag){auto info=Info(signal,tag);Check(host.Queue(token,signal,&info)==0,"actual signal queue");if(!expected.count(signal))expected[signal]=info;}
 SignalHost::Dispatch Deliver(uint64_t allow,uint64_t select,int signal){
  const auto before=Mask();unsigned invoked=0;
  auto result=host.DispatchOneAdmittedSubset(token,allow,select,[&](const SignalHost::Delivery&d)->std::optional<uint64_t>{
   ++invoked;Check(d.token==token&&d.signal==signal,"genuine selected callback identity");Check(d.saved_mask==before,"saved mask copied before selection");Check(d.info==expected.at(signal),"selected original siginfo retained byte exact");
   Check(Mask()==((before|SignalHost::Bit(14)|SignalHost::Bit(signal))&~(SignalHost::Bit(9)|SignalHost::Bit(19))),"callback active action/self mask and unlocked callback");return {};
  });
  Check(invoked==1&&result.error==0&&result.handled&&result.restart,"actual handler ran and SA_RESTART result preserved");Check(Mask()==before,"callback normal return restored prior mask");expected.erase(signal);return result;
 }
 void Pending(uint64_t bits){auto before=Mask();uint64_t all=SignalHost::Bit(30)|SignalHost::Bit(24)|SignalHost::Bit(12);Check(host.Mask(token,0,&all,nullptr)==0,"block queued bits for public pending inspection");uint64_t out=0;Check(host.Pending(token,&out)==0&&out==bits,"all pending bits preserved");Check(host.Mask(token,2,&before,nullptr)==0,"restore actual mask after inspection");}
};
int main(){try{
 {Fixture f;f.Queue(24,11);const auto generation=f.host.Wake(f.token)->Generation();auto result=f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),{});Check(!result.error&&!result.handled,"admitted unselected24 deferred with no handler");Check(f.host.Wake(f.token)->Generation()==generation&&SignalHost::NeedsPoll(f.thread),"defer preserves wake generation and pending hint");f.Pending(SignalHost::Bit(24));f.Queue(24,99);f.Deliver(admitted,SignalHost::Bit(24),24);Check(!SignalHost::NeedsPoll(f.thread),"coalesced first siginfo delivered and hint cleared");}
 {Fixture f;f.Queue(30,21);f.Queue(24,22);f.Deliver(admitted,SignalHost::Bit(30),30);Check(SignalHost::NeedsPoll(f.thread),"unselected24 remains eligible after30 callback");f.Pending(SignalHost::Bit(24));f.Deliver(admitted,SignalHost::Bit(24),24);Check(!SignalHost::NeedsPoll(f.thread),"both genuine callbacks settle pending hint");}
 {Fixture f;f.Queue(30,31);f.Queue(24,32);std::promise<void> queued;auto done=queued.get_future();std::thread producer([&]{auto info=Info(12,33);if(f.host.Queue(f.token,12,&info))std::terminate();queued.set_value();});done.get();producer.join();f.expected[12]=Info(12,33);
  const auto mask=f.Mask(),generation=f.host.Wake(f.token)->Generation();unsigned invoked=0;auto result=f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),[&](const auto&)->std::optional<uint64_t>{++invoked;return {};});Check(result.error==95&&!result.handled&&!invoked,"mixed unknown queued before selection rejects all atomically");Check(f.Mask()==mask&&f.host.Wake(f.token)->Generation()==generation&&SignalHost::NeedsPoll(f.thread),"atomic rejection preserves mask generation and hint");f.Pending(admitted|SignalHost::Bit(12));f.Deliver(admitted|SignalHost::Bit(12),SignalHost::Bit(30),30);f.Deliver(admitted|SignalHost::Bit(12),SignalHost::Bit(24),24);f.Deliver(admitted|SignalHost::Bit(12),SignalHost::Bit(12),12);}
 {Fixture f;f.Queue(30,41);f.Queue(24,42);auto result=f.host.DispatchOneAdmittedSubset(f.token,admitted,0,{});Check(!result.error&&!result.handled,"zero selected mask defers admitted bits");f.Pending(admitted);result=f.host.DispatchOneAdmittedSubset(f.token,SignalHost::Bit(30),admitted,{});Check(result.error==22&&!result.handled,"invalid selected subset rejected unchanged");f.Pending(admitted);f.Deliver(admitted,SignalHost::Bit(30),30);f.Deliver(admitted,SignalHost::Bit(24),24);}
 {Fixture f;f.Queue(12,51);auto result=f.host.DispatchOneAdmittedSubset(f.token,admitted,0,{});Check(result.error==95&&!result.handled,"unknown eligible rejected even when selected mask zero");f.Pending(SignalHost::Bit(12));f.Deliver(SignalHost::Bit(12),SignalHost::Bit(12),12);}
 {Fixture f;f.Queue(12,61);f.Queue(30,62);uint64_t block=SignalHost::Bit(12);Check(f.host.Mask(f.token,0,&block,nullptr)==0,"mask unknown signal before subset selection");f.Deliver(admitted,SignalHost::Bit(30),30);Check(!SignalHost::NeedsPoll(f.thread),"blocked unknown does not reject eligible30 or request poll");f.Pending(block);Check(f.host.Mask(f.token,1,&block,nullptr)==0,"unblock retained unknown");Check(f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),{}).error==95,"retained unknown rejects once eligible");f.Deliver(block,block,12);}
 {Fixture f;f.Queue(30,71);SignalHost::Dispatch foreign;std::thread worker([&]{foreign=f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),{});});worker.join();Check(foreign.error==1&&!foreign.handled,"foreign native thread cannot dispatch owner");f.Pending(SignalHost::Bit(30));Check(f.host.DispatchOneAdmittedSubset(0xabcdef,admitted,SignalHost::Bit(30),{}).error==3,"unknown owner rejected");Check(f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),{}).error==38,"missing boundary does not consume signal");f.Pending(SignalHost::Bit(30));AndroidSignalAction action{};Check(f.host.Action(30,&action,nullptr)==0,"change queued disposition to real default");Check(f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),[](const auto&)->std::optional<uint64_t>{return {};}).error==38,"default queued disposition rejected without consume");f.Pending(SignalHost::Bit(30));Check(f.host.DropThread(f.token)==0,"actual owner retired");Check(f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),{}).error==3&&!SignalHost::NeedsPoll(f.thread),"retired owner cannot dispatch");}
 {Fixture f;f.Queue(30,81);const auto original=f.Mask();auto result=f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),[&](const auto&d)->std::optional<uint64_t>{Check(d.info==f.expected.at(30),"context-edit callback receives original info");return original|SignalHost::Bit(13)|SignalHost::Bit(9);});Check(result.handled&&f.Mask()==(original|SignalHost::Bit(13)),"real callback mask edit restored with unblockable bits removed");}
 {Fixture f;f.Queue(30,91);f.Queue(24,92);const auto original=f.Mask();bool caught=false;try{f.host.DispatchOneAdmittedSubset(f.token,admitted,SignalHost::Bit(30),[&](const auto&d)->std::optional<uint64_t>{Check(d.info==f.expected.at(30),"throwing callback receives original selected info");throw std::runtime_error("actual callback failure");});}catch(const std::runtime_error&e){caught=std::string(e.what())=="actual callback failure";}Check(caught&&f.Mask()==original,"throwing real callback restores previous mask");f.expected.erase(30);f.Pending(SignalHost::Bit(24));f.Deliver(admitted,SignalHost::Bit(24),24);}
 {Fixture f;f.Queue(30,101);f.Queue(12,102);auto result=f.host.DispatchOneAdmitted(f.token,SignalHost::Bit(30),{});Check(result.error==95&&!result.handled,"existing admitted API retains strict excluded rejection");f.Pending(SignalHost::Bit(30)|SignalHost::Bit(12));unsigned callbacks=0;result=f.host.DispatchOneAllowed(f.token,SignalHost::Bit(30),[&](const auto&d)->std::optional<uint64_t>{++callbacks;Check(d.signal==30&&d.info==f.expected.at(30),"existing allowed API selected callback unchanged");return {};});Check(!result.error&&result.handled&&callbacks==1,"existing allowed API still ignores excluded pending");f.expected.erase(30);f.Deliver(SignalHost::Bit(12),SignalHost::Bit(12),12);}
 std::printf("SIGNAL-ADMITTED-SUBSET-PASS checks=%u atomic_unknown_reject=1 selected30_retains24=1 real_callbacks_and_masks=1 old_APIs_unchanged=1\n",checks);
}catch(const std::exception&e){std::fprintf(stderr,"SIGNAL-ADMITTED-SUBSET-FAIL %s\n",e.what());return 1;}}

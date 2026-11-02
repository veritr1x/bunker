#include <cfenv>
#include "signal_host.h"
#include "game_collector_mask.h"
#include <cstdio>
#include <stdexcept>

using bunker::windows::SignalHost;
using bunker::windows::AndroidSignalAction;
namespace {
unsigned checks=0;
void Check(bool value,const char *message){++checks;if(!value)throw std::runtime_error(message);}
uint64_t Mask(SignalHost &host){uint64_t mask=0;Check(!host.Mask(1,0,nullptr,&mask),"actual owner mask query");return mask;}
AndroidSignalAction Action(){AndroidSignalAction action{};action.handler=0x825beb3c;action.flags=0x10000004;action.mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15));return action;}
void Setup(SignalHost &host){Check(!host.RegisterThread(1)&&!host.BindCurrent(1),"real model owner");auto action=Action();Check(!host.Action(30,&action,nullptr),"original stop action");action.flags=0x10000000;Check(!host.Action(24,&action,nullptr),"original restart action");}
void Transition(uint64_t requested,bool nested){
 SignalHost host;Setup(host);Check(!host.Mask(1,2,&requested,nullptr),"ordinary mask setup");const auto interrupted=Mask(host);Check(GameCollectorWaitMask::Ordinary(interrupted),"ordinary predispatch eligibility");
 Check(!host.Queue(1,30),"real queued stop");unsigned outer=0,restart=0;
 auto result=host.DispatchOneAllowed(1,SignalHost::Bit(30),[&](const auto &selected)->std::optional<uint64_t>{
  ++outer;const auto current=Mask(host);
  Check(selected.saved_mask==interrupted,"selected mask is interrupted snapshot");
  Check(!GameCollectorWaitMask::Ordinary(current),"regression: handler mask correctly fails OLD ordinary predicate");
  Check(GameCollectorWaitMask::SelectedStop(1,current,selected),"actual selected stop satisfies production phase predicate");
  Check((current&SignalHost::Bit(24))&&(current&SignalHost::Bit(30)),"original action blocks restart/self during stop handler");
  auto wrong=selected;wrong.token=2;Check(!GameCollectorWaitMask::SelectedStop(1,current,wrong),"foreign selected token rejected");
  wrong=selected;wrong.signal=24;Check(!GameCollectorWaitMask::SelectedStop(1,current,wrong),"nested restart cannot impersonate outer stop");
  wrong=selected;wrong.saved_mask|=SignalHost::Bit(30);Check(!GameCollectorWaitMask::SelectedStop(1,current,wrong),"ineligible interrupted stop rejected");
  wrong=selected;wrong.saved_mask|=SignalHost::Bit(24);Check(!GameCollectorWaitMask::SelectedStop(1,current,wrong),"ineligible interrupted restart rejected");
  wrong=selected;wrong.action.handler=0x825b2af4;Check(!GameCollectorWaitMask::SelectedStop(1,current,wrong),"direct substituted handler rejected");
  wrong=selected;wrong.action.flags^=0x08000000;Check(!GameCollectorWaitMask::SelectedStop(1,current,wrong),"different selected flags rejected");
  wrong=selected;wrong.action.mask^=SignalHost::Bit(10);Check(!GameCollectorWaitMask::SelectedStop(1,current,wrong),"different selected action mask rejected");
  Check(!GameCollectorWaitMask::SelectedStop(1,interrupted,selected),"uninstalled action mask rejected");
  Check(!GameCollectorWaitMask::SelectedStop(1,current^SignalHost::Bit(2),selected),"additional current mask bit rejected");
  Check(!GameCollectorWaitMask::SelectedStop(1,current|SignalHost::Bit(9),selected),"unblockable bit in current mask rejected");
  if(nested){
   Check(!host.Queue(1,24),"restart queues while stop action blocks it");uint64_t pending=0;Check(!host.Pending(1,&pending)&&pending==SignalHost::Bit(24),"restart remains blocked pending before real Suspend");
   const auto temporary=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(24));
   Check(host.Suspend(1,temporary,[&](const auto &delivery)->std::optional<uint64_t>{++restart;Check(delivery.signal==24&&delivery.saved_mask==current,"actual temporary-mask selection preserves outer saved mask");Check(!GameCollectorWaitMask::SelectedStop(1,Mask(host),delivery),"exact nested restart stays a separate profile");return {};})==4,"real restart produces EINTR without synthetic wake/ack");
   Check(restart==1&&Mask(host)==current,"Suspend restores actual outer handler mask");
  }
  return {};
 });
 Check(!result.error&&result.handled&&outer==1,"actual stop delivered once");Check(Mask(host)==interrupted,"normal return restores exact interrupted mask");Check(!SignalHost::NeedsPoll(host.Lookup(1)),"actual selected pending bits exhausted");Check(!host.DropThread(1),"actual owner retirement");
}
void RejectionAndUnbound(){
 SignalHost host;Setup(host);const auto initial=Mask(host);
 for(int signal:{30,24}){auto blocked=initial|SignalHost::Bit(signal);Check(!host.Mask(1,2,&blocked,nullptr),"blocked ordinary setup");Check(!GameCollectorWaitMask::Ordinary(Mask(host)),"ordinary eligibility unchanged and strict");}
 Check(!host.Mask(1,2,&initial,nullptr)&&!host.Queue(1,30),"unbound dispatch setup");
 auto result=host.DispatchOneAllowed(1,SignalHost::Bit(30),{});Check(result.error==38&&!result.handled&&SignalHost::NeedsPoll(host.Lookup(1))&&Mask(host)==initial,"missing boundary does not consume or install mask");
 Check(host.DispatchOneAllowed(1,SignalHost::Bit(30),[&](const auto &d)->std::optional<uint64_t>{Check(GameCollectorWaitMask::SelectedStop(1,Mask(host),d),"later real boundary sees proper selected phase");return {};}).handled,"later bound dispatch");
 Check(!host.DropThread(1),"unbound case retirement");
}
}
int main(){try{Transition(0,false);Transition(SignalHost::Bit(2),false);Transition(SignalHost::Bit(10),false);Transition(0,true);RejectionAndUnbound();std::printf("GAME-COLLECTOR-MASK-PASS checks=%u real-DispatchOneAllowed real-nested-Suspend no-game-GC\n",checks);return 0;}catch(const std::exception&e){std::fprintf(stderr,"collector mask test: %s\n",e.what());return 1;}}

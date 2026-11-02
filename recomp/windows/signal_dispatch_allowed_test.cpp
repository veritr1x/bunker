// Reuse the accepted sender's real NDK handler/stack/identity harness unchanged.
// Its original main remains compiled as an unused external function, not run.
#define main sender_reused_original_main
#include "signal_sender_test.cpp"
#undef main
#include <atomic>
#include <vector>
namespace {
SignalHost::Info Tagged(int signal,uint8_t tag){SignalHost::Info info{};info[0]=uint8_t(signal);info[16]=tag;return info;}
uint64_t GetMask(SignalHost &s,uint64_t token){uint64_t value=0;Check(!s.Mask(token,0,nullptr,&value),"mask snapshot");return value;}
void Setup(SignalHost &s,uint64_t token=1){Check(!s.RegisterThread(token)&&!s.BindCurrent(token),"allowed-dispatch actual owner");AndroidSignalAction a{};a.handler=0x1000;a.flags=4;Check(!s.Action(24,&a,nullptr)&&!s.Action(30,&a,nullptr),"two real dispositions");}
void Select(){
  SignalHost s;Setup(s);const auto original=GetMask(s,1);auto low=Tagged(24,0xa5),high=Tagged(30,0x5a);Check(!s.Queue(1,24,&low)&&!s.Queue(1,30,&high),"queue lower restart before higher stop");
  unsigned calls=0;auto boundary=[&](const auto &d)->std::optional<uint64_t>{++calls;Check(d.signal==30&&d.info==high,"allowed30 bypasses lower pending24 without replacing info");Check(GetMask(s,1)==(original|SignalHost::Bit(30)),"handler automatic mask intact outside mutex");return {};};
  auto none=s.DispatchOneAllowed(1,0,boundary);Check(!none.error&&!none.handled&&!calls&&GetMask(s,1)==original&&SignalHost::NeedsPoll(s.Lookup(1)),"allowed0 leaves all pending/mask/poll intact");
  auto selected=s.DispatchOneAllowed(1,SignalHost::Bit(30),boundary);Check(!selected.error&&selected.handled&&calls==1&&GetMask(s,1)==original&&SignalHost::NeedsPoll(s.Lookup(1)),"stop consumed while unallowed restart remains runnable");
  auto blocked=s.DispatchOneAllowed(1,SignalHost::Bit(30),boundary);Check(!blocked.error&&!blocked.handled&&calls==1&&SignalHost::NeedsPoll(s.Lookup(1)),"unallowed restart is not consumed by later stop-only boundary");
  auto retained=s.DispatchOneAllowed(1,SignalHost::Bit(24),[&](const auto &d)->std::optional<uint64_t>{++calls;Check(d.signal==24&&d.info==low,"deferred restart retains original complete info");return {};});Check(retained.handled&&!SignalHost::NeedsPoll(s.Lookup(1))&&calls==2,"deferred restart delivered only when explicitly allowed");
  uint64_t mask=SignalHost::Bit(30);Check(!s.Mask(1,0,&mask,nullptr)&&!s.Queue(1,30,&high),"masked pending setup");uint64_t pending=0;Check(!s.Pending(1,&pending)&&pending==mask,"blocked pending retained");auto masked=s.DispatchOneAllowed(1,UINT64_MAX,boundary);Check(!masked.error&&!masked.handled&&!SignalHost::NeedsPoll(s.Lookup(1)),"allowed cannot override blocked signal mask");Check(!s.Mask(1,1,&mask,nullptr)&&s.DispatchOneAllowed(1,UINT64_MAX,boundary).handled,"unblock then allowedall delivers pending");
  Check(s.DispatchOneAllowed(999,UINT64_MAX,boundary).error==3,"unknown target status");Check(!s.RegisterThread(2)&&!s.DropThread(2)&&s.DispatchOneAllowed(2,0,boundary).error==3,"dead target status even allowed0");
  Check(!s.Queue(1,30,&high),"wrong-owner pending setup");SignalHost::Dispatch wrong{};std::thread foreign([&]{wrong=s.DispatchOneAllowed(1,UINT64_MAX,boundary);});foreign.join();Check(wrong.error==1&&SignalHost::NeedsPoll(s.Lookup(1)),"wrong owner cannot clear pending");Check(s.DispatchOneAllowed(1,SignalHost::Bit(30),boundary).handled,"owner receives unchanged wrong-owner pending");
  low=Tagged(24,7);auto newer=Tagged(24,9);Check(!s.Queue(1,24,&low)&&!s.Queue(1,24,&newer),"coalesced deferred restart");Check(!s.DispatchOneAllowed(1,SignalHost::Bit(30),boundary).handled,"coalesced restart stays deferred");Check(s.DispatchOneAllowed(1,SignalHost::Bit(24),[&](const auto &d)->std::optional<uint64_t>{Check(d.info==low,"first coalesced info survives allowed filter");return {};}).handled,"coalesced restart delivery");
}
void DefaultEquivalent(){
  SignalHost legacy,allowed;Setup(legacy);Setup(allowed);auto a=Tagged(24,4),b=Tagged(30,8);Check(!legacy.Queue(1,30,&b)&&!legacy.Queue(1,24,&a)&&!allowed.Queue(1,30,&b)&&!allowed.Queue(1,24,&a),"default equivalence setup");
  std::vector<SignalHost::Info> x,y;std::vector<int> sx,sy;
  for(unsigned n=0;n<3;++n){auto left=legacy.DispatchOne(1,[&](const auto &d)->std::optional<uint64_t>{sx.push_back(d.signal);x.push_back(d.info);return {};});auto right=allowed.DispatchOneAllowed(1,UINT64_MAX,[&](const auto &d)->std::optional<uint64_t>{sy.push_back(d.signal);y.push_back(d.info);return {};});Check(left.error==right.error&&left.handled==right.handled&&left.restart==right.restart,"default/all dispatch result equivalence");}
  Check(sx==sy&&sx==std::vector<int>({24,30})&&x==y&&GetMask(legacy,1)==GetMask(allowed,1),"default/all order info mask equivalence");
}
void Concurrent(){
  SignalHost s;Setup(s);auto retained=Tagged(24,0xa5);Check(!s.Queue(1,24,&retained),"concurrent retained restart");std::atomic<bool> done{false};std::atomic<int> error{0};unsigned delivered=0;
  std::thread queue([&]{for(unsigned i=0;i<512;++i){auto restart=Tagged(24,uint8_t(i)),stop=Tagged(30,uint8_t(i));if(s.Queue(1,24,&restart)||s.Queue(1,30,&stop))error=1;}done=true;});
  auto boundary=[&](const auto &d)->std::optional<uint64_t>{Check(d.signal==30,"atomic allowed selection never consumes concurrent lower restart");++delivered;return {};};
  while(!done.load()){auto result=s.DispatchOneAllowed(1,SignalHost::Bit(30),boundary);Check(!result.error,"concurrent dispatch status");}
  queue.join();Check(!error.load(),"concurrent actual queue calls succeeded");while(s.DispatchOneAllowed(1,SignalHost::Bit(30),boundary).handled){}
  Check(delivered>0&&SignalHost::NeedsPoll(s.Lookup(1)),"at least one stop delivered while restart remains pending");Check(s.DispatchOneAllowed(1,SignalHost::Bit(24),[&](const auto &d)->std::optional<uint64_t>{Check(d.signal==24&&d.info==retained,"original restart info survives enrollment/selection races");return {};}).handled&&!SignalHost::NeedsPoll(s.Lookup(1)),"final restart explicitly drained");
}
void NdkHandler(){
  Harness h;AndroidSignalAction action{};Check(!h.model.Action(30,nullptr,&action)&&!h.model.Action(24,&action,nullptr),"reuse exact NDK SA_SIGINFO handler for both signals");
  h.uid=17;Check(!h.Call(h.invoke,kToken,24,1),"actual NDK lower restart send");h.uid=29;Check(!h.Call(h.invoke,kToken,30,0),"actual NDK stop send");
  uint64_t allow=SignalHost::Bit(30);constexpr addr_t checkpoint_allowed=kErrno+32;
  h.runtime.AddImport(checkpoint_allowed,[&](State &state){try{const State original=state;auto result=h.model.DispatchOneAllowed(kToken,allow,[&](const auto &d){return h.delivery->Deliver(d);});Check(!result.error&&!std::memcmp(&state,&original,sizeof(state)),"allowed actual NDK frame returns exact interrupted State");state.gpr.x0.qword=result.handled;}catch(const std::exception&e){std::fprintf(stderr,"allowed checkpoint: %s\n",e.what());std::abort();}catch(...){std::abort();}});
  Check(h.Call(checkpoint_allowed)==1&&h.report.value.calls==1,"higher stop runs first in actual NDK handler");h.Validate(29);Check(h.Pending()&&h.Call(checkpoint_allowed)==0&&h.report.value.calls==1,"unallowed restart retained without an extra handler");
  allow=SignalHost::Bit(24);Check(h.Call(checkpoint_allowed)==1&&h.report.value.calls==2&&!h.Pending(),"actual deferred restart handler runs when allowed");
  std::array<uint8_t,128> expected{};auto store=[&](size_t off,uint32_t value){for(unsigned i=0;i<4;++i)expected[off+i]=uint8_t(value>>(8*i));};store(0,24);store(8,uint32_t(-6));store(16,uint32_t(h.libc.ProcessId()));store(20,17);
  Check(h.report.value.signal_number==24&&!std::memcmp(h.report.value.info,expected.data(),128)&&h.report.value.handler_error==731&&h.guest_error==731,"deferred actual NDK restart gets original full sender info and errno");
}
}
int main(){
#ifdef _WIN32
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
#endif
  try{Select();DefaultEquivalent();Concurrent();NdkHandler();std::printf("SIGNAL-DISPATCH-ALLOWED-SUCCESS checks=%u actual-NDK-handler-reused no-game-GC\n",checks);return 0;}catch(const std::exception&e){std::fprintf(stderr,"allowed-dispatch fixture: %s\n",e.what());return 1;}
}

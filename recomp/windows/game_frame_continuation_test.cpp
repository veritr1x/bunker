#include "unity_lifecycle.h"
#include <atomic>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include "game_frame_run_policy.h"

using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};
void Check(bool value,const char *why){++checks;if(!value)throw std::runtime_error(why);}
template<class F>void Reject(F action,const char *why){bool rejected=false;try{action();}catch(const std::invalid_argument&){rejected=true;}Check(rejected,why);}
GameFrameRunOptions Parse(std::vector<std::string> values,int &remaining){
  std::vector<char*> args;for(auto &s:values)args.push_back(s.data());remaining=int(args.size());return ParseGameFrameRunTail(remaining,args.data());
}
void ParseCases(){
  const std::vector<std::string> original={"game.exe","native","original.apk","storage","--frame-gate","1280","720","ANGLE","--mute-audio","--collector-delivery","--first-frame","--firebase-app-dll","SDK.dll"};
  int argc=0;auto defaults=Parse(original,argc);Check(argc==13&&!defaults.Continuing(),"default SDK/profile argument vector stays unchanged");
  auto bounded=original;bounded.insert(bounded.end(),{"--run-frames","180"});auto b=Parse(bounded,argc);Check(argc==13&&b.mode==GameFrameRunOptions::Mode::ReturnedFrames&&b.returned_frames==180,"explicit bounded tail leaves original Firebase/profile positions intact");
  auto until=original;until.push_back("--run-until-close");auto u=Parse(until,argc);Check(argc==13&&u.mode==GameFrameRunOptions::Mode::UntilClose,"close-driven tail leaves original argument vector intact");
  auto no_sdk=original;no_sdk.resize(11);no_sdk.insert(no_sdk.end(),{"--run-frames","180"});Parse(no_sdk,argc);Check(argc==11,"optional SDK pair is not invented or required");
  for(const auto &bad:std::vector<std::string>{"","0","00","-1","-0","+1"," 1","1 ","1x","0x10","1.0","18446744073709551616","999999999999999999999999999999999"})Reject([&]{Parse({"game.exe","--run-frames",bad},argc);},"malformed/zero/overflow frame limit rejected");
  Reject([&]{Parse({"game.exe","--run-frames"},argc);},"missing count rejected");
  auto one=Parse({"game.exe","--run-frames","1"},argc);Check(one.ReachedLimit(1)&&!one.ReachedLimit(0)&&!one.SnapshotBeforeNextFrame(0),"one returned frame is exact and has no later snapshot request");
  auto max=Parse({"game.exe","--run-frames","18446744073709551615"},argc);Check(max.returned_frames==UINT64_MAX&&max.ReachedLimit(UINT64_MAX)&&!max.ReachedLimit(UINT64_MAX-1),"full positive uint64 range without integer wrap");
  Check(!b.StopAfterReturnedFrame(179,true)&&b.StopAfterReturnedFrame(180,false),"witness cannot stop explicit180-frame mode");
  Check(defaults.StopAfterReturnedFrame(36,true)&&!defaults.StopAfterReturnedFrame(36,false),"default stops on the original witness only");
  Check(!u.StopAfterReturnedFrame(UINT64_MAX,true),"until-close mode does not invent a frame or witness limit");
  unsigned snapshots=0;for(uint64_t n=0;n<=181;++n)snapshots+=b.SnapshotBeforeNextFrame(n);Check(snapshots==1&&b.SnapshotBeforeNextFrame(179),"bounded later snapshot hook occurs exactly after return179");
  for(auto mode:{b,u}){
    RequireGameFrameRunProfile(mode,true,true);
    Reject([&]{RequireGameFrameRunProfile(mode,false,true);},"continuation without first-frame capture profile rejected");
    Reject([&]{RequireGameFrameRunProfile(mode,true,false);},"continuation without muted collector profile rejected");
    Reject([&]{RequireGameFrameRunProfile(mode,false,false);},"continuation without both profile guards rejected");
  }
  RequireGameFrameRunProfile(defaults,false,false);Check(!defaults.Continuing(),"legacy profiles retain default behavior");
}
struct Result {uint64_t returned=0,requests=0,renders=0,snapshot_hooks=0;unsigned resumes=0,focuses=0,cleanups=0;bool guest_false=false,closed=false;};
Result LifecycleCase(GameFrameRunOptions options,uint64_t witness_at,uint64_t close_at,uint64_t false_at,bool exercise_focus){
  bunker::jni::Host java([](addr_t){return true;});java.DefineClass("com/unity3d/player/UnityPlayer");java.DefineClass("android/view/Surface");auto player=java.NewInstance("com/unity3d/player/UnityPlayer"),surface=java.NewInstance("android/view/Surface");
  const auto caller=std::this_thread::get_id();std::thread::id worker;Result result;std::atomic<uint64_t> renders{0};unsigned resumes=0,focuses=0,cleanups=0;
  auto run=[&](addr_t entry,const std::vector<addr_t>&args)->uint64_t{
    Check(std::this_thread::get_id()!=caller,"native lifecycle callbacks stay on the dedicated worker");if(worker==std::thread::id{})worker=std::this_thread::get_id();Check(worker==std::this_thread::get_id(),"every continuation keeps the same UnityMain");
    Check(args.size()>=2&&args[0]==java.EnvAddress()&&args[1]!=0,"callback receives real attached JNIEnv and receiver");
    if(entry==3){++resumes;return 0;}if(entry==4){++focuses;return 0;}if(entry==5){auto n=++renders;return n!=false_at;}return 0;
  };
  UnitySurfaceLifecycle q(java,run,{1,2},player,[&]{Check(java.EnvAddress()!=0,"worker cleanup precedes real JNI detach");++cleanups;});q.ConfigureOneFrame({3,4,5,6,7});q.AfterInitJni();q.Start();q.SurfaceCreated(surface);q.SurfaceChanged(surface);q.WaitIdle();q.ActivityResumed();q.WindowFocusChanged(true);
  const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(10);bool next=false,keep=false;
  while(!result.closed){
    Check(std::chrono::steady_clock::now()<deadline,"bounded standalone lifecycle fixture completed before watchdog");
    if(!next)if(auto completed=q.PollFrame()){
      keep=*completed;++result.returned;result.guest_false=!keep;
      if(close_at&&result.returned==close_at){result.closed=true;break;}
      if(!keep||options.StopAfterReturnedFrame(result.returned,result.returned>=witness_at))break;
      if(options.SnapshotBeforeNextFrame(result.returned))++result.snapshot_hooks;
      if(exercise_focus&&result.returned==10){
        q.WaitIdle();q.WindowFocusChanged(false);q.WaitIdle();const auto before=renders.load();Check(!q.RequestNextFrame(),"real lifecycle refuses continuation while unfocused");Check(renders==before,"focus prerequisite is never bypassed");q.WindowFocusChanged(true);q.WaitIdle();
      }
      next=true;
    }
    if(next&&q.RequestNextFrame())next=false;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  q.WaitIdle();auto status=q.Describe();result.requests=status.requested_frames;result.renders=status.rendered;Check(result.renders==result.returned&&renders==result.returned,"each observed completion corresponds to one actual lifecycle render callback");Check(resumes==1,"continuation never repeats nativeResume");
  if(!keep){bool rejected=false;try{q.RequestNextFrame();}catch(const std::logic_error&){rejected=true;}Check(rejected,"guest false forbids additional native render requests");}
  q.PauseNative(true);q.SurfaceDestroyed();q.Stop();Check(cleanups==1,"same worker is cleaned up exactly once");Check(java.PendingException().empty(),"standalone lifecycle leaves caller JNI state clear");result.resumes=resumes;result.focuses=focuses;result.cleanups=cleanups;java.DeleteLocalReference(surface);java.DeleteLocalReference(player);return result;
}
}
int main(){
  try{
    Check(sizeof(State)==1200&&sizeof(addr_t)==8&&sizeof(Memory*)==8,"actual selected State/address/Memory-pointer ABI sizes");
    ParseCases();GameFrameRunOptions bounded;bounded.mode=GameFrameRunOptions::Mode::ReturnedFrames;bounded.returned_frames=180;auto b=LifecycleCase(bounded,3,0,0,true);Check(b.returned==180&&b.requests==180&&b.snapshot_hooks==1&&b.focuses==3,"180 returns survive early witness and a genuine lifecycle focus interruption");
    auto d=LifecycleCase({},3,0,0,false);Check(d.returned==3&&d.requests==3&&!d.snapshot_hooks,"default returns stop at first witness");
    GameFrameRunOptions until;until.mode=GameFrameRunOptions::Mode::UntilClose;auto c=LifecycleCase(until,3,17,0,false);Check(c.closed&&c.returned==17&&c.requests==17,"close-driven fixture stops without queuing another render");
    auto f=LifecycleCase(bounded,3,0,7,false);Check(f.guest_false&&f.returned==7&&f.requests==7,"original false result ends a requested180-frame sequence");
    std::printf("FRAME-CONTINUATION-PASS checks=%u bounded=180 default=3 close=17 guest_false=7 stable_worker=1 native_resume=1 snapshot_hooks=1 parser_negative=20 transparent_callbacks=1 State=%zu Memory64=%d\n",checks.load(),sizeof(State),int(sizeof(addr_t)==8&&sizeof(Memory*)==8));return 0;
  }catch(const std::exception &e){std::fprintf(stderr,"FRAME-CONTINUATION-FAIL %s\n",e.what());return 1;}
}

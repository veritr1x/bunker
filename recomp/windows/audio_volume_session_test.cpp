#include "audio_volume_session.h"
#include <cstdio>
#include <limits>
#include <stdexcept>
#include <thread>

using namespace bunker::windows;
namespace {unsigned checks=0;void Check(bool value,const char *why){++checks;if(!value)throw std::runtime_error(why);}template<class F>void Reject(F f,const char *why){bool caught=false;try{f();}catch(const std::exception&){caught=true;}Check(caught,why);}}
int main(){
  AudioVolumeObserver::Snapshot value;value.available=value.volume_registered=value.defaults_registered=true;value.scalar=.95f;
  Check(AudioVolumeSession::MusicIndex(value)==1,"positive real scalar profile is index1");value.scalar=0;Check(AudioVolumeSession::MusicIndex(value)==0,"zero scalar profile is index0");value.scalar=.95f;value.muted=true;Check(AudioVolumeSession::MusicIndex(value)==0,"mute profile is index0");value.muted=false;
  for(float scalar:{-1.0f,2.0f,std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()}){auto bad=value;bad.scalar=scalar;Reject([&]{AudioVolumeSession::MusicIndex(bad);},"invalid endpoint scalar rejected");}
  for(int which=0;which<6;++which){auto bad=value;if(which==0)bad.available=false;if(which==1)bad.stopped=true;if(which==2)bad.status=-1;if(which==3)bad.callback_status=-1;if(which==4)bad.volume_registered=false;if(which==5)bad.defaults_registered=false;Reject([&]{AudioVolumeSession::MusicIndex(bad);},"unavailable endpoint/observer state rejected");}
  bunker::jni::Host java([](addr_t){return true;});java.DefineClass("android/content/Context");java.DefineClass("com/unity3d/player/UnityPlayer");java.DefineClass("com/unity3d/player/AudioVolumeHandler",{{"onAudioVolumeChanged","(I)V",false,true}});
  AudioVolumeSession::DeclareFields(java);
  auto context=java.NewHostInstance("android/content/Context",std::make_shared<int>(9)),player=java.NewInstance("com/unity3d/player/UnityPlayer");
  const char *name="com/unity3d/player/AudioVolumeHandler";State state{};state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=reinterpret_cast<addr_t>(name);java.InvokeEnv(6,state);auto clazz=state.gpr.x0.qword;
  const bunker::jni::NativeMethod method{reinterpret_cast<addr_t>("onAudioVolumeChanged"),reinterpret_cast<addr_t>("(I)V"),0x73000100};state={};state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=clazz;state.gpr.x2.qword=reinterpret_cast<addr_t>(&method);state.gpr.x3.qword=1;java.InvokeEnv(215,state);Check(state.gpr.x0.dword==0,"synthetic native callback registered");
  unsigned calls=0;auto owner=std::this_thread::get_id();
  std::unique_ptr<AudioVolumeSession> active;
  try{active=std::make_unique<AudioVolumeSession>(java,[&](addr_t entry,const std::vector<addr_t>&args){Check(entry==0x73000100&&args.size()==3,"exact instance callback signature");Check(std::this_thread::get_id()==owner&&args[0]==java.EnvAddress(),"callback is dispatched on UI caller");Check(args[1]&&args[2]<=1,"typed callback receiver and explicit two-level profile");++calls;return 0;},context,player);}
  catch(const std::runtime_error &error){
    const std::string reason=error.what();Check(reason.find("read-only audio endpoint/notification prerequisite is unavailable:")==0&&reason.find("status=")!=std::string::npos&&reason.find("callback=")!=std::string::npos,"unavailable native prerequisite retains HRESULT/registration diagnostics");
    Check(calls==0&&!java.GetObjectFieldValue(player,"m_AudioVolumeHandler","Lcom/unity3d/player/AudioVolumeHandler;"),"failed real observer construction publishes no receiver/callback");Check(java.PendingException().empty(),"native device absence does not fabricate a Java exception");
    std::printf("Read-only audio session: %u checks; real endpoint unavailable, checked constructor rejection: %s; available-endpoint lifecycle was not rerun\n",checks,error.what());return 0;
  }
  auto &session=*active;
  Check(calls==0,"constructor does not invent an initial native callback");auto initial=session.InitialSnapshot();Check(initial.available&&initial.volume_registered&&initial.defaults_registered,"real endpoint is subscribed");Check(!initial.device_id.empty()&&initial.owner_thread!=0,"real endpoint identity/MTA owner reported");
  auto field=java.GetObjectFieldValue(player,"m_AudioVolumeHandler","Lcom/unity3d/player/AudioVolumeHandler;");Check(field!=0,"real receiver is retained in actual player field");java.DeleteLocalReference(field);
  bool wrong_thread=false;std::thread worker([&]{try{session.Poll();}catch(const std::logic_error&){wrong_thread=true;}});worker.join();Check(wrong_thread,"COM/native worker cannot impersonate UI callback caller");
  auto dispatched=session.Poll();Check(dispatched==calls,"only actual changed mute-profile events are dispatched");session.Pause();session.Pause();Check(session.Poll()==0,"paused observer has no future callbacks");Check(!java.GetObjectFieldValue(player,"m_AudioVolumeHandler","Lcom/unity3d/player/AudioVolumeHandler;"),"pause clears player field");Check(java.PendingException().empty(),"checked service operations preserve clear Java exception state");
  {AudioVolumeSession resumed(java,[](addr_t,const std::vector<addr_t>&){return uint64_t(0);},context,player);Check(resumed.InitialSnapshot().available,"a later resume constructs a fresh real observer without redeclaring Java fields");resumed.Pause();}
  std::printf("Read-only audio session: %u checks passed; real endpoint/observer, synthetic native callback runner\n",checks);
}

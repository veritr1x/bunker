#include "audio_volume_session.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <thread>

namespace bunker::windows {
namespace {
constexpr const char *kHandler="com/unity3d/player/AudioVolumeHandler";
constexpr const char *kField="m_AudioVolumeHandler";
constexpr const char *kFieldType="Lcom/unity3d/player/AudioVolumeHandler;";
void RequireType(jni::Host &java,addr_t object,const char *name){
  auto retained=java.NewLocalReference(object);
  if(!retained)throw std::invalid_argument("audio observer requires live configured Java objects");
  State state{};state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=reinterpret_cast<addr_t>(name);java.InvokeEnv(6,state);auto clazz=state.gpr.x0.qword;
  state={};state.gpr.x0.qword=java.EnvAddress();state.gpr.x1.qword=retained;state.gpr.x2.qword=clazz;java.InvokeEnv(32,state);
  java.DeleteLocalReference(retained);if(clazz)java.DeleteLocalReference(clazz);
  if(!state.gpr.x0.qword||!java.PendingException().empty())throw std::invalid_argument("audio observer Java receiver/context type mismatch");
}
}
struct AudioVolumeSession::State {
  std::thread::id owner=std::this_thread::get_id();
  std::shared_ptr<AudioVolumeObserver> observer;
  AudioVolumeObserver::Snapshot initial;
  jni::Host::ObjectValue context;
  int index=0;bool paused=false;
  void RequireOwner()const{if(owner!=std::this_thread::get_id())throw std::logic_error("audio volume callbacks belong to the constructor/UI caller");}
};
int AudioVolumeSession::MusicIndex(const AudioVolumeObserver::Snapshot &value){
  if(!value.available||value.stopped||value.status<0||value.callback_status<0||!value.volume_registered||!value.defaults_registered||!std::isfinite(value.scalar)||value.scalar<0||value.scalar>1)
    throw std::runtime_error("read-only audio endpoint/notification prerequisite is unavailable");
  return value.muted||value.scalar==0?0:1;
}
void AudioVolumeSession::DeclareFields(jni::Host &java){java.DefineField("com/unity3d/player/UnityPlayer",kField,kFieldType);}
AudioVolumeSession::AudioVolumeSession(jni::Host &java,Runner runner,addr_t context,addr_t player):java_(java),run_(std::move(runner)){
  if(!run_)throw std::invalid_argument("audio volume observer needs a translated callback runner");
  RequireType(java,context,"android/content/Context");RequireType(java,player,"com/unity3d/player/UnityPlayer");
  native_callback_=java.NativeEntry(kHandler,"onAudioVolumeChanged","(I)V");
  if(!native_callback_)throw std::runtime_error("actual AudioVolumeHandler native callback is not registered");
  auto state=std::make_shared<State>();state->context=java.CaptureValue(context);
  state->observer=std::make_shared<AudioVolumeObserver>();state->initial=state->observer->Current();state->index=MusicIndex(state->initial);
  auto receiver=java.NewHostInstance(kHandler,state);
  if(!receiver||!java.PendingException().empty())throw std::runtime_error("typed AudioVolumeHandler creation failed");
  receiver_=java.CaptureValue(receiver);player_=java.CaptureValue(player);java.SetObjectFieldValue(player,kField,kFieldType,receiver);java.DeleteLocalReference(receiver);
  if(!java.PendingException().empty())throw std::runtime_error("AudioVolumeHandler player field publication failed");
  state_=std::move(state);
  // DEX caches the first getStreamVolume(3) result without a native callback.
}
AudioVolumeSession::~AudioVolumeSession(){
  try{Pause();}catch(const std::exception &error){std::fprintf(stderr,"audio volume session cleanup failed: %s\n",error.what());std::abort();}
}
AudioVolumeObserver::Snapshot AudioVolumeSession::InitialSnapshot()const{return state_->initial;}
size_t AudioVolumeSession::Poll(){
  auto &state=*state_;state.RequireOwner();if(state.paused)return 0;
  auto current=state.observer->Current();(void)MusicIndex(current);
  size_t calls=0;
  for(const auto &value:state.observer->DrainChanges()){
    const auto index=MusicIndex(value);if(index==state.index)continue;state.index=index;
    auto receiver=java_.LocalValue(receiver_);
    try{run_(native_callback_,{java_.EnvAddress(),receiver,static_cast<addr_t>(index)});}
    catch(...){java_.DeleteLocalReference(receiver);throw;}
    java_.DeleteLocalReference(receiver);++calls;
    if(!java_.PendingException().empty())throw std::runtime_error("native audio volume callback raised: "+java_.PendingException());
  }
  return calls;
}
void AudioVolumeSession::Pause(){
  if(!state_)return;
  auto &state=*state_;state.RequireOwner();
  auto status=state.observer->Stop();
  if(!state.paused){
    auto player=java_.LocalValue(player_);java_.SetObjectFieldValue(player,kField,kFieldType,0);java_.DeleteLocalReference(player);state.paused=true;
  }
  if(status<0)throw std::runtime_error("audio volume notification unregister failed: "+std::to_string(status));
}
} // namespace bunker::windows

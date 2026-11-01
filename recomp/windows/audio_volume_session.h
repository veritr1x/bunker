#pragma once
#include "audio_volume.h"
#include "jni_host.h"
#include <functional>
#include <memory>
#include <vector>

namespace bunker::windows {
// Host port of the observed AudioVolumeHandler constructor/observer lifetime.
// Java bytecode/class initialization is not executed. The only index profile
// exposed here is mute=0/nonmuted=1, matching the proven native zero test.
class AudioVolumeSession {
 public:
  using Runner=std::function<uint64_t(addr_t,const std::vector<addr_t>&)>;
  AudioVolumeSession(jni::Host&,Runner,addr_t configured_context,addr_t unity_player);
  ~AudioVolumeSession();
  AudioVolumeSession(const AudioVolumeSession&)=delete;
  AudioVolumeSession &operator=(const AudioVolumeSession&)=delete;
  // Declare the exact APK player field once with the host class catalog.
  static void DeclareFields(jni::Host&);
  static int MusicIndex(const AudioVolumeObserver::Snapshot&);
  AudioVolumeObserver::Snapshot InitialSnapshot()const;
  // Owner/UI caller only. COM notifications never invoke translated code.
  size_t Poll();
  void Pause();
 private:
  struct State;
  jni::Host &java_;Runner run_;addr_t native_callback_=0;
  std::shared_ptr<State> state_;
  jni::Host::ObjectValue player_,receiver_;
};
} // namespace bunker::windows

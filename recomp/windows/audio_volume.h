#pragma once
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
// Read-only endpoint observation. Does not play audio, change volume/mute,
// invoke guest callbacks or pretend to implement Android audio playback.
class AudioVolumeObserver {
 public:
  struct Snapshot {
    bool available=false,muted=false,volume_registered=false,defaults_registered=false,stopped=false;
    float scalar=0; // Windows normalized audio-tapered endpoint level, not amplitude.
    int32_t status=0,cleanup_status=0,callback_status=0;
    uint64_t revision=0,generation=0,owner_thread=0,coalesced=0;
    std::u16string device_id;
  };
  // Dedicated MTA worker observes the default eRender/eMultimedia endpoint.
  // Initial snapshot is cached without an initial change event. Missing audio
  // devices are an unavailable HRESULT, never a fabricated volume value.
  AudioVolumeObserver();
  ~AudioVolumeObserver();
  AudioVolumeObserver(const AudioVolumeObserver&)=delete;
  AudioVolumeObserver &operator=(const AudioVolumeObserver&)=delete;
  Snapshot Current()const;
  std::vector<Snapshot> DrainChanges();
  // Unregisters endpoint/default notifications on their owner, then joins.
  // Returns the first failed native cleanup HRESULT; repeated calls are safe.
  int32_t Stop();
 private:struct Impl;std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows

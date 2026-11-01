#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmdeviceapi.h>
#include <endpointvolume.h>
#include "audio_volume.h"
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <thread>

using bunker::windows::AudioVolumeObserver;
namespace {
std::atomic<unsigned> checks{0};
void Check(bool value,const char *why){++checks;if(!value){std::fprintf(stderr,"audio volume check: %s\n",why);std::abort();}}
struct Direct {
  HRESULT status=E_FAIL;float scalar=0;BOOL muted=FALSE;std::u16string device;
};
Direct ReadActualEndpoint(){
  Direct result;IMMDeviceEnumerator *enumerator=nullptr;IMMDevice *device=nullptr;IAudioEndpointVolume *volume=nullptr;LPWSTR id=nullptr;
  result.status=CoCreateInstance(__uuidof(MMDeviceEnumerator),nullptr,CLSCTX_ALL,__uuidof(IMMDeviceEnumerator),reinterpret_cast<void**>(&enumerator));
  if(SUCCEEDED(result.status))result.status=enumerator->GetDefaultAudioEndpoint(eRender,eMultimedia,&device);
  if(SUCCEEDED(result.status))result.status=device->GetId(&id);
  if(SUCCEEDED(result.status)){static_assert(sizeof(wchar_t)==sizeof(char16_t));result.device.assign(reinterpret_cast<const char16_t*>(id));
    result.status=device->Activate(__uuidof(IAudioEndpointVolume),CLSCTX_ALL,nullptr,reinterpret_cast<void**>(&volume));}
  if(SUCCEEDED(result.status))result.status=volume->GetMasterVolumeLevelScalar(&result.scalar);
  if(SUCCEEDED(result.status))result.status=volume->GetMute(&result.muted);
  CoTaskMemFree(id);if(volume)volume->Release();if(device)device->Release();if(enumerator)enumerator->Release();return result;
}
bool Same(const AudioVolumeObserver::Snapshot &snapshot,const Direct &direct){
  return snapshot.available==SUCCEEDED(direct.status)&&(!snapshot.available||
    (snapshot.scalar==direct.scalar&&snapshot.muted==bool(direct.muted)&&snapshot.device_id==direct.device));
}
}
int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(15));std::fputs("audio volume watchdog\n",stderr);std::_Exit(95);}).detach();
  const auto com=CoInitializeEx(nullptr,COINIT_MULTITHREADED);Check(SUCCEEDED(com),"direct comparison COM apartment");
  AudioVolumeObserver observer;
  auto snapshot=observer.Current();
  Check(snapshot.revision&&snapshot.generation&&snapshot.owner_thread&&snapshot.owner_thread!=GetCurrentThreadId(),"real dedicated observer owner and initial revision");
  Check(snapshot.defaults_registered&&!snapshot.stopped&&!snapshot.callback_status,"default-device notification registered");
  Direct direct;
  // Tolerate genuine external endpoint/volume transitions during comparison.
  for(unsigned attempt=0;attempt<50;++attempt){direct=ReadActualEndpoint();snapshot=observer.Current();if(Same(snapshot,direct))break;std::this_thread::sleep_for(std::chrono::milliseconds(20));}
  Check(Same(snapshot,direct),"observer matches independently queried real default endpoint/mute/level");
  if(snapshot.available){
    Check(snapshot.volume_registered&&SUCCEEDED(snapshot.status)&&!snapshot.device_id.empty(),"real endpoint callback subscription and identity");
    Check(std::isfinite(snapshot.scalar)&&snapshot.scalar>=0&&snapshot.scalar<=1,"real normalized audio-tapered level");
  }else Check(FAILED(snapshot.status)&&!snapshot.volume_registered,"unavailable endpoint has explicit native failure, not a fake level");
  std::thread readers[4];for(auto &reader:readers)reader=std::thread([&]{for(unsigned i=0;i<64;++i){auto value=observer.Current();Check(value.owner_thread==snapshot.owner_thread&&value.revision>=snapshot.revision&&!value.stopped,"concurrent readers see coherent live observer snapshots");}});
  for(auto &reader:readers)reader.join();
  uint64_t revision=0;for(const auto &change:observer.DrainChanges()){
    Check(change.revision>revision&&change.generation&&change.owner_thread==snapshot.owner_thread,"queued real changes preserve monotonic identity");revision=change.revision;
  }
  Check(SUCCEEDED(observer.Stop())&&SUCCEEDED(observer.Stop()),"native callback unregister/join and repeated stop");
  auto stopped=observer.Current();Check(stopped.stopped&&!stopped.defaults_registered&&!stopped.volume_registered&&!stopped.cleanup_status,"no active native subscription after stop");
  {
    AudioVolumeObserver again;auto next=again.Current();
    Check(next.defaults_registered&&!next.stopped&&next.owner_thread!=GetCurrentThreadId(),"fresh observer creates real subscription after prior cleanup");
    Check(SUCCEEDED(again.Stop()),"fresh observer cleans up native subscriptions");
  }
  CoUninitialize();
  std::printf("Windows audio volume observer: %u checks; real endpoint available=%s level=%.6f muted=%s; no playback or volume mutation.\n",checks.load(),snapshot.available?"true":"false",double(snapshot.scalar),snapshot.muted?"true":"false");
}

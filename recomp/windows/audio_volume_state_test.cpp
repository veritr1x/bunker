// Synthetic notification mechanics only. The separate live gate independently
// queries/registers the actual endpoint without changing its volume or mute.
#include "audio_volume.cpp"
#include <cstdio>
#include <cstdlib>

using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};
void Require(bool value,const char *why){++checks;if(!value){std::fprintf(stderr,"audio callback unit: %s\n",why);std::abort();}}
}
int main(){
  auto state=std::make_shared<State>();
  const auto generation=state->Begin();
  Snapshot identity;identity.available=true;identity.volume_registered=true;identity.defaults_registered=true;
  identity.generation=generation;identity.revision=0;identity.scalar=.95f;identity.device_id=u"synthetic unit identity";
  state->Finish(generation,identity,true);
  Require(state->current.revision==1&&state->changes.empty(),"initial state has no synthetic change event");
  auto *volume=new Volume(state,generation);auto *defaults=new Defaults(state);
  void *queried=nullptr;
  Require(volume->QueryInterface(__uuidof(IAudioEndpointVolumeCallback),&queried)==S_OK&&queried==static_cast<IAudioEndpointVolumeCallback*>(volume),"volume COM interface identity");
  Require(static_cast<IAudioEndpointVolumeCallback*>(queried)->Release()==1,"volume interface AddRef balanced");
  queried=reinterpret_cast<void*>(1);
  Require(volume->QueryInterface(__uuidof(IMMNotificationClient),&queried)==E_NOINTERFACE&&!queried,"foreign interface rejected");
  Require(volume->QueryInterface(IID_IUnknown,nullptr)==E_POINTER&&volume->OnNotify(nullptr)==E_POINTER,"invalid callback pointers rejected");
  AUDIO_VOLUME_NOTIFICATION_DATA notification{};notification.fMasterVolume=.125f;notification.bMuted=TRUE;
  std::thread senders[4];for(auto &sender:senders)sender=std::thread([&]{for(unsigned i=0;i<128;++i)Require(volume->OnNotify(&notification)==S_OK,"concurrent notification wake accepted");});
  for(auto &sender:senders)sender.join();
  Require(state->refresh&&state->current.revision==1&&state->current.scalar==.95f&&!state->current.muted&&state->changes.empty(),"callbacks request owner query without publishing stale payload or invoking guest code");
  Require(defaults->OnDefaultDeviceChanged(eCapture,eMultimedia,nullptr)==S_OK&&!state->rebind,"capture default does not replace render endpoint");
  Require(defaults->OnDefaultDeviceChanged(eRender,eCommunications,nullptr)==S_OK&&!state->rebind,"other render role does not replace multimedia endpoint");
  Require(defaults->OnDefaultDeviceChanged(eRender,eMultimedia,nullptr)==S_OK&&state->rebind,"multimedia render default schedules owner rebind");
  state->rebind=false;const auto replacement=state->Begin();
  Require(replacement!=generation&&!state->refresh,"new endpoint invalidates earlier callback generation");
  Require(volume->OnNotify(&notification)==S_OK&&!state->refresh,"late old-endpoint callback cannot update new endpoint");
  auto *fresh=new Volume(state,replacement);
  Require(fresh->OnNotify(&notification)==S_OK&&state->refresh,"current generation still schedules actual owner query");
  identity.generation=replacement;
  {std::lock_guard lock(state->mutex);for(unsigned i=0;i<1025;++i)state->Update(identity,true);}
  Require(state->changes.size()==1024&&state->current.coalesced==1,"bounded change queue reports coalescing");
  state->Cleanup(E_ACCESSDENIED);identity.cleanup_status=0;state->Finish(replacement,identity,false);
  Require(state->current.cleanup_status==E_ACCESSDENIED,"native cleanup error survives later status publication");
  {std::lock_guard lock(state->mutex);state->stop=true;state->refresh=false;state->rebind=false;}
  Require(fresh->OnNotify(&notification)==S_OK&&!state->refresh&&defaults->OnDeviceAdded(nullptr)==S_OK&&!state->rebind,"notifications after stop cannot restart observation");
  auto weak=std::weak_ptr<State>(state);state.reset();
  Require(!weak.expired(),"in-flight callback objects retain only safe shared state");
  Require(volume->Release()==0&&fresh->Release()==0&&defaults->Release()==0&&weak.expired(),"last callback releases shared state without observer cycle");
  std::printf("Audio callback mechanics: %u synthetic checks; no Windows endpoint mutation or fabricated live event.\n",checks.load());
}

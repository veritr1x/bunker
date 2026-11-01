#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmdeviceapi.h>
#include <endpointvolume.h>
#include "audio_volume.h"
#include <atomic>
#include <cmath>
#include <condition_variable>
#include <deque>
#include <future>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace bunker::windows {
namespace audio_volume_detail {
using Snapshot=AudioVolumeObserver::Snapshot;
template<class T>struct Com {
  T *value=nullptr;
  Com()=default;Com(const Com&)=delete;Com &operator=(const Com&)=delete;
  ~Com(){Reset();}
  void Reset(){if(value){value->Release();value=nullptr;}}
  T *operator->()const{return value;}
};
void Check(HRESULT status,const char *operation){
  if(FAILED(status))throw std::runtime_error(std::string(operation)+" HRESULT="+std::to_string(static_cast<int32_t>(status)));
}
struct State {
  mutable std::mutex mutex;
  std::condition_variable wake;
  bool stop=false,rebind=false,refresh=false;
  uint64_t generation=0;
  int32_t cleanup_status=0;
  Snapshot current;
  std::deque<Snapshot> changes;
  std::atomic<int32_t> callback_status{0};
  void Update(Snapshot snapshot,bool notify){
    if(current.revision==UINT64_MAX)throw std::overflow_error("audio volume revision exhausted");
    snapshot.revision=current.revision+1;snapshot.coalesced=current.coalesced;snapshot.cleanup_status=cleanup_status;
    if(notify){
      if(changes.size()==1024){changes.pop_front();++snapshot.coalesced;}
      changes.push_back(snapshot);
    }
    current=std::move(snapshot);
  }
  uint64_t Begin(){std::lock_guard lock(mutex);
    if(generation==UINT64_MAX)throw std::overflow_error("audio endpoint generation exhausted");
    refresh=false;return ++generation;
  }
  void Finish(uint64_t expected,Snapshot snapshot,bool initial){
    std::lock_guard lock(mutex);if(stop||expected!=generation)return;
    Update(std::move(snapshot),!initial);
  }
  HRESULT Refresh(uint64_t expected)noexcept{
    try{{std::lock_guard lock(mutex);if(stop||expected!=generation)return S_OK;refresh=true;}wake.notify_one();return S_OK;}
    catch(...){return E_FAIL;}
  }
  HRESULT Rebind()noexcept{
    try{{std::lock_guard lock(mutex);if(stop)return S_OK;rebind=true;}wake.notify_one();return S_OK;}
    catch(...){return E_FAIL;}
  }
  void Cleanup(HRESULT status){if(FAILED(status)){std::lock_guard lock(mutex);if(!cleanup_status)cleanup_status=status;current.cleanup_status=cleanup_status;}}
};
template<class Interface>class Callback:public Interface {
 public:
  HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void **out)override{
    if(!out)return E_POINTER;
    *out=nullptr;
    if(IsEqualIID(id,IID_IUnknown)||IsEqualIID(id,__uuidof(Interface))){*out=static_cast<Interface*>(this);AddRef();return S_OK;}
    return E_NOINTERFACE;
  }
  ULONG STDMETHODCALLTYPE AddRef()override{return refs_.fetch_add(1,std::memory_order_relaxed)+1;}
  ULONG STDMETHODCALLTYPE Release()override{auto left=refs_.fetch_sub(1,std::memory_order_acq_rel)-1;if(!left)delete this;return left;}
 protected:virtual ~Callback()=default;
 private:std::atomic<ULONG> refs_{1};
};
class Defaults final:public Callback<IMMNotificationClient> {
  std::shared_ptr<State> state_;
 public:
  explicit Defaults(std::shared_ptr<State> state):state_(std::move(state)){}
  HRESULT STDMETHODCALLTYPE OnDefaultDeviceChanged(EDataFlow flow,ERole role,LPCWSTR)override{
    return flow==eRender&&role==eMultimedia?state_->Rebind():S_OK;
  }
  HRESULT STDMETHODCALLTYPE OnDeviceAdded(LPCWSTR)override{return state_->Rebind();}
  HRESULT STDMETHODCALLTYPE OnDeviceRemoved(LPCWSTR)override{return state_->Rebind();}
  HRESULT STDMETHODCALLTYPE OnDeviceStateChanged(LPCWSTR,DWORD)override{return state_->Rebind();}
  HRESULT STDMETHODCALLTYPE OnPropertyValueChanged(LPCWSTR,const PROPERTYKEY)override{return S_OK;}
};
class Volume final:public Callback<IAudioEndpointVolumeCallback> {
  std::shared_ptr<State> state_;const uint64_t generation_;
 public:
  Volume(std::shared_ptr<State> state,uint64_t generation):state_(std::move(state)),generation_(generation){}
  HRESULT STDMETHODCALLTYPE OnNotify(PAUDIO_VOLUME_NOTIFICATION_DATA data)override{
    if(!data)return E_POINTER;
    try{
      // Query the current endpoint on its owner instead of trusting potentially
      // delayed/out-of-order notification payloads. No COM or guest code runs
      // on this notification callback's thread.
      return state_->Refresh(generation_);
    }catch(const std::bad_alloc&){state_->callback_status=E_OUTOFMEMORY;return E_OUTOFMEMORY;}
    catch(...){state_->callback_status=E_FAIL;return E_FAIL;}
  }
};
void Work(const std::shared_ptr<State> &state,std::promise<void> startup){
  const auto initialized=CoInitializeEx(nullptr,COINIT_MULTITHREADED);
  bool startup_sent=false,default_registered=false;
  Com<IMMDeviceEnumerator> enumerator;Com<IAudioEndpointVolume> endpoint;
  Com<Defaults> defaults;Com<Volume> volume;
  auto unbind=[&]{
    if(endpoint.value&&volume.value)state->Cleanup(endpoint->UnregisterControlChangeNotify(volume.value));
    volume.Reset();endpoint.Reset();
  };
  try{
    Check(initialized,"audio CoInitializeEx");
    Check(CoCreateInstance(__uuidof(MMDeviceEnumerator),nullptr,CLSCTX_ALL,__uuidof(IMMDeviceEnumerator),reinterpret_cast<void**>(&enumerator.value)),"audio device enumerator");
    defaults.value=new Defaults(state);
    Check(enumerator->RegisterEndpointNotificationCallback(defaults.value),"audio default-device subscription");default_registered=true;
    auto query=[&](Snapshot &snapshot){
      HRESULT status=endpoint.value?endpoint->GetMasterVolumeLevelScalar(&snapshot.scalar):E_UNEXPECTED;
      BOOL muted=FALSE;if(SUCCEEDED(status))status=endpoint->GetMute(&muted);snapshot.muted=bool(muted);
      if(SUCCEEDED(status)&&(!std::isfinite(snapshot.scalar)||snapshot.scalar<0||snapshot.scalar>1))status=E_UNEXPECTED;
      snapshot.status=status;snapshot.available=SUCCEEDED(status);
    };
    auto bind=[&](bool initial){
      const auto generation=state->Begin();unbind();
      Snapshot snapshot;snapshot.generation=generation;snapshot.owner_thread=GetCurrentThreadId();snapshot.defaults_registered=true;
      Com<IMMDevice> device;
      HRESULT status=enumerator->GetDefaultAudioEndpoint(eRender,eMultimedia,&device.value);
      if(SUCCEEDED(status)){
        LPWSTR id=nullptr;status=device->GetId(&id);
        if(SUCCEEDED(status)){
          struct Id{LPWSTR value;~Id(){CoTaskMemFree(value);}} free{id};
          static_assert(sizeof(char16_t)==sizeof(wchar_t));snapshot.device_id.assign(reinterpret_cast<const char16_t*>(id));
          status=device->Activate(__uuidof(IAudioEndpointVolume),CLSCTX_ALL,nullptr,reinterpret_cast<void**>(&endpoint.value));
        }
      }
      if(SUCCEEDED(status)){
        snapshot.available=true;snapshot.volume_registered=true;
        volume.value=new Volume(state,generation);
        status=endpoint->RegisterControlChangeNotify(volume.value);
        if(FAILED(status)){snapshot.volume_registered=false;volume.Reset();endpoint.Reset();}
      }
      if(SUCCEEDED(status))query(snapshot);
      else{snapshot.status=status;snapshot.available=false;}
      state->Finish(generation,std::move(snapshot),initial);
    };
    bind(true);startup.set_value();startup_sent=true;
    for(;;){
      bool rebind;Snapshot snapshot;
      {std::unique_lock lock(state->mutex);state->wake.wait(lock,[&]{return state->stop||state->rebind||state->refresh;});
        if(state->stop)break;
        rebind=state->rebind;state->rebind=false;state->refresh=false;snapshot=state->current;}
      if(rebind)bind(false);
      else{query(snapshot);state->Finish(snapshot.generation,std::move(snapshot),false);}
    }
  }catch(...){
    if(!startup_sent){startup.set_exception(std::current_exception());startup_sent=true;}
    else{std::lock_guard lock(state->mutex);state->current.available=false;state->current.status=E_FAIL;}
  }
  unbind();
  if(default_registered)state->Cleanup(enumerator->UnregisterEndpointNotificationCallback(defaults.value));
  defaults.Reset();enumerator.Reset();
  if(SUCCEEDED(initialized))CoUninitialize();
  {std::lock_guard lock(state->mutex);state->stop=true;state->current.stopped=true;state->current.volume_registered=false;state->current.defaults_registered=false;}
}
}  // namespace audio_volume_detail
using namespace audio_volume_detail;
struct AudioVolumeObserver::Impl {
  std::shared_ptr<State> state=std::make_shared<State>();
  std::thread worker;
  std::mutex stop_mutex;
  Impl(){std::promise<void> ready;auto started=ready.get_future();worker=std::thread(Work,state,std::move(ready));
    try{started.get();}catch(...){if(worker.joinable())worker.join();throw;}}
  ~Impl(){Stop();}
  int32_t Stop(){std::lock_guard serial(stop_mutex);
    {std::lock_guard lock(state->mutex);state->stop=true;}state->wake.notify_one();if(worker.joinable())worker.join();
    std::lock_guard lock(state->mutex);return state->cleanup_status;
  }
};
AudioVolumeObserver::AudioVolumeObserver():impl_(std::make_unique<Impl>()){}
AudioVolumeObserver::~AudioVolumeObserver()=default;
AudioVolumeObserver::Snapshot AudioVolumeObserver::Current()const{
  std::lock_guard lock(impl_->state->mutex);auto snapshot=impl_->state->current;snapshot.callback_status=impl_->state->callback_status.load();return snapshot;
}
std::vector<AudioVolumeObserver::Snapshot> AudioVolumeObserver::DrainChanges(){
  std::lock_guard lock(impl_->state->mutex);std::vector<Snapshot> changes;
  changes.assign(impl_->state->changes.begin(),impl_->state->changes.end());impl_->state->changes.clear();return changes;
}
int32_t AudioVolumeObserver::Stop(){return impl_->Stop();}
}  // namespace bunker::windows

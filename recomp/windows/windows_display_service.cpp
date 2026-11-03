#include "windows_display_service.h"
#include <algorithm>
#include <cerrno>
#include <cfenv>
#include <cstring>
#include <cwchar>
#include <exception>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#include <shellscalingapi.h>
#endif
namespace bunker::windows {
namespace {
struct Environment {
 int error=errno;fenv_t fp{};
#ifdef _WIN32
 DWORD last=GetLastError();
#endif
 Environment(){std::fegetenv(&fp);}
 ~Environment(){std::fesetenv(&fp);errno=error;
#ifdef _WIN32
 SetLastError(last);
#endif
 }
};
using Info=WindowsDisplayService::DisplayInfo;
struct NativeInfo {Info value;bool primary=false;};
#ifdef _WIN32
struct MonitorRecord {HMONITOR handle;MONITORINFOEXW info;};
struct MonitorList {std::vector<MonitorRecord> monitors;std::exception_ptr failure;};
BOOL CALLBACK Monitor(HMONITOR monitor,HDC,LPRECT,LPARAM data) noexcept {
 auto &list=*reinterpret_cast<MonitorList*>(data);
 try{MONITORINFOEXW info{};info.cbSize=sizeof(info);if(!GetMonitorInfoW(monitor,&info))throw std::runtime_error("Windows display GetMonitorInfo failed");list.monitors.push_back({monitor,info});return TRUE;}
 catch(...){list.failure=std::current_exception();return FALSE;}
}
using ScaleReader=HRESULT(WINAPI*)(HMONITOR,DEVICE_SCALE_FACTOR*);
using DpiReader=HRESULT(WINAPI*)(HMONITOR,MONITOR_DPI_TYPE,UINT*,UINT*);
struct ScaleApi {HMODULE module=nullptr;ScaleReader scale=nullptr;DpiReader dpi=nullptr;};
template<class F>F Procedure(HMODULE module,const char*name){auto raw=GetProcAddress(module,name);F result=nullptr;static_assert(sizeof(result)==sizeof(raw));std::memcpy(&result,&raw,sizeof(result));return result;}
const ScaleApi& Scale(){
 // Function pointers stay valid for process lifetime; no monitor setting or
 // process/thread DPI-awareness policy is changed by this adapter.
 static const ScaleApi api=[](){ScaleApi a;a.module=LoadLibraryExW(L"shcore.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);if(!a.module)throw std::runtime_error("Windows display Shcore unavailable");a.scale=Procedure<ScaleReader>(a.module,"GetScaleFactorForMonitor");a.dpi=Procedure<DpiReader>(a.module,"GetDpiForMonitor");if(!a.scale||!a.dpi)throw std::runtime_error("Windows display scale/DPI API unavailable");return a;}();
 return api;
}
std::vector<NativeInfo> NativeDisplays(){
 Environment preserve;fenv_t conversion_environment{};if(std::feholdexcept(&conversion_environment)||std::fesetround(FE_TONEAREST))throw std::runtime_error("Windows display floating environment unavailable");MonitorList list;
 if(!EnumDisplayMonitors(nullptr,nullptr,Monitor,reinterpret_cast<LPARAM>(&list))){if(list.failure)std::rethrow_exception(list.failure);throw std::runtime_error("Windows display enumeration failed");}
 std::vector<DISPLAYCONFIG_PATH_INFO> paths;std::vector<DISPLAYCONFIG_MODE_INFO> modes;bool read=false;
 for(unsigned attempt=0;attempt<8;++attempt){UINT32 np=0,nm=0;LONG error=GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,&np,&nm);if(error!=ERROR_SUCCESS)throw std::runtime_error("Windows active display topology unavailable: "+std::to_string(error));paths.resize(np);modes.resize(nm);error=QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS,&np,paths.data(),&nm,modes.data(),nullptr);if(error==ERROR_INSUFFICIENT_BUFFER)continue;if(error!=ERROR_SUCCESS)throw std::runtime_error("Windows active display query failed: "+std::to_string(error));paths.resize(np);modes.resize(nm);read=true;break;}
 if(!read)throw std::runtime_error("Windows display topology changed during query");
 std::vector<NativeInfo> result;
 for(const auto &record:list.monitors){const auto &monitor=record.info;
  const DISPLAYCONFIG_PATH_INFO *match=nullptr;
  for(const auto &path:paths){DISPLAYCONFIG_SOURCE_DEVICE_NAME name{};name.header.type=DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME;name.header.size=sizeof(name);name.header.adapterId=path.sourceInfo.adapterId;name.header.id=path.sourceInfo.id;LONG error=DisplayConfigGetDeviceInfo(&name.header);if(error!=ERROR_SUCCESS)throw std::runtime_error("Windows display source name unavailable");if(std::wcscmp(name.viewGdiDeviceName,monitor.szDevice)==0){if(match)throw std::runtime_error("Windows display cloned source timing is unsupported");match=&path;}}
  if(!match)throw std::runtime_error("Windows monitor lacks active display topology");
  if(match->sourceInfo.modeInfoIdx>=modes.size())throw std::runtime_error("Windows display source mode missing");
  const auto &mode=modes[match->sourceInfo.modeInfoIdx];if(mode.infoType!=DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE)throw std::runtime_error("Windows display source mode type mismatch");
  const auto &source=mode.sourceMode;const auto &rate=match->targetInfo.refreshRate;
  if(!source.width||!source.height||source.width>INT32_MAX||source.height>INT32_MAX||!rate.Numerator||!rate.Denominator)throw std::runtime_error("Windows display dimensions/refresh unavailable");
  auto rotation=static_cast<uint32_t>(match->targetInfo.rotation);if(rotation<1||rotation>4)throw std::runtime_error("Windows display rotation unsupported");
  DEVICE_SCALE_FACTOR scale=SCALE_100_PERCENT;UINT dx=0,dy=0;const auto &api=Scale();if(FAILED(api.scale(record.handle,&scale))||scale<=0||scale>1000||FAILED(api.dpi(record.handle,MDT_EFFECTIVE_DPI,&dx,&dy))||!dx||!dy)throw std::runtime_error("Windows display scale/DPI query failed");
  NativeInfo item;auto &info=item.value;info.width=static_cast<int32_t>(source.width);info.height=static_cast<int32_t>(source.height);info.rotation=static_cast<int32_t>(rotation-1);info.windows_scale_percent=static_cast<uint32_t>(scale);info.windows_effective_dpi_x=dx;info.windows_effective_dpi_y=dy;info.density_dpi=static_cast<int32_t>((uint64_t(scale)*160+50)/100);info.refresh_numerator=rate.Numerator;info.refresh_denominator=rate.Denominator;
  float hz=static_cast<float>(double(rate.Numerator)/double(rate.Denominator));static_assert(sizeof(hz)==sizeof(info.refresh_bits));std::memcpy(&info.refresh_bits,&hz,sizeof(hz));
  info.nominal_presentation_budget_ns=static_cast<int64_t>((uint64_t(1000000000)*rate.Denominator+rate.Numerator-1)/rate.Numerator);info.device.assign(monitor.szDevice,monitor.szDevice+std::wcslen(monitor.szDevice));item.primary=(monitor.dwFlags&MONITORINFOF_PRIMARY)!=0;result.push_back(std::move(item));
 }
 std::sort(result.begin(),result.end(),[](const NativeInfo&a,const NativeInfo&b){return a.value.device<b.value.device;});return result;
}
std::u16string WindowDevice(void *native){
 Environment preserve;auto window=static_cast<HWND>(native);
 if(!window||!IsWindow(window))throw std::runtime_error("Activity window is closed or unavailable");
 DWORD process=0;if(!GetWindowThreadProcessId(window,&process)||process!=GetCurrentProcessId())throw std::runtime_error("Activity window is not owned by this process");
 auto monitor=MonitorFromWindow(window,MONITOR_DEFAULTTONULL);if(!monitor)throw std::runtime_error("Activity window has no associated monitor");
 MONITORINFOEXW info{};info.cbSize=sizeof(info);if(!GetMonitorInfoW(monitor,&info))throw std::runtime_error("Activity window monitor information unavailable");
 return std::u16string(info.szDevice,info.szDevice+std::wcslen(info.szDevice));
}
#else
std::vector<NativeInfo> NativeDisplays(){throw std::runtime_error("Windows display service requires native Windows");}
std::u16string WindowDevice(void*){throw std::runtime_error("Windows activity window requires native Windows");}
#endif
}
struct WindowsDisplayService::Impl {
 struct Display {std::weak_ptr<Impl> owner;int32_t id;std::mutex mutex;Info last;};
 struct Manager {std::weak_ptr<Impl> owner;};
 struct WindowManager {std::weak_ptr<Impl> owner;std::function<void*()> reader;};
 struct ActivityWindow {jni::Host::ObjectValue activity,manager;};
 jni::Host &host;Observer observer;std::mutex mutex;std::map<std::u16string,int32_t> ids;int64_t next_id=1;jni::Host::ObjectValue manager;std::map<int32_t,jni::Host::ObjectValue> objects;
 Impl(jni::Host&h,Observer o):host(h),observer(std::move(o)){}
 std::vector<ActivityWindow> activity_windows;
 addr_t Jni(size_t slot,addr_t a=0,addr_t b=0){State state{};state.gpr.x0.qword=host.EnvAddress();state.gpr.x1.qword=a;state.gpr.x2.qword=b;host.InvokeEnv(slot,state);return state.gpr.x0.qword;}
 bool IsActivity(addr_t object){auto clazz=Jni(6,reinterpret_cast<addr_t>("android/app/Activity"));auto result=clazz&&Jni(32,object,clazz);if(clazz)host.DeleteLocalReference(clazz);return object&&result&&host.PendingException().empty();}
 jni::Host::ObjectValue Associated(addr_t activity){std::vector<ActivityWindow> entries;{std::lock_guard lock(mutex);entries=activity_windows;}for(const auto&entry:entries){auto local=host.LocalValue(entry.activity);auto same=Jni(24,activity,local);host.DeleteLocalReference(local);if(same)return entry.manager;}return {};}
 addr_t ActivityManager(addr_t activity){Environment preserve;auto value=Associated(activity);auto local=host.LocalValue(value);if(!local)host.ThrowException("java/lang/IllegalStateException",u"Activity has no Windows window association");return local;}
 int32_t WindowDisplay(const std::function<void*()>&reader){Environment preserve;auto window=reader();auto device=WindowDevice(window);auto inventory=Inventory();if(!window||reader()!=window)throw std::runtime_error("Activity window closed during display query");for(const auto&info:inventory)if(info.device==device)return info.id;throw std::runtime_error("Activity window monitor is absent from display inventory");}
 std::vector<Info> Inventory(){auto native=NativeDisplays();std::vector<Info> result;unsigned primaries=0;{std::lock_guard lock(mutex);for(auto &x:native){if(x.primary){x.value.id=0;++primaries;}else{auto it=ids.find(x.value.device);if(it==ids.end()){if(next_id>INT32_MAX)throw std::runtime_error("Windows display ID space exhausted");it=ids.emplace(x.value.device,static_cast<int32_t>(next_id++)).first;}x.value.id=it->second;}result.push_back(std::move(x.value));}}if(!result.empty()&&primaries!=1)throw std::runtime_error("Windows desktop has no unique primary display");return result;}
 std::optional<Info> Find(int32_t id){if(id<0)return std::nullopt;for(auto &x:Inventory())if(x.id==id)return x;return std::nullopt;}
 void Observe(const Info&info){if(observer){Environment preserve;observer(info);}}
 Info Read(addr_t object){auto display=host.ReadHostState<Display>(object);if(!display)throw std::runtime_error("Display has no Windows-backed state");auto owner=display->owner.lock();if(owner.get()!=this)throw std::runtime_error("Display owner expired or mismatched");auto current=Find(display->id);std::lock_guard lock(display->mutex);if(current)display->last=*current;return display->last;}
 addr_t Get(const std::shared_ptr<Impl>&self,int32_t id){auto info=Find(id);if(!info)return 0;Observe(*info);jni::Host::ObjectValue value;{std::lock_guard lock(mutex);auto it=objects.find(id);if(it!=objects.end())value=it->second;}auto existing=host.LocalValue(value);if(existing)return existing;auto payload=std::make_shared<Display>();payload->owner=self;payload->id=id;payload->last=*info;auto local=host.NewHostInstance("android/view/Display",payload);auto captured=host.CaptureValue(local);{std::lock_guard lock(mutex);auto [it,inserted]=objects.emplace(id,captured);(void)inserted;value=it->second;}return host.LocalValue(value);}
};
WindowsDisplayService::WindowsDisplayService(jni::Host&host,Observer observer){
 auto self=std::make_shared<Impl>(host,std::move(observer));impl_=self;std::weak_ptr<Impl> weak=self;
 auto owner=[weak](){auto state=weak.lock();if(!state)throw std::runtime_error("Windows display adapter owner expired");return state;};
 host.DefineClass("android/hardware/display/DisplayManager",{},"java/lang/Object",true);host.DefineClass("android/view/Display",{},"java/lang/Object",true);host.DefineClass("android/util/DisplayMetrics",{},"java/lang/Object",true);
 // Only the reached framework metadata/method surface is represented. The
 // configured launch Activity keeps its original class and ContextState.
 host.DefineClass("android/app/NativeActivity",{},"android/app/Activity",true);
 host.DefineInterface("android/view/WindowManager",{{"getDefaultDisplay","()Landroid/view/Display;"}});
 host.DefineClass("android/view/WindowManagerImpl",{},"java/lang/Object",true,{"android/view/WindowManager"});
 host.DefineObjectMethod("android/app/Activity","getWindowManager","()Landroid/view/WindowManager;",[weak,&host](addr_t activity,const jni::Host::MethodArguments&){Environment preserve;auto state=weak.lock();if(!state){host.ThrowException("java/lang/IllegalStateException",u"Windows display adapter owner expired");return addr_t(0);}return state->ActivityManager(activity);});
 host.DefineObjectMethod("android/view/WindowManagerImpl","getDefaultDisplay","()Landroid/view/Display;",[weak,&host](addr_t object,const jni::Host::MethodArguments&){
  Environment preserve;auto state=weak.lock();if(!state){host.ThrowException("java/lang/IllegalStateException",u"Windows display adapter owner expired");return addr_t(0);}
  auto manager=host.ReadHostState<Impl::WindowManager>(object);if(!manager)return addr_t(0); // Preserve the pending typed-state error.
  if(manager->owner.lock()!=state){host.ThrowException("java/lang/IllegalStateException",u"WindowManager owner expired or mismatched");return addr_t(0);}
  try{auto result=state->Get(state,state->WindowDisplay(manager->reader));if(!result)host.ThrowException("java/lang/IllegalStateException",u"Activity window display became unavailable");return result;}
  catch(const std::runtime_error&error){const std::string message=error.what();host.ThrowException("java/lang/IllegalStateException",std::u16string(message.begin(),message.end()));return addr_t(0);}
 });
 for(const char *field:{"widthPixels","heightPixels","densityDpi"})host.DefineField("android/util/DisplayMetrics",field,"I");
 auto manager=host.NewHostInstance("android/hardware/display/DisplayManager",std::make_shared<Impl::Manager>(Impl::Manager{weak}));self->manager=host.CaptureValue(manager);host.DeleteLocalReference(manager);
 host.DefineObjectMethod("android/content/Context","getSystemService","(Ljava/lang/String;)Ljava/lang/Object;",[owner](addr_t,const jni::Host::MethodArguments&args){auto state=owner();if(!args[0])return addr_t(0);auto name=state->host.StringValue(args[0]);if(!name)return addr_t(0);if(*name!=u"display"){state->host.ThrowException("java/lang/UnsupportedOperationException",u"Windows display adapter supports only Context.getSystemService(display)");return addr_t(0);}return state->host.LocalValue(state->manager);});
 host.DefineObjectMethod("android/hardware/display/DisplayManager","getDisplay","(I)Landroid/view/Display;",[owner](addr_t object,const jni::Host::MethodArguments&args){auto state=owner();auto manager_state=state->host.ReadHostState<Impl::Manager>(object);if(!manager_state||manager_state->owner.lock()!=state)throw std::runtime_error("DisplayManager has no Windows-backed owner");int32_t id;uint32_t bits=static_cast<uint32_t>(args[0]);std::memcpy(&id,&bits,sizeof(id));return state->Get(state,id);});
 for(const std::string name:{"getDisplayId","getRotation","getWidth","getHeight"})host.DefineIntMethod("android/view/Display",name,"()I",[owner,name](addr_t object,const jni::Host::MethodArguments&){auto info=owner()->Read(object);return name=="getDisplayId"?info.id:name=="getRotation"?info.rotation:name=="getWidth"?info.width:info.height;});
 host.DefineFloatBitsMethod("android/view/Display","getRefreshRate","()F",[owner](addr_t object,const jni::Host::MethodArguments&){return owner()->Read(object).refresh_bits;});
 host.DefineBooleanMethod("android/view/Display","isWideColorGamut","()Z",[owner](addr_t object,const jni::Host::MethodArguments&){owner()->Read(object);return false;});
 host.DefineLongMethod("android/view/Display","getAppVsyncOffsetNanos","()J",[owner](addr_t object,const jni::Host::MethodArguments&){return owner()->Read(object).app_vsync_offset_ns;});
 host.DefineLongMethod("android/view/Display","getPresentationDeadlineNanos","()J",[owner](addr_t object,const jni::Host::MethodArguments&){return owner()->Read(object).nominal_presentation_budget_ns;});
 host.DefineConstructor("android/util/DisplayMetrics","()V",[owner](const jni::Host::MethodArguments&){auto state=owner();auto result=state->host.NewInstance("android/util/DisplayMetrics");state->host.SetIntFieldValue(result,"widthPixels",0);state->host.SetIntFieldValue(result,"heightPixels",0);state->host.SetIntFieldValue(result,"densityDpi",0);return result;});
 host.DefineVoidMethod("android/view/Display","getRealMetrics","(Landroid/util/DisplayMetrics;)V",[owner](addr_t object,const jni::Host::MethodArguments&args){auto state=owner();if(!args[0]){state->host.ThrowException("java/lang/NullPointerException",u"null DisplayMetrics");return;}auto info=state->Read(object);state->host.SetIntFieldValue(args[0],"widthPixels",info.width);state->host.SetIntFieldValue(args[0],"heightPixels",info.height);state->host.SetIntFieldValue(args[0],"densityDpi",info.density_dpi);});
}
WindowsDisplayService::~WindowsDisplayService()=default;
std::vector<WindowsDisplayService::DisplayInfo> WindowsDisplayService::Displays(){return impl_->Inventory();}
void WindowsDisplayService::BindActivityWindow(addr_t activity,std::function<void*()> reader){
 Environment preserve;auto state=impl_;
 if(!state->host.PendingException().empty())throw std::invalid_argument("Activity window binding requires no pending Java exception");
 if(!reader||!state->IsActivity(activity))throw std::invalid_argument("Activity window binding requires an actual Activity and weak native window reader");
 (void)state->WindowDisplay(reader);
 auto existing=state->host.LocalValue(state->Associated(activity));if(existing){state->host.DeleteLocalReference(existing);throw std::invalid_argument("Activity window already associated");}
 auto value=state->host.CaptureValue(activity);
 auto local=state->host.NewHostInstance("android/view/WindowManagerImpl",std::make_shared<Impl::WindowManager>(Impl::WindowManager{state,std::move(reader)}));
 auto manager=state->host.CaptureValue(local);state->host.DeleteLocalReference(local);
 {std::lock_guard lock(state->mutex);state->activity_windows.push_back({std::move(value),std::move(manager)});}
}
}

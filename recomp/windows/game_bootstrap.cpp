// Natural native-frame diagnostic with lazy real Unity and IL2CPP modules.
#include "jni_host.h"
#include "android_context.h"
#include "android_internal_storage.h"
#include "android_obb_storage.h"
#include "android_asset_pack_wrapper.h"
#include "android_shared_preferences.h"
#include "windows_shared_preferences.h"
#include "windows_android_id.h"
#include "jni_interface_proxy.h"
#include "java_native_libraries.h"
#include "apk_assets.h"
#include "native_window.h"
#include "unity_lifecycle.h"
#include "signal_host.h"
#include "semaphore_host.h"
#include "nonlocal_jmp.h"
#include "audio_volume_session.h"
#include "egl_host.h"
#include "gl_host.h"
#include "filesystem.h"
#include "module_registry.h"
#include "pthread_host.h"
#include "libc.h"
#include "logging.h"
#include "zlib_host.h"
#include "../fastaes/elfload.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"
#include "game_traces.h"
#include "game_metadata.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <atomic>
#include <charconv>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <windows.h>
#include <bcrypt.h>
extern "C" Memory *__real_sub_825b0544(State &,addr_t,Memory *);

namespace {
using namespace unity_image;
const auto &kInitializers=unity_image::kConstructors;
std::map<std::string,addr_t> resolved;
size_t constructor_index;
const char *stage="setup";
std::atomic<bool> jni_diagnostic_reached{false};
std::atomic<bool> init_java_diagnostic_active{false};
std::atomic<size_t> init_java_errors{0};
void Require(bool condition,const char *message){if(!condition)throw std::runtime_error(message);}
template<class T>T Read(addr_t address){T result{};recomp::ReadGuestMemory(&result,address,sizeof(result));return result;}
void InstallDiagnosticJni(bunker::jni::Host &host,recomp::Runtime &runtime){
  auto invoke=[&host](bool vm,size_t slot,State &state){
    if(!jni_diagnostic_reached.exchange(true))std::fprintf(stderr,"Unity bootstrap: opt-in JNI dispatch diagnostic reached\n");
    auto prior=host.PendingException();
    try{if(vm)host.InvokeVm(slot,state);else host.InvokeEnv(slot,state);}
    catch(const std::exception &error){std::fprintf(stderr,"Unity bootstrap: JNI diagnostic %s slot%zu failed: %s\n",vm?"VM":"Env",slot,error.what());std::abort();}
    auto pending=host.PendingException();
    if(!pending.empty()&&pending!=prior){
      if(init_java_diagnostic_active.load())++init_java_errors;
      std::fprintf(stderr,"Unity bootstrap: original pending Java exception after %s slot%zu return=%#llx: %s\n",vm?"VM":"Env",slot,static_cast<unsigned long long>(state.gpr.x30.qword),pending.c_str());
    }
  };
  for(size_t slot=4;slot<bunker::jni::kEnvSlots;++slot)runtime.AddImport(host.EnvMarker(slot),[invoke,slot](State &state){invoke(false,slot,state);});
  for(size_t slot=3;slot<bunker::jni::kVmSlots;++slot)runtime.AddImport(host.VmMarker(slot),[invoke,slot](State &state){invoke(true,slot,state);});
}
std::string Sha256(const std::filesystem::path &path){
  // BCrypt's object storage must outlive the hash handle, including failures.
  std::vector<uint8_t> object;
  struct Cng {
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
    ~Cng(){if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);}
  } cng;
  auto check=[](NTSTATUS status){if(status<0)throw std::runtime_error("Windows SHA256 operation failed");};
  check(BCryptOpenAlgorithmProvider(&cng.algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0));
  DWORD object_size=0,got=0;check(BCryptGetProperty(cng.algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&object_size),sizeof(object_size),&got,0));
  object.resize(object_size);check(BCryptCreateHash(cng.algorithm,&cng.hash,object.data(),object.size(),nullptr,0,0));
  std::ifstream input(path,std::ios::binary);if(!input)throw std::runtime_error("cannot open original input for SHA256");
  char buffer[65536];while(input.read(buffer,sizeof(buffer))||input.gcount())check(BCryptHashData(cng.hash,reinterpret_cast<PUCHAR>(buffer),static_cast<ULONG>(input.gcount()),0));
  if(!input.eof())throw std::runtime_error("input read failed during SHA256");
  uint8_t bytes[32];check(BCryptFinishHash(cng.hash,bytes,sizeof(bytes),0));
  std::string result;const char *hex="0123456789abcdef";for(auto b:bytes){result+=hex[b>>4];result+=hex[b&15];}return result;
}
static void *Resolve(const char *name){
  auto it=resolved.find(name);
  if(it==resolved.end()){std::fprintf(stderr,"Unity bootstrap: ELF import absent from verified manifest: %s\n",name);std::abort();}
  return reinterpret_cast<void*>(it->second);
}
template<class Provider> addr_t Try(Provider &provider,const std::string &name){
  try{return provider.Marker(name);}catch(const std::invalid_argument&){return 0;}
}
addr_t TryProcess(bunker::windows::SignalHost &provider,const std::string &name){
  try{return provider.ProcessMarker(name);}catch(const std::invalid_argument&){return 0;}
}
addr_t TryGlImport(bunker::windows::GlHost &provider,const std::string &name){
  for(const auto &supported:bunker::windows::GlHost::Commands())if(name==supported)return provider.Marker(name);
  return 0;
}
bool Translated(addr_t entry){
  // Generated trace table is ordered. Data exports are intentionally excluded.
  size_t low=0,high=std::size(kTraces);
  while(low<high){size_t mid=low+(high-low)/2;if(kTraces[mid].address<entry)low=mid+1;else high=mid;}
  return low<std::size(kTraces)&&kTraces[low].address==entry;
}
bool Executable(addr_t address){
  if(address&3)return false;
  for(const auto &range:kGameExecutableRanges)if(address>=range.low&&address<=range.high&&range.high-address>=4)return true;
  return false;
}
#include "game_bootstrap_detail.h"
LONG WINAPI Crash(EXCEPTION_POINTERS *exception){
  std::fprintf(stderr,"Unity bootstrap: native exception %#lx at %p; stage=%s, completed constructors=%zu/%zu\n",
      exception->ExceptionRecord->ExceptionCode,exception->ExceptionRecord->ExceptionAddress,stage,constructor_index,std::size(kInitializers));
  std::fflush(stderr);return EXCEPTION_EXECUTE_HANDLER;
}
struct LocalFrame {
  bunker::jni::Host &host;
  explicit LocalFrame(bunker::jni::Host &value):host(value){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=64;host.InvokeEnv(19,s);if(s.gpr.x0.dword)throw std::runtime_error("initJni local frame allocation failed");}
  ~LocalFrame(){State s{};s.gpr.x0.qword=host.EnvAddress();host.InvokeEnv(20,s);}
};
void DefineGameAndroidApiProfile(bunker::jni::Host &host){
  // Chosen framework compatibility contract, independent of APK targetSdk and
  // Windows identity. This catalog still rejects unported API bodies explicitly.
  constexpr int32_t api_level=33;
  LocalFrame locals(host);
  host.DefineClass("android/os/Build$VERSION",{},"java/lang/Object",true);
  host.DefineField("android/os/Build$VERSION","SDK_INT","I",true);
  auto env=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);Require(host.PendingException().empty(),"Android compatibility SDK field setup failed");return s.gpr.x0.qword;};
  const auto clazz=env(6,reinterpret_cast<addr_t>("android/os/Build$VERSION"));
  const auto field=env(144,clazz,reinterpret_cast<addr_t>("SDK_INT"),reinterpret_cast<addr_t>("I"));
  env(159,clazz,field,api_level);
  Require(env(150,clazz,field)==api_level,"Android compatibility SDK field differs from selected profile");
  std::fprintf(stderr,"Game bootstrap: explicit Android13 compatibility profile SDK_INT=%d; APK targetSdk and host identity are separate\n",api_level);
}
}
extern "C" Memory *__wrap_sub_825b0544(State &s,addr_t pc,Memory *memory){return GameOriginalSaveHelper(s,pc,memory);}
int main(int argc,char **argv){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  SetUnhandledExceptionFilter(Crash);_set_abort_behavior(0,3);
  const bool frame_gate=argc==8&&!std::strcmp(argv[4],"--frame-gate");
  const bool surface_gate=frame_gate||(argc==7&&!std::strcmp(argv[4],"--surface-gate"));
  if(argc!=4&&!(argc==5&&!std::strcmp(argv[4],"--init-jni"))&&!surface_gate){std::fprintf(stderr,"Usage: bunker-game-bootstrap.exe <verified-native-directory> <original-game.apk> <writable-storage-directory> [--init-jni | --surface-gate <landscape-client-width> <height> | --frame-gate <width> <height> <pinned-ANGLE-DLL-directory>]\n");return 2;}
  const bool init_jni=argc!=4;
  bool frame_continues=true;
  try{
    using namespace bunker::windows;
    namespace fs=std::filesystem;
    int32_t width=0,height=0;
    if(surface_gate){
      auto dimension=[](const char *text){int32_t value=0;auto end=text+std::strlen(text);auto result=std::from_chars(text,end,value);if(result.ec!=std::errc{}||result.ptr!=end||value<=0||value>32767)throw std::invalid_argument("surface dimensions must be integer client pixels in1..32767");return value;};
      width=dimension(argv[5]);height=dimension(argv[6]);if(width<=height)throw std::invalid_argument("APK sensorLandscape surface gate requires width greater than height");
    }
    if(std::size(kInitializers)!=kExpectedConstructors)throw std::runtime_error("trace/metadata constructor count mismatch");
    auto native_directory=fs::canonical(fs::u8path(argv[1]));
    auto library=native_directory/"libunity.so",il2cpp_library=native_directory/"libil2cpp.so";
    auto apk=fs::canonical(fs::u8path(argv[2]));
    if(Sha256(library)!=kUnitySha256||Sha256(il2cpp_library)!=il2cpp_image::kIl2cppSha256||Sha256(apk)!=kApkSha256)throw std::runtime_error("runtime original Unity/IL2CPP/APK SHA256 differs from verified translation/metadata");
    if(kExploratory)std::fprintf(stderr,"Unity bootstrap: EXPLORATORY DIAGNOSTIC ONLY: %zu unsupported translated traces remain; every real constructor will still execute\n",kUnsupportedTraces);
    else if(kUnsupportedTraces)throw std::runtime_error("strict bootstrap refuses unsupported translated traces");
    auto storage=fs::absolute(fs::u8path(argv[3]));fs::create_directories(storage);
    GameAutomaticEnvironments automatic_environments;game_environments=&automatic_environments;
    automatic_environments.original=__real_sub_825b0544;
    std::vector<recomp::Trace> selected(std::begin(kTraces),std::end(kTraces));bool original_helper_present=false;for(auto &trace:selected)if(trace.address==0x825b0544){original_helper_present=true;trace.entry=GameOriginalSaveHelper;}
    Require(original_helper_present,"current IL2CPP automatic save helper is absent from union");
    recomp::Runtime runtime;runtime.AddTraces(selected.data(),selected.size());
    FileSystem files;
    files.EnableGrowdownMappings();
    std::fprintf(stderr,"Game bootstrap: explicit owned Windows MAP_GROWSDOWN profile enabled\n");
    files.MountFile("/data/app/bunker/base.apk",apk);
    files.MountDirectory("/data/app/bunker/lib/arm64",library.parent_path());
    files.MountDirectory("/data/user/0/bunker",storage,true);
    files.SetWorkingDirectory("/data/user/0/bunker");
    auto error=[&](int value){files.SetError(value);};
    Pthreads *runner=nullptr;
    Logging logging;logging.SetErrorSink(error);
    logging.SetStream([&](addr_t stream,std::string_view text){return files.FWrite(text.data(),1,text.size(),stream);});
    bunker::jni::Host java(Translated);
    DefineUnityJavaCatalog(java);
    DefineGameAndroidApiProfile(java);
    std::unique_ptr<JavaNativeLibraries> native_catalog;
    {LocalFrame locals(java);auto call=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=java.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;java.InvokeEnv(slot,s);Require(java.PendingException().empty(),"native catalog setup raised a Java exception");return s.gpr.x0.qword;};
      auto app=call(6,reinterpret_cast<addr_t>("com/unity3d/player/UnityPlayer")),clazz=call(6,reinterpret_cast<addr_t>("java/lang/Class"));
      auto method=call(33,clazz,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));auto loader=call(34,app,method);
      native_catalog=std::make_unique<JavaNativeLibraries>(java,JavaNativeLibraries::Config{loader,app,{{u"unity",u"/data/app/bunker/lib/arm64/libunity.so"},{u"il2cpp",u"/data/app/bunker/lib/arm64/libil2cpp.so"}}});
    }
    if(frame_gate)AudioVolumeSession::DeclareFields(java);
    AndroidContextConfig context_config;
    context_config.package_name=kPackageName;context_config.target_sdk=kTargetSdk;context_config.activity_class=kLaunchActivity;
    ApplyUnityPackageMetadata(context_config);
    context_config.prepare_internal_directory=MakeInternalDirectoryPreparer(files,context_config.data_dir);
    // This closed mount profile exposes APK/native/internal data only. Its
    // external-volume catalog is independent of APK expansion-file inventory.
    context_config.external_obb_volumes=std::vector<ExternalObbVolume>{};
    context_config.read_android_id=MakeWindowsAndroidIdReader(context_config.package_name);
    context_config.apk_assets=std::make_shared<ApkAssets>(apk);
    stage="Android Context setup";AndroidContext context(java,context_config);
    stage="SharedPreferences setup";
    auto preferences_backend=MakeWindowsSharedPreferencesBackend(context_config.package_name);
    auto read_preferences=std::move(preferences_backend.read);
    preferences_backend.read=[read=std::move(read_preferences),package=context_config.package_name](const std::u16string &name){
      auto snapshot=read(name);
      std::fprintf(stderr,"Game bootstrap: original preferences read store=%s observed=%s entries=%zu\n",name==package?"legacy":"v2",snapshot?"present":"absent",snapshot?snapshot->size():0);
      return snapshot;
    };
    auto write_preferences=std::move(preferences_backend.write);
    preferences_backend.write=[write=std::move(write_preferences),package=context_config.package_name](const std::u16string &name,const SharedPreferencesSnapshot &snapshot){
      auto status=write(name,snapshot);auto version=snapshot.find(u"__UNITY_PLAYERPREFS_VERSION__");
      std::fprintf(stderr,"Game bootstrap: original preferences write store=%s entries=%zu version_kind=%u version_bits=%#llx status=%u\n",name==package?"legacy":"v2",snapshot.size(),version==snapshot.end()?0:unsigned(version->second.kind),(unsigned long long)(version==snapshot.end()?0:version->second.bits),status);
      return status;
    };
    std::unique_ptr<AndroidSharedPreferences> preferences;
    {LocalFrame locals(java);preferences=std::make_unique<AndroidSharedPreferences>(java,context.Activity(),context_config.package_name,std::move(preferences_backend));}
    stage="interface proxy setup";JniInterfaceProxy interface_proxies(java);
    // The input APK was SHA256-verified above. No extra split/JAR/DEX sources or
    // dynamic Java code loader are exposed by this diagnostic's closed catalog.
    stage="asset-pack wrapper setup";AndroidAssetPackWrapper asset_packs(java,{kApkSha256,"b2be67185a866f3489146d9864ca40d1de5c2668037f026609890afe12940689",true});
    stage="native providers setup";
    // Real policy/semaphores for explicitly bound threads. These cohorts are
    // unpolled: delivery and unknown worker contexts fail rather than queueing
    // a request that cannot receive a real same-worker acknowledgment.
    SignalHost process_signals([](uint64_t token){std::fprintf(stderr,"Game bootstrap: unsupported unpolled delivery target=%#llx\n",(unsigned long long)token);std::abort();},0x7ff600100000ULL,
      [&files](addr_t address,size_t size)->std::optional<SignalHost::StackRegion>{
        auto mapping=files.MappingRegion(address,size,true);
        if(!mapping)return {};
        return SignalHost::StackRegion{mapping->base,mapping->base+mapping->size,mapping->generation};
      },
      [&files](addr_t address,size_t size,uint64_t generation)->std::optional<SignalHost::StackLease>{
        auto use=files.AcquireMappingUse(address,size,true);
        if(!use||use->region.generation!=generation)return {};
        return SignalHost::StackLease{{use->region.base,use->region.base+use->region.size,use->region.generation},std::move(use->lease)};
      });process_signals.SetErrorSink(error);
    Semaphores semaphores(process_signals);semaphores.SetErrorSink(error);
    std::unique_ptr<NonlocalJumps> jumps;
    recomp::Runtime window_bridges;
    recomp::Runtime egl_bridges,gl_bridges;
    std::mutex window_call_mutex;std::map<std::string,uint64_t> window_calls;
    std::unique_ptr<NativeWindows> native_windows;
    std::unique_ptr<EglHost> egl;
    std::unique_ptr<GlHost> graphics;
    // ModuleRegistry owns 0x7ff400000000; keep this combined provider disjoint.
    if(surface_gate)native_windows=std::make_unique<NativeWindows>(java,0x7ff440000000ULL);
    if(frame_gate){
      auto dlls=fs::canonical(fs::u8path(argv[7]));
      egl=std::make_unique<EglHost>(*native_windows,dlls.wstring());graphics=std::make_unique<GlHost>(*egl,dlls.wstring());
      egl->SetProcedureResolver([&](const std::string &name){
        std::fprintf(stderr,"Unity bootstrap: requested typed GL procedure %s\n",name.c_str());return graphics->Marker(name);
      });
    }
    GameModuleLedger unity_ledger{"Unity",{std::begin(unity_image::kConstructors),std::end(unity_image::kConstructors)},{std::begin(unity_image::kUnityFinalizers),std::end(unity_image::kUnityFinalizers)}};
    GameModuleLedger il2cpp_ledger{"IL2CPP",{std::begin(il2cpp_image::kConstructors),std::end(il2cpp_image::kConstructors)},{std::begin(il2cpp_image::kFinalizers),std::end(il2cpp_image::kFinalizers)}};
    ModuleRegistry modules([&](addr_t entry){try{Require(runner,"module lifecycle runner is unavailable");auto *owner=unity_ledger.Owns(entry)?&unity_ledger:il2cpp_ledger.Owns(entry)?&il2cpp_ledger:nullptr;Require(owner,"module lifecycle entry has no verified owner");owner->Run(entry,*runner);constructor_index=unity_ledger.constructed;}catch(const std::exception &e){std::fprintf(stderr,"Game bootstrap: module lifecycle failed:%s entry=%#llx\n",e.what(),(unsigned long long)entry);std::abort();}});
    LibC libc([&](addr_t entry,const std::vector<addr_t> &args){return runner->Run(entry,args);});
    logging.SetAllocator([&](uint64_t size){return libc.Malloc(size);});
    libc.SetErrorSink(error);libc.SetEnvironment({});
    // Import callbacks can reference this audit until every worker has joined.
    GameTlsAudit tls_audit;tls_audit.free_callback=libc.Marker("free");
    // Destroy/join guest workers before the providers they may still call.
    Pthreads threads(runtime,Translated,0x7ff900000000ULL,
      [&libc](addr_t entry){return Translated(entry)||entry==libc.Marker("free");});threads.SetErrorSink(error);runner=&threads;
    const auto parent_token=threads.Self();Require(!process_signals.RegisterThread(parent_token)&&!process_signals.BindCurrent(parent_token),"cannot bind actual UI virtual signal context");
    auto current_signal_thread=[&]{auto token=threads.Self();Require(bool(process_signals.Lookup(token)),"guest-created worker lacks proved SignalHost lifecycle hooks");return token;};
    auto current_jump_thread=[&](){
      auto token=threads.Self();AndroidThreadAttr attr{};
      if(!process_signals.Lookup(token))throw std::runtime_error("setjmp thread has no registered virtual signal-mask lifetime");
      if(threads.GetAttr(token,&attr)||!attr.stack_base||!attr.stack_size||attr.stack_size>UINT64_MAX-attr.stack_base)throw std::runtime_error("setjmp thread has no owned guest stack");
      return NonlocalJumps::Thread{token,token,attr.stack_base,attr.stack_base+attr.stack_size};
    };
    automatic_environments.current=current_jump_thread;
    if(surface_gate)jumps=std::make_unique<NonlocalJumps>(current_jump_thread,[&files,current_jump_thread](addr_t environment,size_t size)->std::optional<NonlocalJumps::Region>{
      if(auto mapping=files.MappingRegion(environment,size,true)){
        std::fprintf(stderr,"Unity bootstrap: jmp_buf=%#llx owned mmap=[%#llx,%#llx) generation=%llu\n",static_cast<unsigned long long>(environment),static_cast<unsigned long long>(mapping->base),static_cast<unsigned long long>(mapping->base+mapping->size),static_cast<unsigned long long>(mapping->generation));
        return NonlocalJumps::Region{mapping->base,mapping->base+mapping->size,mapping->generation};
      }
      auto current=current_jump_thread();
      if(auto owned=game_environments->Find(environment,size,current.token))return owned;
      std::fprintf(stderr,"Unity bootstrap: unknown jmp_buf allocation=%#llx bytes=%zu; owned guest stack=[%#llx,%#llx); no mmap/stack lifetime; heap/subobject provenance is not invented\n",static_cast<unsigned long long>(environment),size,static_cast<unsigned long long>(current.stack_low),static_cast<unsigned long long>(current.stack_high));
      return {};
    },[&](){uint64_t mask=0;auto token=threads.Self();if(process_signals.Mask(token,0,nullptr,&mask))throw std::runtime_error("setjmp signal mask is not registered for this virtual thread");return mask;},Executable);
    Zlib zlib([&](addr_t entry,const std::vector<addr_t> &args){return threads.Run(entry,args);});
    struct Drain {Pthreads &threads;~Drain(){if(threads.Shutdown())std::abort();}} drain{threads};
    files.Install(runtime);threads.Install();libc.Install(runtime);logging.Install(runtime);
    constexpr addr_t mmap_audit_marker=0x7ffc68000000ULL;
    auto mmap_bridge=recomp::MakeBridge<addr_t(addr_t,uint64_t,int32_t,int32_t,int32_t,int64_t)>([&files](auto address,auto length,auto protection,auto flags,auto descriptor,auto offset){return files.Mmap(address,length,protection,flags,descriptor,offset);});
    runtime.AddImport(mmap_audit_marker,[&,mmap_bridge](State &s){
      const auto length=s.gpr.x1.qword,caller=s.gpr.x30.qword;const auto flags=s.gpr.x3.dword;
      try{mmap_bridge(s);std::fprintf(stderr,"Game bootstrap: original mmap length=%llu flags=%#x LR=%#llx result=%#llx errno=%d\n",(unsigned long long)length,flags,(unsigned long long)caller,(unsigned long long)s.gpr.x0.qword,files.Error());}
      catch(const std::exception &e){std::fprintf(stderr,"Game bootstrap: original mmap length=%llu flags=%#x LR=%#llx failed:%s\n",(unsigned long long)length,flags,(unsigned long long)caller,e.what());std::abort();}
    });
    constexpr addr_t sscanf_audit_marker=0x7ffc68000008ULL;
    auto sscanf_bridge=recomp::MakeBridge<int32_t(const char*,const char*,uint64_t*)>([&libc](auto input,auto format,auto output){return libc.ScanUnsignedLongLong(input,format,output);});
    runtime.AddImport(sscanf_audit_marker,[&,sscanf_bridge](State &s){
      const auto caller=s.gpr.x30.qword,output=s.gpr.x2.qword;
      try{
        const auto format=recomp::ReadGuestString(s.gpr.x1.qword);
        sscanf_bridge(s);const auto count=static_cast<int32_t>(s.gpr.x0.dword);
        const auto value=count==1?Read<uint64_t>(output):0;
        std::fprintf(stderr,"Game bootstrap: original sscanf format=%s LR=%#llx result=%d assigned=%d value=%llu errno=%d\n",format.c_str(),(unsigned long long)caller,count,int(count==1),(unsigned long long)value,files.Error());
      }catch(const std::exception &e){std::fprintf(stderr,"Game bootstrap: original sscanf LR=%#llx failed:%s\n",(unsigned long long)caller,e.what());std::abort();}
      catch(...){std::fprintf(stderr,"Game bootstrap: original sscanf LR=%#llx failed:unknown host exception\n",(unsigned long long)caller);std::abort();}
    });
    tls_audit.Install(runtime,threads);
    recomp::Runtime module_bridges;modules.Install(module_bridges);
    for(const char *name:{"dlopen","dlsym","dlclose","dlerror"}){auto marker=modules.Marker(name);runtime.AddImport(marker,[&,name,marker](State &s){try{
      const auto argument=s.gpr.x0.qword,caller=s.gpr.x30.qword;
      const auto text=!std::strcmp(name,"dlopen")?(argument?recomp::ReadGuestString(argument):"<null>"):!std::strcmp(name,"dlsym")?(s.gpr.x1.qword?recomp::ReadGuestString(s.gpr.x1.qword):"<null>"):std::string();
      module_bridges.Dispatch(s,marker,nullptr);std::fprintf(stderr,"Game bootstrap: original %s argument=%#llx name=%s result=%#llx LR=%#llx Unity refs=%zu IL2CPP refs=%zu\n",name,(unsigned long long)argument,text.c_str(),(unsigned long long)s.gpr.x0.qword,(unsigned long long)caller,modules.ReferenceCount("libunity.so"),modules.ReferenceCount("libil2cpp.so"));
    }catch(const std::exception &e){std::fprintf(stderr,"Game bootstrap: module bridge %s failed:%s\n",name,e.what());std::abort();}});}
    if(init_jni)InstallDiagnosticJni(java,runtime);else java.Install(runtime);
    zlib.Install(runtime);
    recomp::Runtime signal_bridges,jump_bridges;
    auto no_delivery=[](const SignalHost::Delivery&)->std::optional<uint64_t>{throw std::runtime_error("unpolled frame profile cannot deliver a target signal");};
    process_signals.Install(signal_bridges,current_signal_thread,no_delivery);
    for(const char *name:{"sigaction","pthread_sigmask","sigprocmask","pthread_kill","sigsuspend","sigpending","sigemptyset","sigfillset","sigaddset","sigdelset","sigismember","sigaltstack"}){auto marker=process_signals.Marker(name);runtime.AddImport(marker,[&,name,marker](State &s){try{if(!std::strcmp(name,"pthread_kill")&&s.gpr.x1.dword){std::fprintf(stderr,"Game bootstrap: unsupported nonzero signal delivery signal=%u target=%#llx guestPC=%#llx LR=%#llx\n",s.gpr.x1.dword,(unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.pc.qword,(unsigned long long)s.gpr.x30.qword);std::abort();}
      const auto input=s.gpr.x0.qword,output=s.gpr.x1.qword;
      signal_bridges.Dispatch(s,marker,nullptr);
      if(!std::strcmp(name,"sigaltstack")){
        const auto stack=process_signals.AlternateStack(current_signal_thread()).configured;
        std::fprintf(stderr,"Game bootstrap: original sigaltstack new=%#llx old=%#llx SP=%#llx LR=%#llx result=%d configured=%#llx flags=%u size=%llu\n",(unsigned long long)input,(unsigned long long)output,(unsigned long long)s.gpr.sp.qword,(unsigned long long)s.gpr.x30.qword,int32_t(s.gpr.x0.dword),(unsigned long long)stack.pointer,uint32_t(stack.flags),(unsigned long long)stack.size);
      }
    }catch(const std::exception &e){std::fprintf(stderr,"Game bootstrap: signal bridge %s failed:%s\n",name,e.what());std::abort();}});}
    semaphores.Install(runtime,current_signal_thread,no_delivery);
    if(jumps){automatic_environments.jumps=jumps.get();jumps->Install(jump_bridges);for(const char *name:{"setjmp","_setjmp","sigsetjmp","longjmp","_longjmp","siglongjmp"}){auto marker=jumps->Marker(name);runtime.AddImport(marker,[&,name,marker](State &s){try{if(!std::strcmp(name,"setjmp"))automatic_environments.BeforeSetjmp(s,current_signal_thread());jump_bridges.Dispatch(s,marker,nullptr);}catch(const std::exception &e){std::fprintf(stderr,"Game bootstrap: nonlocal bridge %s failed:%s\n",name,e.what());std::abort();}});}}
    if(graphics){
      graphics->Install(gl_bridges);
      for(const auto &name:GlHost::Commands()){
        auto marker=graphics->Marker(name);runtime.AddImport(marker,[&,marker,name](State &s){
          std::fprintf(stderr,"Unity bootstrap: guest %s x0=%#llx x1=%#llx return=%#llx\n",name.c_str(),static_cast<unsigned long long>(s.gpr.x0.qword),static_cast<unsigned long long>(s.gpr.x1.qword),static_cast<unsigned long long>(s.gpr.x30.qword));gl_bridges.Dispatch(s,marker,nullptr);
        });
      }
    }
    if(egl)egl->Install(egl_bridges);
    if(native_windows){
      // Forward the original checked provider bridges without adding a nested
      // Runtime::Run/ExecutionContext. Observe actual guest imports, not our
      // separate host calls used to verify the HWND's initial geometry.
      native_windows->Install(window_bridges);
      for(const char *name:{"ANativeWindow_fromSurface","ANativeWindow_acquire","ANativeWindow_release","ANativeWindow_getWidth","ANativeWindow_getHeight","ANativeWindow_setBuffersGeometry"}){
        const auto marker=native_windows->Marker(name);
        runtime.AddImport(marker,[&,marker,name](State &s){
          {std::lock_guard<std::mutex> lock(window_call_mutex);++window_calls[name];}
          std::fprintf(stderr,"Unity bootstrap: guest %s x0=%#llx x1=%#llx return=%#llx\n",name,static_cast<unsigned long long>(s.gpr.x0.qword),static_cast<unsigned long long>(s.gpr.x1.qword),static_cast<unsigned long long>(s.gpr.x30.qword));
          window_bridges.Dispatch(s,marker,nullptr);
          std::fprintf(stderr,"Unity bootstrap: guest %s completed x0=%#llx\n",name,static_cast<unsigned long long>(s.gpr.x0.qword));
        });
      }
    }
    size_t missing=0;std::set<addr_t> forwarded_egl;
    auto load=[&](const char *module_name,const auto &imports,const fs::path &path,addr_t base,size_t span,elf_image &target){
      resolved.clear();size_t provided=0,weak=0;
      for(const auto &import:imports){
        std::string name=import.name;addr_t address=tls_audit.Marker(name);if(!address&&name=="mmap")address=mmap_audit_marker;if(!address&&name=="sscanf")address=sscanf_audit_marker;if(!address)address=Try(process_signals,name);if(!address)address=Try(semaphores,name);
        if(!address)for(addr_t candidate:{Try(files,name),Try(threads,name),Try(libc,name),Try(logging,name),Try(modules,name),Try(zlib,name),native_windows?Try(*native_windows,name):0,jumps?Try(*jumps,name):0,egl?Try(*egl,name):0,graphics?TryGlImport(*graphics,name):0}){
          if(candidate){if(address&&address!=candidate)throw std::runtime_error("ambiguous import provider: "+name);address=candidate;}
        }
        if(address){++provided;if(egl&&Try(*egl,name)==address&&forwarded_egl.insert(address).second)runtime.AddImport(address,[&,address,name](State &s){std::fprintf(stderr,"Game bootstrap: guest %s x0=%#llx x1=%#llx x2=%#llx LR=%#llx\n",name.c_str(),(unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.x1.qword,(unsigned long long)s.gpr.x2.qword,(unsigned long long)s.gpr.x30.qword);egl_bridges.Dispatch(s,address,nullptr);});}
        else if(import.weak){++weak;}
        else{Require(!import.object,"missing strong data import; fabricated storage is forbidden");address=0x7ffc00000000ULL+missing++*8;runtime.AddImport(address,[name,module_name](State &s){std::fprintf(stderr,"Game bootstrap: unsupported import module=%s name=%s PC=%#llx LR=%#llx x0=%#llx x1=%#llx stage=%s\n",module_name,name.c_str(),(unsigned long long)s.gpr.pc.qword,(unsigned long long)s.gpr.x30.qword,(unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.x1.qword,stage);std::fflush(stderr);std::abort();});}
        Require(resolved.emplace(name,address).second,"duplicate import inventory entry");
      }
      Require(!elf_load(path.u8string().c_str(),base,Resolve,&target)&&target.span==span,"verified module data-image/span load failed");
      std::fprintf(stderr,"Game bootstrap: mapped %s imports=%zu real/%zu weak-zero; cumulative failure markers=%zu; constructors remain lazy\n",module_name,provided,weak,missing);
    };
    elf_image image{},il2cpp_image_data{};
    load("libunity.so",unity_image::kGameImports,library,kUnityBase,kUnityImageSpan,image);
    load("libil2cpp.so",il2cpp_image::kGameImports,il2cpp_library,il2cpp_image::kIl2cppBase,il2cpp_image::kIl2cppSpan,il2cpp_image_data);
    Module unity;unity.name="libunity.so";unity.aliases={"/data/app/bunker/lib/arm64/libunity.so"};
    for(auto &symbol:kUnityExports){auto actual=reinterpret_cast<addr_t>(elf_symbol(&image,symbol.name));if(actual!=symbol.address)throw std::runtime_error(std::string("loaded export differs from translation: ")+symbol.name);unity.exports.emplace(symbol.name,actual);}
    unity.initializers.assign(std::begin(kInitializers),std::end(kInitializers));
    unity.finalizers.assign(std::begin(kUnityFinalizers),std::end(kUnityFinalizers));
    modules.Add(std::move(unity));
    Module il2cpp;il2cpp.name="libil2cpp.so";il2cpp.aliases={"/data/app/bunker/lib/arm64/libil2cpp.so"};
    for(auto &symbol:il2cpp_image::kExports){auto actual=reinterpret_cast<addr_t>(elf_symbol(&il2cpp_image_data,symbol.name));Require(actual==symbol.address,"IL2CPP export differs from verified ELF");il2cpp.exports.emplace(symbol.name,actual);}
    il2cpp.initializers=il2cpp_ledger.constructors;il2cpp.finalizers=il2cpp_ledger.finalizers;modules.Add(std::move(il2cpp));
    Require(modules.ReferenceCount("libil2cpp.so")==0&&!il2cpp_ledger.constructed,"IL2CPP constructor state was made eager");
    stage="constructors";auto module=modules.Open("libunity.so",2);
    if(!module||constructor_index!=kExpectedConstructors)throw std::runtime_error("not all real Unity constructors completed");
    std::fprintf(stderr,"Unity bootstrap: ALL %zu real constructors completed in order\n",constructor_index);
    stage="JNI_OnLoad";auto onload=modules.Symbol(module,"JNI_OnLoad");if(!onload||!Translated(onload))throw std::runtime_error("real JNI_OnLoad export is not translated");
    auto version=threads.Run(onload,{java.VmAddress(),0});
    std::fprintf(stderr,"Unity bootstrap: real JNI_OnLoad returned %#llx, pending Java exception: %s\n",static_cast<unsigned long long>(version),java.PendingException().c_str());
    if(version!=bunker::jni::kVersion16||!java.PendingException().empty())return 5;
    for(auto &binding:kUnityRegistrations)if(java.NativeEntry(binding.class_name,binding.name,binding.signature)!=binding.entry)throw std::runtime_error(std::string("actual JNI_OnLoad native registration mismatch: ")+binding.class_name+"."+binding.name);
    std::fprintf(stderr,"Unity bootstrap: all %zu evidenced native bindings match original ELF/DEX\n",std::size(kUnityRegistrations));
    for(auto name:kUnityJavaClasses){auto count=java.NativeCount(name);if(count)std::fprintf(stderr,"Unity bootstrap: registered %zu natives on %s\n",count,name);}
    // Reaching this line proves constructors and JNI registration only. Surface,
    // graphics/audio initialization and the game lifecycle are separate gates.
    std::fprintf(stderr,"Unity bootstrap: %sconstructor/JNI-only gate passed; %zu unsupported traces remain; the game is not running\n",kExploratory?"EXPLORATORY ":"",kUnsupportedTraces);
    if(init_jni){
      stage="initJni(Context)";LocalFrame frame(java);
      auto entry=java.NativeEntry("com/unity3d/player/UnityPlayer","initJni","(Landroid/content/Context;)V");
      if(!entry||!Translated(entry))throw std::runtime_error("verified instance-native initJni(Context) entry is unavailable");
      auto player=java.NewInstance("com/unity3d/player/UnityPlayer"),activity=context.Activity();
      if(!player||!activity||!java.PendingException().empty())throw std::runtime_error("typed initJni receiver/context creation failed");
      context.BindUnityPlayer(player);
      std::fprintf(stderr,"Unity bootstrap: %sisolated instance-native initJni(Context)V gate entry=%#llx; host-typed UnityPlayer/Activity objects; Java <clinit>/constructors are not executed or marked initialized\n",kExploratory?"EXPLORATORY ":"",static_cast<unsigned long long>(entry));
      init_java_errors=0;init_java_diagnostic_active=true;
      threads.Run(entry,{java.EnvAddress(),player,activity});
      init_java_diagnostic_active=false;
      auto exception=java.PendingException();
      std::fprintf(stderr,"Unity bootstrap: initJni native entry returned; pending Java exception: %s\n",exception.c_str());
      if(!exception.empty())throw std::runtime_error("initJni stopped with pending Java exception: "+exception);
      if(init_java_errors.load())throw std::runtime_error("initJni encountered "+std::to_string(init_java_errors.load())+" Java exception(s); inspect the original JNI diagnostics even when native code cleared them");
      std::fprintf(stderr,"Unity bootstrap: isolated initJni native-entry gate passed; Activity/UnityPlayer Java lifecycle, surface/render/resume and game startup remain unexecuted\n");
      if(surface_gate){
        auto recreate=java.NativeEntry("com/unity3d/player/UnityPlayer","nativeRecreateGfxState","(ILandroid/view/Surface;)V");
        auto changed=java.NativeEntry("com/unity3d/player/UnityPlayer","nativeSendSurfaceChangedEvent","()V");
        if(!Translated(recreate)||!Translated(changed))throw std::runtime_error("verified surface natives are not translated");
        auto window=native_windows->Create(width,height,frame_gate?u"Bunker":u"Bunker native surface diagnostic",frame_gate);
        auto surface=native_windows->NewSurface(window);
        auto token=native_windows->FromSurface(surface);
        auto actual_width=native_windows->Width(token),actual_height=native_windows->Height(token);native_windows->Release(token);
        if(actual_width!=width||actual_height!=height)throw std::runtime_error("actual HWND client geometry differs from configured landscape pixels");
        std::fprintf(stderr,"Unity bootstrap: %ssurface-only host lifecycle port; actual HWND client=%dx%d; APK sensorLandscape; resumed=false; no Java class-init or render/resume claim\n",kExploratory?"EXPLORATORY ":"",actual_width,actual_height);
        uint64_t worker_token=0;bool worker_registered=false;
        const auto actual_render=frame_gate?java.NativeEntry("com/unity3d/player/UnityPlayer","nativeRender","()Z"):0;
        UnitySurfaceLifecycle lifecycle(java,[&](addr_t target,const std::vector<addr_t>&args){
          if(actual_render&&target==actual_render)std::fprintf(stderr,"Game bootstrap: before original nativeRender IL2CPP constructors=%zu refs=%zu\n",il2cpp_ledger.constructed,modules.ReferenceCount("libil2cpp.so"));
          std::fprintf(stderr,"Unity bootstrap: UnityMain host-thread=%lu native=%#llx argc=%zu env=%#llx receiver=%#llx display=%#llx surface=%#llx\n",GetCurrentThreadId(),static_cast<unsigned long long>(target),args.size(),static_cast<unsigned long long>(args.at(0)),static_cast<unsigned long long>(args.at(1)),static_cast<unsigned long long>(args.size()>2?args[2]:0),static_cast<unsigned long long>(args.size()>3?args[3]:0));
          auto result=threads.Run(target,args);std::fprintf(stderr,"Unity bootstrap: UnityMain native=%#llx returned\n",static_cast<unsigned long long>(target));return result;
        },{recreate,changed},player,[&]{
          const auto token=worker_token;
          if(!token)return;
          int released=0;std::exception_ptr release_error;
          try{if(egl)egl->ReleaseCurrentThread();}catch(...){release_error=std::current_exception();}
          try{if(tls_audit.PendingModuleCallbacks(threads))Require(!unity_ledger.finalized&&!il2cpp_ledger.finalized,"real UnityMain TLS survives an already finalized module; safe callback lifetime is unproved");released=threads.ReleaseCurrent();}catch(...){if(!release_error)release_error=std::current_exception();}
          jumps->DropThread(token,token);
          const auto dropped=worker_registered?process_signals.DropThread(token):0;
          if(release_error)std::rethrow_exception(release_error);
          if(released||dropped)throw std::runtime_error("UnityMain runner/signal lifetime cleanup failed");
        });
        if(frame_gate){
          auto native=[&](const char *name,const char *signature){auto address=java.NativeEntry("com/unity3d/player/UnityPlayer",name,signature);if(!Translated(address))throw std::runtime_error(std::string("required frame native is not translated: ")+name);return address;};
          lifecycle.ConfigureOneFrame({native("nativeResume","()V"),native("nativeFocusChanged","(Z)V"),native("nativeRender","()Z"),native("nativePause","()Z"),native("nativeDone","()Z")});
        }
        lifecycle.AfterInitJni();
        // A real model mask is captured at Start, then inherited by the child.
        // Full policy imports are installed, with delivery explicitly rejected
        // because these translated cohorts do not poll for suspension.
        Require(threads.Self()==parent_token&&bool(process_signals.Lookup(parent_token)),"actual UI virtual signal lifetime changed before UnityMain start");
        uint64_t parent_mask=0;if(process_signals.Mask(parent_token,0,nullptr,&parent_mask))throw std::runtime_error("cannot snapshot parent virtual signal mask");
        lifecycle.Start([&,parent_token,parent_mask]{
          worker_token=threads.Self();
          if(process_signals.RegisterThread(worker_token,parent_token))throw std::runtime_error("cannot register UnityMain virtual signal-mask lifetime");
          worker_registered=true;
          if(process_signals.BindCurrent(worker_token)||process_signals.Mask(worker_token,2,&parent_mask,nullptr))throw std::runtime_error("cannot inherit UnityMain signal mask");
          std::fprintf(stderr,"Unity bootstrap: UnityMain virtual-thread=%llu generation=%llu inherited mask=%#llx; alternate stack disabled\n",static_cast<unsigned long long>(worker_token),static_cast<unsigned long long>(worker_token),static_cast<unsigned long long>(parent_mask));
        });init_java_errors=0;init_java_diagnostic_active=true;
        stage="surfaceCreated/recreate";lifecycle.SurfaceCreated(surface);lifecycle.WaitIdle();
        stage="surfaceChanged/recreate+notify";lifecycle.SurfaceChanged(surface);lifecycle.WaitIdle();
        if(frame_gate){
          stage="one-frame resume/focus/render/pause/done";
          auto indicator=java.NativeEntry("com/unity3d/player/UnityPlayer","nativeRestartActivityIndicator","()V");
          if(!Translated(indicator))throw std::runtime_error("actual UI resume activity-indicator entry is not translated");
          std::fprintf(stderr,"Unity bootstrap: UI resume prerequisite nativeRestartActivityIndicator entry=%#llx\n",static_cast<unsigned long long>(indicator));
          threads.Run(indicator,{java.EnvAddress(),player});
          if(!java.PendingException().empty()||init_java_errors.load())throw std::runtime_error("UI resume prerequisite raised an original Java exception");
          AudioVolumeSession volume(java,[&](addr_t address,const std::vector<addr_t>&args){return threads.Run(address,args);},activity,player);
          auto audio=volume.InitialSnapshot();
          std::fprintf(stderr,"Unity bootstrap: real read-only music-volume observer ready scalar=%g muted=%d profile-index=%d; no initial native callback; no playback/system mutation\n",double(audio.scalar),audio.muted,AudioVolumeSession::MusicIndex(audio));
          volume.Poll();lifecycle.ActivityResumed();
          auto lease=native_windows->FromSurface(surface);auto hwnd=static_cast<HWND>(native_windows->NativeHandle(lease));native_windows->Release(lease);
          if(GetForegroundWindow()!=hwnd)std::fprintf(stderr,"Unity bootstrap: real foreground activation requested, accepted=%d\n",int(SetForegroundWindow(hwnd)!=0));
          bool focused=false;auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
          while(!focused&&std::chrono::steady_clock::now()<deadline){
            for(const auto &event:native_windows->DrainEvents(window)){
              if(event.kind==NativeWindows::Event::Focus){lifecycle.WindowFocusChanged(event.focused);focused=event.focused;}
              if(event.kind==NativeWindows::Event::CloseRequested)throw std::runtime_error("window close requested before first native frame");
              if(event.kind==NativeWindows::Event::Resized&&(event.width!=actual_width||event.height!=actual_height))throw std::runtime_error("one-frame client resized before startup; rerun with explicit dimensions");
            }
            if(!focused)std::this_thread::sleep_for(std::chrono::milliseconds(10));
          }
          if(!focused)throw std::runtime_error("no real HWND focus event; native frame prerequisite remains unmet");
          bool keep_running=false;while(true){try{keep_running=lifecycle.WaitForFrame();break;}catch(const std::runtime_error &e){if(std::string(e.what())!="one-frame diagnostic timed out before nativeRender completed")throw;std::fprintf(stderr,"Game bootstrap: first nativeRender observation window expired; retaining same live worker/window and waiting, not restarting\n");volume.Poll();}}
          frame_continues=keep_running;lifecycle.WaitIdle();volume.Poll();
          std::fprintf(stderr,"Unity bootstrap: first nativeRender returned continue=%d; requesting finishing PAUSE at diagnostic frame boundary\n",int(keep_running));
          volume.Pause();lifecycle.PauseNative(true);
        }
        stage="surfaceDestroyed/recreate(null)";lifecycle.SurfaceDestroyed();lifecycle.Stop();
        if(egl)egl->SetProcedureResolver({});
        init_java_diagnostic_active=false;
        if(init_java_errors.load())throw std::runtime_error("surface native calls encountered original Java exceptions");
        auto state=lifecycle.Describe();if(state.resumed||state.surface||state.started)throw std::runtime_error("surface lifecycle did not finish paused and detached");
        {std::lock_guard<std::mutex> lock(window_call_mutex);
          const auto from=window_calls["ANativeWindow_fromSurface"],acquire=window_calls["ANativeWindow_acquire"],release=window_calls["ANativeWindow_release"];
          std::fprintf(stderr,"Unity bootstrap: observed guest native-window calls fromSurface=%llu acquire=%llu release=%llu\n",static_cast<unsigned long long>(from),static_cast<unsigned long long>(acquire),static_cast<unsigned long long>(release));
          if(from<2||release!=from+acquire)throw std::runtime_error("real native-window handoff calls missing or guest reference calls unbalanced");
        }
        native_windows->Close(window);java.DeleteLocalReference(surface);
        if(!frame_gate)std::fprintf(stderr,"Unity bootstrap: isolated surface handoff/detach gate passed on UnityMain; HWND closed after native detach acknowledgment; no nativeRender/nativeResume executed\n");
        else std::fprintf(stderr,"Unity bootstrap: bounded native frame diagnostic completed: rendered=%llu continue=%d nativeDone=%d process-kill-requested=%d; Java class-init/constructor completion, a rendered image and a playable game are not claimed\n",static_cast<unsigned long long>(state.rendered),int(frame_continues),int(state.native_done),int(state.process_kill_requested));
      }
    }
    Require(!threads.Shutdown(),"actual guest workers did not drain before JNI/module teardown");
    preferences->CheckPersistence();
    if(auto pending=tls_audit.PendingModuleCallbacks(threads)){
      // A real callback must run before JNI/module globals are retired. If
      // natural guest code already retired an owner, do not invoke stale code.
      Require(!unity_ledger.finalized&&!il2cpp_ledger.finalized,"real UI TLS survives an already finalized module; safe callback lifetime is unproved");
      Require(!threads.ReleaseCurrent(),"actual UI TLS retirement failed");preferences->CheckPersistence();if(jumps)jumps->DropThread(parent_token,parent_token);Require(!process_signals.DropThread(parent_token),"actual UI signal retirement failed");native_catalog->Revoke();
      std::fprintf(stderr,"Game bootstrap: reached teardown boundary: %zu real UI TLS destructor(s) retired before JNI/global teardown; modules retained until process exit, Unity refs=%zu IL2CPP refs=%zu; no forced finalizers/reuse claim\n",pending,modules.ReferenceCount("libunity.so"),modules.ReferenceCount("libil2cpp.so"));return 7;
    }
    stage="JNI_OnUnload";auto onunload=modules.Symbol(module,"JNI_OnUnload");if(onunload)threads.Run(onunload,{java.VmAddress(),0});
    preferences->CheckPersistence();
    Require(!tls_audit.PendingModuleCallbacks(threads),"JNI_OnUnload created UI TLS requiring an unproved teardown order");
    stage="interface proxy ownership before module finalizers";
    try{interface_proxies.CheckNoEnabledProxies();}catch(const std::exception &error){
      std::fprintf(stderr,"Game bootstrap: retained-module proxy ownership boundary: %s; Unity refs=%zu IL2CPP refs=%zu; no native delete/finalizer forced\n",error.what(),modules.ReferenceCount("libunity.so"),modules.ReferenceCount("libil2cpp.so"));return 8;
    }
    stage="finalizers";if(modules.Close(module))throw std::runtime_error("Unity module finalization failed");
    preferences->CheckPersistence();
    interface_proxies.CheckNoEnabledProxies();
    std::fprintf(stderr,"Game bootstrap: actual lazy IL2CPP lifecycle constructors=%zu finalizers=%zu remaining refs=%zu; no host-forced guest handle close\n",il2cpp_ledger.constructed,il2cpp_ledger.finalized,modules.ReferenceCount("libil2cpp.so"));
    Require(!tls_audit.PendingModuleCallbacks(threads),"actual module finalizers created surviving UI TLS; callback lifetime is unproved");
    if(modules.ReferenceCount("libunity.so")||modules.ReferenceCount("libil2cpp.so")){
      Require(!tls_audit.PendingModuleCallbacks(threads),"module finalization created UI TLS requiring an unproved teardown order");
      Require(!threads.ReleaseCurrent(),"actual UI retirement with retained modules failed");preferences->CheckPersistence();if(jumps)jumps->DropThread(parent_token,parent_token);Require(!process_signals.DropThread(parent_token),"actual UI signal retirement with retained modules failed");native_catalog->Revoke();
      std::fprintf(stderr,"Game bootstrap: reached teardown boundary: actual module references remain Unity=%zu IL2CPP=%zu; globals retained until process exit, no host-forced finalizers\n",modules.ReferenceCount("libunity.so"),modules.ReferenceCount("libil2cpp.so"));return 7;
    }
    libc.Finalize();interface_proxies.CheckNoEnabledProxies();Require(!tls_audit.PendingModuleCallbacks(threads),"actual global finalizers created surviving UI TLS; callback lifetime is unproved");const auto current_token=parent_token;auto released=threads.ReleaseCurrent();
    preferences->CheckPersistence();
    if(jumps)jumps->DropThread(current_token,current_token);
    if(process_signals.Lookup(current_token)&&process_signals.DropThread(current_token))throw std::runtime_error("parent signal-thread cleanup failed");
    native_catalog->Revoke();
    if(released)throw std::runtime_error("main runner TLS/stack cleanup failed");
    if(frame_gate&&!frame_continues){std::fprintf(stderr,"Unity bootstrap: nativeRender returned false/requested Activity finish; one-frame startup was not successful\n");return 6;}
    std::fprintf(stderr,"Game bootstrap: normal profile completion=%s; original constructors/JNI, lifecycle and ownership checks complete\n",frame_gate?"frame":surface_gate?"surface":init_jni?"init":"default");return 0;
  }catch(const std::exception &error){std::fprintf(stderr,"Unity bootstrap: %s; stage=%s completed constructors=%zu\n",error.what(),stage,constructor_index);return 1;}
}

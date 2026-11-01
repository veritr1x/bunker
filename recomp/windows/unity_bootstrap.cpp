// Diagnostic execution gate for the actual translated libunity.so. This is not
// a game launcher: every constructor must run before JNI_OnLoad is attempted.
#include "jni_host.h"
#include "android_context.h"
#include "apk_assets.h"
#include "native_window.h"
#include "unity_lifecycle.h"
#include "filesystem.h"
#include "module_registry.h"
#include "pthread_host.h"
#include "libc.h"
#include "logging.h"
#include "zlib_host.h"
#include "../fastaes/elfload.h"
#include "unity_traces.h"
#include "unity_bootstrap_data.h"
#include <cstdio>
#include <atomic>
#include <charconv>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#include <windows.h>
#include <bcrypt.h>

namespace {
std::map<std::string,addr_t> resolved;
size_t constructor_index;
const char *stage="setup";
std::atomic<bool> jni_diagnostic_reached{false};
std::atomic<bool> init_java_diagnostic_active{false};
std::atomic<size_t> init_java_errors{0};
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
bool Translated(addr_t entry){
  // Generated trace table is ordered. Data exports are intentionally excluded.
  size_t low=0,high=std::size(kTraces);
  while(low<high){size_t mid=low+(high-low)/2;if(kTraces[mid].address<entry)low=mid+1;else high=mid;}
  return low<std::size(kTraces)&&kTraces[low].address==entry;
}
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
}
int main(int argc,char **argv){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  SetUnhandledExceptionFilter(Crash);_set_abort_behavior(0,3);
  const bool surface_gate=argc==7&&!std::strcmp(argv[4],"--surface-gate");
  if(argc!=4&&!(argc==5&&!std::strcmp(argv[4],"--init-jni"))&&!surface_gate){std::fprintf(stderr,"Usage: bunker-unity-bootstrap.exe <original-libunity.so> <original-game.apk> <writable-storage-directory> [--init-jni | --surface-gate <landscape-client-width> <height>]\n");return 2;}
  const bool init_jni=argc!=4;
  try{
    using namespace bunker::windows;
    namespace fs=std::filesystem;
    int32_t width=0,height=0;
    if(surface_gate){
      auto dimension=[](const char *text){int32_t value=0;auto end=text+std::strlen(text);auto result=std::from_chars(text,end,value);if(result.ec!=std::errc{}||result.ptr!=end||value<=0||value>32767)throw std::invalid_argument("surface dimensions must be integer client pixels in1..32767");return value;};
      width=dimension(argv[5]);height=dimension(argv[6]);if(width<=height)throw std::invalid_argument("APK sensorLandscape surface gate requires width greater than height");
    }
    if(std::size(kInitializers)!=kExpectedConstructors)throw std::runtime_error("trace/metadata constructor count mismatch");
    auto library=fs::canonical(fs::u8path(argv[1]));
    auto apk=fs::canonical(fs::u8path(argv[2]));
    if(Sha256(library)!=kUnitySha256||Sha256(apk)!=kApkSha256)throw std::runtime_error("runtime original Unity/APK SHA256 differs from verified translation/metadata");
    if(kExploratory)std::fprintf(stderr,"Unity bootstrap: EXPLORATORY DIAGNOSTIC ONLY: %zu unsupported translated traces remain; every real constructor will still execute\n",kUnsupportedTraces);
    else if(kUnsupportedTraces)throw std::runtime_error("strict bootstrap refuses unsupported translated traces");
    auto storage=fs::absolute(fs::u8path(argv[3]));fs::create_directories(storage);
    recomp::Runtime runtime;runtime.AddTraces(kTraces,std::size(kTraces));
    FileSystem files;
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
    AndroidContextConfig context_config;
    context_config.package_name=kPackageName;context_config.target_sdk=kTargetSdk;context_config.activity_class=kLaunchActivity;
    context_config.apk_assets=std::make_shared<ApkAssets>(apk);
    AndroidContext context(java,context_config);
    std::unique_ptr<NativeWindows> native_windows;
    // ModuleRegistry owns 0x7ff400000000; keep this combined provider disjoint.
    if(surface_gate)native_windows=std::make_unique<NativeWindows>(java,0x7ff440000000ULL);
    ModuleRegistry modules([&](addr_t entry){
      if(std::strcmp(stage,"constructors")==0){
        if(constructor_index>=std::size(kInitializers)||entry!=kInitializers[constructor_index])throw std::runtime_error("constructor order mismatch");
        std::fprintf(stderr,"Unity bootstrap: constructor %zu/%zu guest=%#llx\n",constructor_index+1,std::size(kInitializers),static_cast<unsigned long long>(entry));
      }else std::fprintf(stderr,"Unity bootstrap: %s callback guest=%#llx\n",stage,static_cast<unsigned long long>(entry));
      runner->Run(entry);
      if(std::strcmp(stage,"constructors")==0)++constructor_index;
    });
    LibC libc([&](addr_t entry,const std::vector<addr_t> &args){return runner->Run(entry,args);});
    logging.SetAllocator([&](uint64_t size){return libc.Malloc(size);});
    libc.SetErrorSink(error);libc.SetEnvironment({});
    // Destroy/join guest workers before the providers they may still call.
    Pthreads threads(runtime,Translated);threads.SetErrorSink(error);runner=&threads;
    Zlib zlib([&](addr_t entry,const std::vector<addr_t> &args){return threads.Run(entry,args);});
    struct Drain {Pthreads &threads;~Drain(){if(threads.Shutdown())std::abort();}} drain{threads};
    files.Install(runtime);threads.Install();libc.Install(runtime);logging.Install(runtime);modules.Install(runtime);
    if(init_jni)InstallDiagnosticJni(java,runtime);else java.Install(runtime);
    zlib.Install(runtime);
    if(native_windows)native_windows->Install(runtime);
    size_t provided=0,missing=0;
    for(const auto &import:kUnityImports){
      std::string name=import.name;addr_t address=0;
      // These provider namespaces are disjoint. The selected provider owns both
      // its function marker and data symbol representation (notably __sF).
      for(addr_t candidate:{Try(files,name),Try(threads,name),Try(libc,name),Try(logging,name),Try(modules,name),Try(zlib,name),native_windows?Try(*native_windows,name):0}){
        if(candidate){if(address&&address!=candidate)throw std::runtime_error("ambiguous import provider: "+name);address=candidate;}
      }
      if(address)++provided;
      else {
        if(import.is_object){std::fprintf(stderr,"Unity bootstrap: unsupported DATA import %s; refusing fabricated data\n",import.name);return 3;}
        address=0x7ffc00000000ULL+missing++*8;
        runtime.AddImport(address,[name,address](State &s){
          std::fprintf(stderr,"Unity bootstrap: unsupported import %s marker=%#llx guest-pc=%#llx return=%#llx; stage=%s, completed constructors=%zu/%zu\n",name.c_str(),static_cast<unsigned long long>(address),static_cast<unsigned long long>(s.gpr.pc.qword),static_cast<unsigned long long>(s.gpr.x30.qword),stage,constructor_index,std::size(kInitializers));
          std::fprintf(stderr,"Unity bootstrap: import arguments x0=%#llx x1=%#llx x2=%#llx x3=%#llx x4=%#llx x5=%#llx\n",static_cast<unsigned long long>(s.gpr.x0.qword),static_cast<unsigned long long>(s.gpr.x1.qword),static_cast<unsigned long long>(s.gpr.x2.qword),static_cast<unsigned long long>(s.gpr.x3.qword),static_cast<unsigned long long>(s.gpr.x4.qword),static_cast<unsigned long long>(s.gpr.x5.qword));
          std::fflush(stderr);std::abort();
        });
      }
      resolved.emplace(std::move(name),address);
    }
    std::fprintf(stderr,"Unity bootstrap: actual image SHA256=%s; %zu traces, %zu constructors, %zu imports provided, %zu explicit failure markers\n",kUnitySha256,std::size(kTraces),std::size(kInitializers),provided,missing);
    elf_image image;
    if(elf_load(library.u8string().c_str(),kUnityBase,Resolve,&image))return 4;
    if(image.span!=kUnityImageSpan)throw std::runtime_error("loaded image span differs from verified translation");
    Module unity;unity.name="libunity.so";unity.aliases={"/data/app/bunker/lib/arm64/libunity.so"};
    for(auto &symbol:kUnityExports){auto actual=reinterpret_cast<addr_t>(elf_symbol(&image,symbol.name));if(actual!=symbol.address)throw std::runtime_error(std::string("loaded export differs from translation: ")+symbol.name);unity.exports.emplace(symbol.name,actual);}
    unity.initializers.assign(std::begin(kInitializers),std::end(kInitializers));
    unity.finalizers.assign(std::begin(kUnityFinalizers),std::end(kUnityFinalizers));
    auto snapshot=std::make_shared<std::vector<uint8_t>>(image.base,image.base+image.span);
    unity.reset_image=[snapshot,&image]{recomp::WriteGuestMemory(reinterpret_cast<addr_t>(image.base),snapshot->data(),snapshot->size());};
    modules.Add(std::move(unity));
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
        auto window=native_windows->Create(width,height,u"Bunker native surface diagnostic",false);
        auto surface=native_windows->NewSurface(window);
        auto token=native_windows->FromSurface(surface);
        auto actual_width=native_windows->Width(token),actual_height=native_windows->Height(token);native_windows->Release(token);
        if(actual_width!=width||actual_height!=height)throw std::runtime_error("actual HWND client geometry differs from configured landscape pixels");
        std::fprintf(stderr,"Unity bootstrap: %ssurface-only host lifecycle port; actual HWND client=%dx%d; APK sensorLandscape; resumed=false; no Java class-init or render/resume claim\n",kExploratory?"EXPLORATORY ":"",actual_width,actual_height);
        UnitySurfaceLifecycle lifecycle(java,[&](addr_t target,const std::vector<addr_t>&args){
          std::fprintf(stderr,"Unity bootstrap: UnityMain host-thread=%lu native=%#llx argc=%zu env=%#llx receiver=%#llx display=%#llx surface=%#llx\n",GetCurrentThreadId(),static_cast<unsigned long long>(target),args.size(),static_cast<unsigned long long>(args.at(0)),static_cast<unsigned long long>(args.at(1)),static_cast<unsigned long long>(args.size()>2?args[2]:0),static_cast<unsigned long long>(args.size()>3?args[3]:0));
          auto result=threads.Run(target,args);std::fprintf(stderr,"Unity bootstrap: UnityMain native=%#llx returned\n",static_cast<unsigned long long>(target));return result;
        },{recreate,changed},player,[&]{if(threads.ReleaseCurrent())throw std::runtime_error("UnityMain runner TLS/stack cleanup failed");});
        lifecycle.AfterInitJni();lifecycle.Start();init_java_errors=0;init_java_diagnostic_active=true;
        stage="surfaceCreated/recreate";lifecycle.SurfaceCreated(surface);lifecycle.WaitIdle();
        stage="surfaceChanged/recreate+notify";lifecycle.SurfaceChanged(surface);lifecycle.WaitIdle();
        stage="surfaceDestroyed/recreate(null)";lifecycle.SurfaceDestroyed();lifecycle.Stop();
        init_java_diagnostic_active=false;
        if(init_java_errors.load())throw std::runtime_error("surface native calls encountered original Java exceptions");
        auto state=lifecycle.Describe();if(state.resumed||state.surface||state.started)throw std::runtime_error("surface lifecycle did not finish paused and detached");
        native_windows->Close(window);java.DeleteLocalReference(surface);
        std::fprintf(stderr,"Unity bootstrap: isolated surface handoff/detach gate passed on UnityMain; HWND closed after native detach acknowledgment; no nativeRender/nativeResume executed\n");
      }
    }
    stage="JNI_OnUnload";auto onunload=modules.Symbol(module,"JNI_OnUnload");if(onunload)threads.Run(onunload,{java.VmAddress(),0});
    stage="finalizers";if(modules.Close(module))throw std::runtime_error("Unity module finalization failed");
    libc.Finalize();threads.ReleaseCurrent();return 0;
  }catch(const std::exception &error){std::fprintf(stderr,"Unity bootstrap: %s; stage=%s completed constructors=%zu\n",error.what(),stage,constructor_index);return 1;}
}

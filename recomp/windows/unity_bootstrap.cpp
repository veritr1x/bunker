// Diagnostic execution gate for the actual translated libunity.so. This is not
// a game launcher: every constructor must run before JNI_OnLoad is attempted.
#include "jni_host.h"
#include "android_context.h"
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
}
int main(int argc,char **argv){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  SetUnhandledExceptionFilter(Crash);_set_abort_behavior(0,3);
  if(argc!=4){std::fprintf(stderr,"Usage: bunker-unity-bootstrap.exe <original-libunity.so> <original-game.apk> <writable-storage-directory>\n");return 2;}
  try{
    using namespace bunker::windows;
    namespace fs=std::filesystem;
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
    AndroidContext context(java,context_config);
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
    files.Install(runtime);threads.Install();libc.Install(runtime);logging.Install(runtime);modules.Install(runtime);java.Install(runtime);zlib.Install(runtime);
    size_t provided=0,missing=0;
    for(const auto &import:kUnityImports){
      std::string name=import.name;addr_t address=0;
      // These provider namespaces are disjoint. The selected provider owns both
      // its function marker and data symbol representation (notably __sF).
      for(addr_t candidate:{Try(files,name),Try(threads,name),Try(libc,name),Try(logging,name),Try(modules,name),Try(zlib,name)}){
        if(candidate){if(address&&address!=candidate)throw std::runtime_error("ambiguous import provider: "+name);address=candidate;}
      }
      if(address)++provided;
      else {
        if(import.is_object){std::fprintf(stderr,"Unity bootstrap: unsupported DATA import %s; refusing fabricated data\n",import.name);return 3;}
        address=0x7ffc00000000ULL+missing++*8;
        runtime.AddImport(address,[name,address](State &s){
          std::fprintf(stderr,"Unity bootstrap: unsupported import %s marker=%#llx guest-pc=%#llx return=%#llx; stage=%s, completed constructors=%zu/%zu\n",name.c_str(),static_cast<unsigned long long>(address),static_cast<unsigned long long>(s.gpr.pc.qword),static_cast<unsigned long long>(s.gpr.x30.qword),stage,constructor_index,std::size(kInitializers));
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
    for(auto name:kUnityJavaClasses){auto count=java.NativeCount(name);if(count)std::fprintf(stderr,"Unity bootstrap: registered %zu natives on %s\n",count,name);}
    // Reaching this line proves constructors and JNI registration only. Surface,
    // graphics/audio initialization and the game lifecycle are separate gates.
    std::fprintf(stderr,"Unity bootstrap: %sconstructor/JNI-only gate passed; %zu unsupported traces remain; the game is not running\n",kExploratory?"EXPLORATORY ":"",kUnsupportedTraces);
    stage="JNI_OnUnload";auto onunload=modules.Symbol(module,"JNI_OnUnload");if(onunload)threads.Run(onunload,{java.VmAddress(),0});
    stage="finalizers";if(modules.Close(module))throw std::runtime_error("Unity module finalization failed");
    libc.Finalize();threads.ReleaseCurrent();return 0;
  }catch(const std::exception &error){std::fprintf(stderr,"Unity bootstrap: %s; stage=%s completed constructors=%zu\n",error.what(),stage,constructor_index);return 1;}
}

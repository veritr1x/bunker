// Actual IL2CPP constructor/GC-initialization diagnostic; not a game launcher.
#include "filesystem.h"
#include "module_registry.h"
#include "pthread_host.h"
#include "libc.h"
#include "logging.h"
#include "zlib_host.h"
#include "signal_host.h"
#include "semaphore_host.h"
#include "../fastaes/elfload.h"
#include "il2cpp_traces.h"
#include "il2cpp_data.h"
#ifdef IL2CPP_MODULE_EXPORT_PROOF
#include "il2cpp_module_exports.h"
#endif
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <stdexcept>
#include <vector>
#include <windows.h>
#include <bcrypt.h>
#ifndef IL2CPP_OVERLAY_COUNT
#define IL2CPP_OVERLAY_COUNT 0
#endif
#ifndef IL2CPP_REMAINING_UNSUPPORTED
#define IL2CPP_REMAINING_UNSUPPORTED kUnsupportedTraces
#endif
namespace {
std::map<std::string,addr_t> resolved;
const char *stage="setup";size_t completed=0;
bool Translated(addr_t address){
  size_t lo=0,hi=std::size(kTraces);while(lo<hi){auto mid=lo+(hi-lo)/2;if(kTraces[mid].address<address)lo=mid+1;else hi=mid;}
  return lo<std::size(kTraces)&&kTraces[lo].address==address;
}
template<class P>addr_t Try(P&p,const std::string&name){try{return p.Marker(name);}catch(const std::invalid_argument&){return 0;}}
std::string Sha256(const std::filesystem::path&path){
  std::vector<uint8_t> object;
  struct Scope{BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;~Scope(){if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);}}scope;
  auto require=[](NTSTATUS status){if(status<0)throw std::runtime_error("Windows SHA256 failure");};
  require(BCryptOpenAlgorithmProvider(&scope.algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0));
  DWORD bytes=0,size=0;require(BCryptGetProperty(scope.algorithm,BCRYPT_OBJECT_LENGTH,(PUCHAR)&size,4,&bytes,0));object.resize(size);
  require(BCryptCreateHash(scope.algorithm,&scope.hash,object.data(),size,nullptr,0,0));
  std::ifstream file(path,std::ios::binary);if(!file)throw std::runtime_error("cannot hash original input");char buffer[65536];
  while(file.read(buffer,sizeof(buffer))||file.gcount())require(BCryptHashData(scope.hash,(PUCHAR)buffer,ULONG(file.gcount()),0));
  if(!file.eof())throw std::runtime_error("input read failed during SHA256");
  uint8_t result[32];require(BCryptFinishHash(scope.hash,result,32,0));std::string text;
  for(auto byte:result){text+="0123456789abcdef"[byte>>4];text+="0123456789abcdef"[byte&15];}return text;
}
void *Resolve(const char*name){auto i=resolved.find(name);if(i==resolved.end()){std::fprintf(stderr,"IL2CPP import absent from verified inventory: %s\n",name);std::abort();}return(void*)i->second;}
LONG WINAPI Crash(EXCEPTION_POINTERS*e){
  auto s=recomp::CurrentExecutionState();
  std::fprintf(stderr,"IL2CPP native exception %#lx at%p stage=%s constructors=%zu/9 guest-pc=%#llx return=%#llx\n",
    e->ExceptionRecord->ExceptionCode,e->ExceptionRecord->ExceptionAddress,stage,completed,
    (unsigned long long)(s?s->gpr.pc.qword:0),(unsigned long long)(s?s->gpr.x30.qword:0));
  std::fflush(stderr);return EXCEPTION_EXECUTE_HANDLER;
}
template<class T>T Read(addr_t address){T result{};recomp::ReadGuestMemory(&result,address,sizeof(result));return result;}
}
int main(int argc,char**argv){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);SetUnhandledExceptionFilter(Crash);_set_abort_behavior(0,3);
  const bool module_gate=argc==5&&!std::strcmp(argv[4],"--module-load-exports");
  const bool gc_signal_init=argc==5&&!std::strcmp(argv[4],"--gc-signal-init");
  if((argc!=4&&argc!=5)||(argc==5&&!module_gate&&!gc_signal_init)){std::fprintf(stderr,"Usage: il2cpp-bootstrap.exe original.so original.apk writable-storage [--gc-signal-init | --module-load-exports]\n");return 2;}
  try{
    using namespace bunker::windows;namespace fs=std::filesystem;
    auto library=fs::canonical(fs::u8path(argv[1])),apk=fs::canonical(fs::u8path(argv[2])),storage=fs::absolute(fs::u8path(argv[3]));fs::create_directories(storage);
    if(Sha256(library)!=kIl2cppSha256||Sha256(apk)!=kApkSha256)throw std::runtime_error("actual inputs differ from verified IL2CPP/APK hashes");
#ifndef IL2CPP_MODULE_EXPORT_PROOF
    if(module_gate)throw std::runtime_error("module export profile requires the separately prepared Unity lookup proof");
#else
    if(module_gate&&(std::size(kUnityRequestedExports)!=222||std::strcmp(kUnityApiProofApkSha256,kApkSha256)))throw std::runtime_error("Unity API proof is not bound to the actual original APK");
#endif
    if(std::size(kInitializers)!=9)throw std::runtime_error("actual IL2CPP constructor count differs");
    std::fprintf(stderr,"IL2CPP EXPLORATORY mixed snapshot: SHA256=%s; %zu traces,9 constructors,%u overlays,%u remaining unsupported traces; not a whole-library/game/GC proof\n",kIl2cppSha256,std::size(kTraces),unsigned(IL2CPP_OVERLAY_COUNT),unsigned(IL2CPP_REMAINING_UNSUPPORTED));
    recomp::Runtime runtime;runtime.AddTraces(kTraces,std::size(kTraces));
    FileSystem files;files.MountFile("/data/app/bunker/base.apk",apk);files.MountDirectory("/data/app/bunker/lib/arm64",library.parent_path());
    files.MountDirectory("/data/user/0/bunker",storage,true);files.SetWorkingDirectory("/data/user/0/bunker");auto error=[&](int e){files.SetError(e);};
    Pthreads *runner=nullptr;
    size_t finalized=0;
    ModuleRegistry modules([&](addr_t entry){
      if(module_gate){
        if(completed<std::size(kInitializers)){
          if(std::strcmp(stage,"module-open")||entry!=kInitializers[completed])throw std::runtime_error("module constructor order/owner differs");
          std::fprintf(stderr,"IL2CPP module constructor %zu/9 guest=%#llx\n",completed+1,(unsigned long long)entry);
          runner->Run(entry);++completed;return;
        }
        if(std::strcmp(stage,"module-close")||finalized>=std::size(kFinalizers)||
           entry!=kFinalizers[std::size(kFinalizers)-1-finalized])throw std::runtime_error("module finalizer order/owner differs");
        std::fprintf(stderr,"IL2CPP module finalizer %zu/2 guest=%#llx\n",finalized+1,(unsigned long long)entry);
        runner->Run(entry);++finalized;return;
      }
      runner->Run(entry);
    });
    LibC libc([&](addr_t entry,const std::vector<addr_t>&args){return runner->Run(entry,args);});libc.SetErrorSink(error);libc.SetEnvironment({});
    Logging logging;logging.SetErrorSink(error);logging.SetAllocator([&](uint64_t n){return libc.Malloc(n);});logging.SetStream([&](addr_t f,std::string_view text){return files.FWrite(text.data(),1,text.size(),f);});
    Pthreads threads(runtime,Translated);threads.SetErrorSink(error);runner=&threads;
    SignalHost signals([&](uint64_t id){
      std::fprintf(stderr,"IL2CPP unsupported effect: signal delivery requested for thread%#llx in unpolled old snapshot; stage=%s constructors=%zu/9\n",(unsigned long long)id,stage,completed);std::abort();
    });
    Semaphores semaphores(signals);signals.SetErrorSink(error);semaphores.SetErrorSink(error);
    // Backend teardown may invoke translated allocator callbacks. Keep every
    // import provider alive until Zlib has finished those callbacks.
    Zlib zlib([&](addr_t entry,const std::vector<addr_t>&args){return threads.Run(entry,args);});
    const auto primordial=threads.Self();if(signals.RegisterThread(primordial)||signals.BindCurrent(primordial))throw std::runtime_error("cannot bind actual primordial thread to signal policy");
    auto current=[&]{auto id=threads.Self();if(!signals.Lookup(id)||signals.Queue(id,0))throw std::runtime_error("actual worker has no integrated signal lifecycle");return id;};
    auto no_delivery=[](const SignalHost::Delivery&)->std::optional<uint64_t>{throw std::runtime_error("unpolled IL2CPP snapshot cannot deliver a signal");};
    struct Drain{Pthreads&threads;~Drain(){if(threads.Shutdown())std::abort();}}drain{threads};
    files.Install(runtime);modules.Install(runtime);libc.Install(runtime);logging.Install(runtime);threads.Install();zlib.Install(runtime);
    signals.Install(runtime,current,no_delivery);semaphores.Install(runtime,current,no_delivery);
    size_t provided=0,missing=0,weak=0;
    for(const auto &import:kImports){
      std::string name=import.name;addr_t address=0;
      // Explicit diagnostic ownership overrides pthread's ENOSYS signal stubs;
      // actual thread/stack/TLS services still belong to Pthreads.
      address=Try(signals,name);if(!address)address=Try(semaphores,name);
      if(!address)for(addr_t candidate:{Try(files,name),Try(threads,name),Try(libc,name),Try(logging,name),Try(modules,name),Try(zlib,name)}){
        if(candidate){if(address&&address!=candidate)throw std::runtime_error("ambiguous import provider: "+name);address=candidate;}
      }
      if(address)++provided;
      else if(import.weak){++weak;std::fprintf(stderr,"IL2CPP unresolved weak import uses ELF zero: %s\n",import.name);}
      else{
        if(import.object)throw std::runtime_error("missing actual data import: "+name);
        address=0x7ffc10000000ULL+missing++*8;
        runtime.AddImport(address,[name](State&s){
          std::fprintf(stderr,"IL2CPP unsupported import %s stage=%s constructors=%zu/9 guest-pc=%#llx return=%#llx x0=%#llx x1=%#llx x2=%#llx x3=%#llx\n",
            name.c_str(),stage,completed,(unsigned long long)s.gpr.pc.qword,(unsigned long long)s.gpr.x30.qword,
            (unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.x1.qword,(unsigned long long)s.gpr.x2.qword,(unsigned long long)s.gpr.x3.qword);
          std::fflush(stderr);std::abort();
        });
      }
      resolved.emplace(name,address);
    }
    std::fprintf(stderr,"IL2CPP imports: %zu provided,%zu explicit strong failure markers,%zu unresolved weak zeros\n",provided,missing,weak);
    elf_image image{};if(elf_load(library.u8string().c_str(),kIl2cppBase,Resolve,&image))return 3;
    if(image.span!=kIl2cppSpan)throw std::runtime_error("actual IL2CPP image span differs");
    Module module;module.name="libil2cpp.so";module.aliases={"/data/app/bunker/lib/arm64/libil2cpp.so"};
    for(auto &symbol:kExports){auto actual=(addr_t)elf_symbol(&image,symbol.name);if(actual!=symbol.address)throw std::runtime_error(std::string("ELF export differs: ")+symbol.name);module.exports.emplace(symbol.name,actual);}
    // The new profile gives libdl sole lifecycle ownership. Default/GC-init
    // modes retain their original explicit lifecycle calls for regression.
    if(module_gate){module.initializers.assign(std::begin(kInitializers),std::end(kInitializers));module.finalizers.assign(std::begin(kFinalizers),std::end(kFinalizers));}
    modules.Add(std::move(module));stage=module_gate?"module-open":"setup";
    auto handle=modules.Open(module_gate?"/data/app/bunker/lib/arm64/libil2cpp.so":"libil2cpp.so",2);
    if(!handle)throw std::runtime_error("cannot register translated IL2CPP module");
    if(!module_gate){stage="constructors";for(auto entry:kInitializers){
      if(!Translated(entry))throw std::runtime_error("actual constructor entry is not translated");
      std::fprintf(stderr,"IL2CPP constructor %zu/9 guest=%#llx\n",completed+1,(unsigned long long)entry);threads.Run(entry);++completed;
      uint64_t pending=0;if(signals.Pending(primordial,&pending)||pending||SignalHost::NeedsPoll(signals.Lookup(primordial)))throw std::runtime_error("constructor requires unsupported unpolled signal effects");
    }}
    std::fprintf(stderr,"IL2CPP ALL9 actual constructors completed in original order\n");
    if(module_gate){
#ifdef IL2CPP_MODULE_EXPORT_PROOF
      if(completed!=9||finalized||modules.ReferenceCount("libil2cpp.so")!=1)throw std::runtime_error("module load did not own exactly one constructor cycle/reference");
      uint64_t pending=0;if(signals.Pending(primordial,&pending)||pending||SignalHost::NeedsPoll(signals.Lookup(primordial)))throw std::runtime_error("module constructors require unpolled signal delivery");
      stage="module-export-lookups";size_t lookups=0;
      for(auto &request:kUnityRequestedExports){
        auto address=modules.Symbol(handle,request.name);
        if(!address||address!=request.address||address!=(addr_t)elf_symbol(&image,request.name)||!Translated(address))throw std::runtime_error(std::string("actual Unity-requested export differs: ")+request.name);
        ++lookups;
      }
      if(modules.Error())throw std::runtime_error("successful module lookups left a libdl error");
      auto second=modules.Open("libil2cpp.so",1);
      if(second!=handle||modules.ReferenceCount("libil2cpp.so")!=2||completed!=9||finalized)throw std::runtime_error("repeat module load reran lifecycle or changed handle");
      if(modules.Close(second)||modules.ReferenceCount("libil2cpp.so")!=1||completed!=9||finalized)throw std::runtime_error("nonfinal module close invoked finalizers");
      if(modules.Symbol(handle,kUnityRequestedExports[0].name)!=kUnityRequestedExports[0].address)throw std::runtime_error("nonfinal close invalidated a live export");
      std::fprintf(stderr,"IL2CPP module gate:222 exact Unity-requested export lookups,repeat alias load/refcount2,nonfinal close passed; API bodies NOT invoked; Unity source=%s\n",kUnityApiProofSha256);
#endif
    }
    if(gc_signal_init){
      stage="GC-signal-init";
      const auto entry=kIl2cppBase+0x25b3020,ack=kIl2cppBase+0x7cb1e68;int32_t count=0;AndroidSignalAction before30{},before24{};
      signals.Action(30,nullptr,&before30);signals.Action(24,nullptr,&before24);
      if(before30.handler||before24.handler||semaphores.GetValue(ack,&count)==0)throw std::runtime_error("GC signal setup is not pristine; refusing duplicate direct initialization");
      if(!Translated(entry))throw std::runtime_error("actual GC signal initializer not translated");
      std::fprintf(stderr,"IL2CPP calling actual parameterless GC signal initializer RVA0x25b3020; no GC records/global rewrites\n");threads.Run(entry);
      AndroidSignalAction stop{},restart{};signals.Action(30,nullptr,&stop);signals.Action(24,nullptr,&restart);
      if(stop.handler!=kIl2cppBase+0x25beb3c||restart.handler!=stop.handler||stop.flags!=0x10000004||restart.flags!=0x10000000)throw std::runtime_error("actual GC wrapper dispositions differ from independently audited binary");
      if(Read<int32_t>(kIl2cppBase+0x7984e14)!=30||Read<int32_t>(kIl2cppBase+0x7984e18)!=24||Read<addr_t>(kIl2cppBase+0x79a7698+30*8)!=kIl2cppBase+0x25b2af4||Read<addr_t>(kIl2cppBase+0x79a7698+24*8)!=kIl2cppBase+0x25b2c70)throw std::runtime_error("actual GC original-handler table/default signals differ");
      if(semaphores.GetValue(ack,&count)||count)throw std::runtime_error("real GC acknowledgment semaphore was not initialized empty");
      uint64_t mask=0;signals.Mask(primordial,0,nullptr,&mask);if(mask&(SignalHost::Bit(30)|SignalHost::Bit(24)))throw std::runtime_error("real GC setup did not unblock actual signals");
      std::fprintf(stderr,"IL2CPP real GC signal initialization passed:30/24 thunks/original handlers,empty semaphore,unblocked mask; suspension/collector correctness UNPROVED\n");
    }
    if(module_gate){
      stage="module-close";
      if(modules.Close(handle)||finalized!=2||completed!=9||modules.ReferenceCount("libil2cpp.so"))throw std::runtime_error("module final close did not own exactly one reverse finalizer cycle");
      if(modules.Symbol(handle,"il2cpp_init")||!modules.Error()||modules.Error())throw std::runtime_error("stale module handle/dlerror behavior differs");
      if(modules.Open("libil2cpp.so",2)||!modules.Error()||modules.Error()||completed!=9||finalized!=2)throw std::runtime_error("reopen without data reset must fail without lifecycle effects");
      std::fprintf(stderr,"IL2CPP module gate:exact9 constructors+2 reverse finalizers once,stale handle rejected,reopen without reset rejected; no init/GC/startup-hook/API-body execution\n");
    }else{
      stage="finalizers";for(auto i=std::rbegin(kFinalizers);i!=std::rend(kFinalizers);++i){std::fprintf(stderr,"IL2CPP finalizer guest=%#llx\n",(unsigned long long)*i);threads.Run(*i);}
    }
    libc.Finalize();if(!module_gate)modules.Close(handle);threads.ReleaseCurrent();signals.DropThread(primordial);
    std::fprintf(stderr,"IL2CPP diagnostic lifecycle completed; il2cpp_init/game/GC collection were not executed\n");return 0;
  }catch(const std::exception&e){std::fprintf(stderr,"IL2CPP bootstrap failed: %s; stage=%s constructors=%zu/9\n",e.what(),stage,completed);return 1;}
}

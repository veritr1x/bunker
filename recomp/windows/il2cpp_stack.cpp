// Original parameterless collector stack-top helper only; no collector init.
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
#include <array>
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
namespace {
std::map<std::string,addr_t> resolved;
const char *stage="setup";size_t constructed=0,finalized=0;unsigned checks=0;
void Require(bool condition,const char *why){if(!condition)throw std::runtime_error(why);++checks;}
template<class T>T Read(addr_t address){T result{};recomp::ReadGuestMemory(&result,address,sizeof(result));return result;}
bool Translated(addr_t address){size_t lo=0,hi=std::size(kTraces);while(lo<hi){auto mid=lo+(hi-lo)/2;if(kTraces[mid].address<address)lo=mid+1;else hi=mid;}return lo<std::size(kTraces)&&kTraces[lo].address==address;}
template<class P>addr_t Try(P&p,const std::string&name){try{return p.Marker(name);}catch(const std::invalid_argument&){return 0;}}
std::string Sha256(const std::filesystem::path &path){
  std::vector<uint8_t> storage;
  struct Scope{BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;~Scope(){if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);}}s;
  auto require=[](NTSTATUS status){if(status<0)throw std::runtime_error("input SHA256 failure");};
  require(BCryptOpenAlgorithmProvider(&s.algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0));DWORD size=0,bytes=0;require(BCryptGetProperty(s.algorithm,BCRYPT_OBJECT_LENGTH,(PUCHAR)&size,sizeof(size),&bytes,0));storage.resize(size);require(BCryptCreateHash(s.algorithm,&s.hash,storage.data(),size,nullptr,0,0));
  std::ifstream file(path,std::ios::binary);if(!file)throw std::runtime_error("cannot read original input");char buffer[65536];while(file.read(buffer,sizeof(buffer))||file.gcount())require(BCryptHashData(s.hash,reinterpret_cast<PUCHAR>(buffer),ULONG(file.gcount()),0));if(!file.eof())throw std::runtime_error("input read failed");uint8_t digest[32];require(BCryptFinishHash(s.hash,digest,sizeof(digest),0));std::string result;for(auto b:digest){result+="0123456789abcdef"[b>>4];result+="0123456789abcdef"[b&15];}return result;
}
void *Resolve(const char *name){auto found=resolved.find(name);if(found==resolved.end())throw std::runtime_error(std::string("import outside verified inventory: ")+name);return reinterpret_cast<void*>(found->second);}
LONG WINAPI Crash(EXCEPTION_POINTERS *error){auto state=recomp::CurrentExecutionState();std::fprintf(stderr,"IL2CPP stack native exception=%#lx stage=%s constructors=%zu/9 guest-pc=%#llx return=%#llx\n",error->ExceptionRecord->ExceptionCode,stage,constructed,(unsigned long long)(state?state->gpr.pc.qword:0),(unsigned long long)(state?state->gpr.x30.qword:0));return EXCEPTION_EXECUTE_HANDLER;}
struct CollectorState {
  uint32_t init_count,core_initialized;uint8_t adapter_initialized,record_initialized;
  std::array<addr_t,256> records;
  bool operator==(const CollectorState&b)const{return init_count==b.init_count&&core_initialized==b.core_initialized&&adapter_initialized==b.adapter_initialized&&record_initialized==b.record_initialized&&records==b.records;}
};
CollectorState Pristine(){CollectorState value{Read<uint32_t>(kIl2cppBase+0x79a6190),Read<uint32_t>(kIl2cppBase+0x79a62e0),Read<uint8_t>(kIl2cppBase+0x79a7998),Read<uint8_t>(kIl2cppBase+0x79a732c),Read<std::array<addr_t,256>>(kIl2cppBase+0x79a6b28)};Require(!value.init_count&&!value.core_initialized&&!value.adapter_initialized&&!value.record_initialized,"unexpected initialized collector state");for(auto record:value.records)Require(!record,"actual collector thread bucket must remain pristine");return value;}
}
int main(int argc,char **argv){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);SetUnhandledExceptionFilter(Crash);_set_abort_behavior(0,3);
  if(argc!=4){std::fputs("Usage: il2cpp-stack.exe original.so original.apk NEW-storage\n",stderr);return 2;}
  try{
    using namespace bunker::windows;namespace fs=std::filesystem;
    const auto library=fs::canonical(fs::u8path(argv[1])),apk=fs::canonical(fs::u8path(argv[2])),storage=fs::absolute(fs::u8path(argv[3]));fs::create_directories(storage);
    Require(Sha256(library)==kIl2cppSha256&&Sha256(apk)==kApkSha256,"original ELF/APK hash differs");Require(std::size(kInitializers)==9&&std::size(kFinalizers)==2,"actual module lifecycle differs");
    std::fprintf(stderr,"IL2CPP stack EXPLORATORY original393781-trace cohort +validated128-definition overlay;189 unsupported remain; no GC/init/metadata/suspension/savecallback\n");
    recomp::Runtime runtime;runtime.AddTraces(kTraces,std::size(kTraces));
    FileSystem files;files.MountFile("/data/app/bunker/base.apk",apk);files.MountDirectory("/data/app/bunker/lib/arm64",library.parent_path());files.MountDirectory("/data/user/0/bunker",storage,true);files.SetWorkingDirectory("/data/user/0/bunker");auto error=[&](int e){files.SetError(e);};
    Pthreads *runner=nullptr;
    ModuleRegistry modules([&](addr_t entry){
      if(!std::strcmp(stage,"module-open")){Require(constructed<9&&entry==kInitializers[constructed],"actual constructor order differs");std::fprintf(stderr,"IL2CPP stack constructor %zu/9 guest=%#llx\n",constructed+1,(unsigned long long)entry);runner->Run(entry);++constructed;}
      else if(!std::strcmp(stage,"module-close")){Require(finalized<2&&entry==kFinalizers[1-finalized],"actual reverse finalizer order differs");std::fprintf(stderr,"IL2CPP stack finalizer %zu/2 guest=%#llx\n",finalized+1,(unsigned long long)entry);runner->Run(entry);++finalized;}
      else throw std::runtime_error("unexpected module lifecycle callback");
    });
    LibC libc([&](addr_t entry,const std::vector<addr_t>&args){return runner->Run(entry,args);});libc.SetEnvironment({});libc.SetErrorSink(error);
    Logging logging;logging.SetErrorSink(error);logging.SetAllocator([&](uint64_t n){return libc.Malloc(n);});logging.SetStream([&](addr_t stream,std::string_view text){return files.FWrite(text.data(),1,text.size(),stream);});
    Pthreads threads(runtime,Translated);threads.SetErrorSink(error);runner=&threads;
    SignalHost signals([](uint64_t){std::fputs("IL2CPP stack gate cannot deliver unpolled signals\n",stderr);std::abort();});signals.SetErrorSink(error);Semaphores semaphores(signals);semaphores.SetErrorSink(error);
    Zlib zlib([&](addr_t entry,const std::vector<addr_t>&args){return threads.Run(entry,args);});
    const auto token=threads.Self();Require(!signals.RegisterThread(token)&&!signals.BindCurrent(token),"cannot bind actual primordial virtual signal identity");
    auto current=[&]{auto id=threads.Self();if(!signals.Lookup(id))throw std::runtime_error("unintegrated worker signal lifecycle");return id;};
    auto no_delivery=[](const SignalHost::Delivery&)->std::optional<uint64_t>{throw std::runtime_error("unpolled stack gate cannot deliver signals");};
    struct Drain{Pthreads&t;~Drain(){if(t.Shutdown())std::abort();}}drain{threads};
    files.Install(runtime);modules.Install(runtime);libc.Install(runtime);logging.Install(runtime);threads.Install();zlib.Install(runtime);signals.Install(runtime,current,no_delivery);semaphores.Install(runtime,current,no_delivery);
    size_t provided=0,missing=0;
    for(auto &import:kImports){std::string name=import.name;addr_t address=Try(signals,name);if(!address)address=Try(semaphores,name);if(!address)for(auto candidate:{Try(files,name),Try(threads,name),Try(libc,name),Try(logging,name),Try(modules,name),Try(zlib,name)})if(candidate){Require(!address||address==candidate,"ambiguous original import provider");address=candidate;}
      if(address)++provided;else if(import.weak)throw std::runtime_error("unexpected weak import in pinned image");else{Require(!import.object,"missing actual data import");address=0x7ffc10000000ULL+missing++*8;runtime.AddImport(address,[name](State&s){std::fprintf(stderr,"IL2CPP stack unsupported import %s stage=%s pc=%#llx LR=%#llx\n",name.c_str(),stage,(unsigned long long)s.gpr.pc.qword,(unsigned long long)s.gpr.x30.qword);std::abort();});}resolved.emplace(name,address);
    }
    std::fprintf(stderr,"IL2CPP stack imports: %zu real providers,%zu explicit failure markers\n",provided,missing);
    elf_image image{};Require(!elf_load(library.u8string().c_str(),kIl2cppBase,Resolve,&image)&&image.span==kIl2cppSpan,"original image-data load differs");
    Module module;module.name="libil2cpp.so";module.aliases={"/data/app/bunker/lib/arm64/libil2cpp.so"};module.initializers.assign(std::begin(kInitializers),std::end(kInitializers));module.finalizers.assign(std::begin(kFinalizers),std::end(kFinalizers));
    for(auto &symbol:kExports){auto actual=reinterpret_cast<addr_t>(elf_symbol(&image,symbol.name));Require(actual==symbol.address,"actual ELF export differs");module.exports.emplace(symbol.name,actual);}modules.Add(std::move(module));
    stage="module-open";auto handle=modules.Open("/data/app/bunker/lib/arm64/libil2cpp.so",2);Require(handle&&constructed==9&&!finalized&&modules.ReferenceCount("libil2cpp.so")==1,"module did not own exactly9 constructor calls");
    const auto pristine=Pristine();uint64_t pending=0;Require(!signals.Pending(token,&pending)&&!pending&&!SignalHost::NeedsPoll(signals.Lookup(token)),"unexpected signal request after constructors");
    AndroidThreadAttr before{},after{};uint64_t base=0,size=0;
    Require(!threads.GetAttr(token,&before)&&!threads.AttrGetStack(&before,&base,&size),"actual current guest stack attributes unavailable");Require(base&&size&&size<=UINT64_MAX-base&&!(base&15),"invalid actual guest stack range");
    MEMORY_BASIC_INFORMATION first{},last{};Require(VirtualQuery(reinterpret_cast<void*>(base),&first,sizeof(first))&&VirtualQuery(reinterpret_cast<void*>(base+size-1),&last,sizeof(last))&&first.State==MEM_COMMIT&&last.State==MEM_COMMIT,"actual guest stack lacks committed Windows backing");
    const auto entry=kIl2cppBase+0x25b1974;Require(Translated(entry),"original parameterless stack helper is not translated");stage="stack-top-helper";const auto top=threads.Run(entry);
    Require(top==base+size,"original helper did not return actual guest stack base+size");Require(threads.Self()==token&&!threads.GetAttr(token,&after)&&!std::memcmp(&before,&after,sizeof(before)),"helper changed current thread identity/stack attributes");
    Require(Pristine()==pristine,"stack helper changed real collector state");Require(!signals.Pending(token,&pending)&&!pending&&!SignalHost::NeedsPoll(signals.Lookup(token)),"stack helper requested signal delivery");
    std::fprintf(stderr,"IL2CPP actual stack helper passed: entry=%#llx token=%#llx guest=[%#llx,%#llx) result=%#llx; original pthread_self/getattr_np/attr_getstack/attr_destroy; PC/SP preserved\n",(unsigned long long)entry,(unsigned long long)token,(unsigned long long)base,(unsigned long long)(base+size),(unsigned long long)top);
    Require(!threads.AttrDestroy(&before)&&!threads.AttrDestroy(&after)&&threads.AttrGetStack(&before,&base,&size)==22,"attribute cleanup did not invalidate copied attr");
    // Keep all callbacks/providers and the original thread alive through close.
    stage="module-close";Require(!modules.Close(handle)&&constructed==9&&finalized==2&&!modules.ReferenceCount("libil2cpp.so"),"actual final close lifecycle differs");libc.Finalize();Require(Pristine()==pristine,"teardown unexpectedly initialized collector");
    stage="thread-retirement";Require(!threads.ReleaseCurrent(),"actual current TLS/thread cleanup failed");Require(threads.GetAttr(token,&after)==3,"retired old pthread token still exposes stack attributes");Require(!signals.DropThread(token),"actual virtual signal token retirement failed");
    std::fprintf(stderr,"IL2CPP stack gate passed: %u checks;9 actual constructors,2 reverse finalizers,current-thread cleanup; no init/GC/metadata/suspension/savecallback/longjmp executed\n",checks);return 0;
  }catch(const std::exception&e){std::fprintf(stderr,"IL2CPP stack gate failed: %s stage=%s constructors=%zu/9 finalizers=%zu/2\n",e.what(),stage,constructed,finalized);return 1;}
}

// New isolated original-API-loader diagnostic. Retains1756d78 unchanged.
#include "jni_host.h"
#include "android_context.h"
#include "apk_assets.h"
#include "java_native_libraries.h"
#include "combined_java_class.h"
#include "filesystem.h"
#include "module_registry.h"
#include "pthread_host.h"
#include "libc.h"
#include "logging.h"
#include "zlib_host.h"
#include "signal_host.h"
#include "semaphore_host.h"
#include "../whole/guest_memory.h"
#include "../fastaes/elfload.h"
#include <array>
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <stdexcept>
#include <vector>
#include <windows.h>
#include <bcrypt.h>
#include "combined_traces.h"
#include "combined_metadata.h"
static_assert(sizeof(State)==1200&&alignof(State)==16,"State differs from the audited recursive LLVM layout");
namespace {
using namespace bunker::windows;
const char*stage="setup";std::map<std::string,addr_t> resolved;
std::atomic<size_t> java_errors{0};
void Require(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
bool Translated(addr_t a){auto p=std::lower_bound(std::begin(kTraces),std::end(kTraces),a,[](const recomp::Trace&t,addr_t v){return t.address<v;});return p!=std::end(kTraces)&&p->address==a;}
template<class P>addr_t Try(P&p,const std::string&n){try{return p.Marker(n);}catch(const std::invalid_argument&){return 0;}}
void*Resolve(const char*n){auto p=resolved.find(n);if(p==resolved.end()){std::fprintf(stderr,"unlisted import:%s\n",n);std::abort();}return(void*)p->second;}
template<class T>T Read(addr_t a){T t{};recomp::ReadGuestMemory(&t,a,sizeof(t));return t;}
template<class T>T CheckedRead(addr_t a){
 MEMORY_BASIC_INFORMATION info{};Require(a&&VirtualQuery((void*)a,&info,sizeof(info))==sizeof(info),"snapshot address is not mapped");
 auto end=(addr_t)info.BaseAddress+info.RegionSize;
 auto protection=info.Protect&0xff;
 bool readable=protection==PAGE_READONLY||protection==PAGE_READWRITE||protection==PAGE_WRITECOPY||protection==PAGE_EXECUTE_READ||protection==PAGE_EXECUTE_READWRITE||protection==PAGE_EXECUTE_WRITECOPY;
 Require(info.State==MEM_COMMIT&&readable&&!(info.Protect&PAGE_GUARD)&&a<=end&&sizeof(T)<=end-a,"snapshot range is inaccessible");
 return Read<T>(a);
}
struct JniNode{addr_t node,object,vtable,target,next;bool operator==(const JniNode&o)const{return node==o.node&&object==o.object&&vtable==o.vtable&&target==o.target&&next==o.next;}};
std::vector<JniNode> JniCache(){
 std::vector<JniNode> entries;auto node=CheckedRead<addr_t>(0x7130da68);
 while(node){
  Require(entries.size()<128,"JNI cache list exceeds bounded snapshot");
  for(auto&e:entries)Require(e.node!=node,"JNI cache list cycles");
  auto object=CheckedRead<addr_t>(node),next=CheckedRead<addr_t>(node+8);
  auto vtable=object?CheckedRead<addr_t>(object):0,target=vtable?CheckedRead<addr_t>(vtable+8):0;
  entries.push_back({node,object,vtable,target,next});
  std::fprintf(stderr,"JNI-cache node=%#llx object=%#llx vtable=%#llx slot8=%#llx next=%#llx\n",(unsigned long long)node,(unsigned long long)object,(unsigned long long)vtable,(unsigned long long)target,(unsigned long long)next);
  node=next;
 }
 std::fprintf(stderr,"JNI-cache snapshot entries=%zu\n",entries.size());
 return entries;
}
void EmptyQueue(){
 std::array<uint8_t,0xc18> bytes{};recomp::ReadGuestMemory(bytes.data(),0x7127ef90,bytes.size());
 auto count=Read<uint32_t>(0x7127fb90);auto dirty=Read<uint8_t>(0x7127fba0);auto active=Read<addr_t>(0x7127fb98);
 std::fprintf(stderr,"Original startup queue count=%u active=%#llx dirty=%u\n",count,(unsigned long long)active,unsigned(dirty));
 Require(count==0&&active==0&&dirty==0&&std::all_of(bytes.begin(),bytes.end(),[](uint8_t b){return b==0;}),"original startup queue is nonempty/nonpristine; refusing callbacks");
}
struct NativeStringOwner{
 Pthreads&t;addr_t address;bool live=true;
 void Destroy(){Require(live,"NativeString destroyed twice");live=false;auto prior=stage;stage="actual owned NativeString destructor";t.Run(0x700e0044,{address});stage=prior;}
 ~NativeStringOwner(){if(live)try{Destroy();}catch(...){std::fprintf(stderr,"actual NativeString cleanup failed\n");std::abort();}}
};
std::string Sha256(const std::filesystem::path&p){
 BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;std::vector<uint8_t>obj;
 struct Guard{BCRYPT_ALG_HANDLE&a;BCRYPT_HASH_HANDLE&h;~Guard(){if(h)BCryptDestroyHash(h);if(a)BCryptCloseAlgorithmProvider(a,0);}}guard{alg,hash};
 auto check=[](NTSTATUS s){Require(s>=0,"SHA256 operation failed");};DWORD size=0,n=0;
 check(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0));
 check(BCryptGetProperty(alg,BCRYPT_OBJECT_LENGTH,(PUCHAR)&size,4,&n,0));obj.resize(size);
 check(BCryptCreateHash(alg,&hash,obj.data(),size,nullptr,0,0));
 std::ifstream f(p,std::ios::binary);Require(bool(f),"hash input absent");char bytes[65536];
 while(f.read(bytes,sizeof(bytes))||f.gcount())check(BCryptHashData(hash,(PUCHAR)bytes,ULONG(f.gcount()),0));
 Require(f.eof(),"hash input read failure");uint8_t result[32];check(BCryptFinishHash(hash,result,32,0));std::string s;
 for(auto b:result){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;
}
addr_t Jni(bunker::jni::Host&h,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){
 State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(slot,s);return s.gpr.x0.qword;
}
struct LocalFrame{bunker::jni::Host&h;LocalFrame(bunker::jni::Host&h):h(h){Require(!Jni(h,19,128),"local frame failed");}~LocalFrame(){Jni(h,20);}};
void InstallJava(bunker::jni::Host&h,recomp::Runtime&r){
 auto invoke=[&](bool vm,size_t slot,State&s){
  auto before=h.PendingException();try{if(vm)h.InvokeVm(slot,s);else h.InvokeEnv(slot,s);}
  catch(const std::exception&e){std::fprintf(stderr,"JNI slot%zu stage=%s:%s\n",slot,stage,e.what());std::abort();}
  auto after=h.PendingException();if(!after.empty()&&after!=before){++java_errors;std::fprintf(stderr,"new Java exception stage=%s LR=%#llx:%s\n",stage,(unsigned long long)s.gpr.x30.qword,after.c_str());}
 };
 for(size_t i=4;i<bunker::jni::kEnvSlots;++i)r.AddImport(h.EnvMarker(i),[invoke,i](State&s){invoke(false,i,s);});
 for(size_t i=3;i<bunker::jni::kVmSlots;++i)r.AddImport(h.VmMarker(i),[invoke,i](State&s){invoke(true,i,s);});
}
struct Ledger{
 std::string name;std::vector<addr_t>ctors,finis;size_t initialized=0,finalized=0;bool closing=false;
 void Run(addr_t a,Pthreads&t){
  auto expected=closing?(finalized<finis.size()?finis[finis.size()-1-finalized]:0):(initialized<ctors.size()?ctors[initialized]:0);
  Require(a==expected,"module lifecycle entry/order/owner mismatch");
  std::fprintf(stderr,"%s %s %zu/%zu guest=%#llx\n",name.c_str(),closing?"finalizer":"constructor",closing?finalized+1:initialized+1,closing?finis.size():ctors.size(),(unsigned long long)a);
  t.Run(a);if(closing)++finalized;else ++initialized;
 }
};
LONG WINAPI Crash(EXCEPTION_POINTERS*e){auto s=recomp::CurrentExecutionState();std::fprintf(stderr,"combined native exception %#lx stage=%s guestPC=%#llx LR=%#llx\n",e->ExceptionRecord->ExceptionCode,stage,(unsigned long long)(s?s->gpr.pc.qword:0),(unsigned long long)(s?s->gpr.x30.qword:0));std::fflush(stderr);return EXCEPTION_EXECUTE_HANDLER;}
}
int main(int argc,char**argv){
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);SetUnhandledExceptionFilter(Crash);_set_abort_behavior(0,3);
 if(argc!=4){std::fprintf(stderr,"Usage: api-loader.exe native-directory original.apk writable-storage\n");return 2;}
 try{
 namespace fs=std::filesystem;using namespace bunker::windows;
 auto dir=fs::canonical(fs::u8path(argv[1])),apk=fs::canonical(fs::u8path(argv[2])),storage=fs::absolute(fs::u8path(argv[3]));fs::create_directories(storage);
 Require(Sha256(dir/"libunity.so")==unity_image::kUnitySha256&&Sha256(dir/"libil2cpp.so")==il2cpp_image::kIl2cppSha256&&Sha256(apk)==unity_image::kApkSha256,"original input SHA256 differs");
 recomp::Runtime runtime;runtime.AddTraces(kTraces,std::size(kTraces));FileSystem files;
 files.MountFile("/data/app/bunker/base.apk",apk);files.MountDirectory("/data/app/bunker/lib/arm64",dir);files.MountDirectory("/data/user/0/bunker",storage,true);files.SetWorkingDirectory("/data/user/0/bunker");
 auto error=[&](int e){files.SetError(e);};Pthreads*runner=nullptr;Ledger*active=nullptr;
 Ledger unity{"Unity",{std::begin(unity_image::kConstructors),std::end(unity_image::kConstructors)},{std::begin(unity_image::kFinalizersOwned),std::end(unity_image::kFinalizersOwned)}};
 Ledger il2cpp{"IL2CPP",{std::begin(il2cpp_image::kConstructors),std::end(il2cpp_image::kConstructors)},{std::begin(il2cpp_image::kFinalizersOwned),std::end(il2cpp_image::kFinalizersOwned)}};
 ModuleRegistry modules([&](addr_t a){Require(active&&runner,"unowned module lifecycle");active->Run(a,*runner);});
 LibC libc([&](addr_t a,const std::vector<addr_t>&args){return runner->Run(a,args);});libc.SetErrorSink(error);libc.SetEnvironment({});
 Logging logging;logging.SetErrorSink(error);logging.SetAllocator([&](uint64_t n){return libc.Malloc(n);});logging.SetStream([&](addr_t f,std::string_view s){return files.FWrite(s.data(),1,s.size(),f);});
 bunker::jni::Host java(Translated);unity_image::DefineUnityJavaCatalog(java);DefineCombinedRuntimeClass(java);
 AndroidContextConfig config;config.package_name=unity_image::kPackageName;config.target_sdk=unity_image::kTargetSdk;config.activity_class=unity_image::kLaunchActivity;unity_image::ApplyUnityPackageMetadata(config);config.apk_assets=std::make_shared<ApkAssets>(apk);AndroidContext context(java,config);
 Pthreads threads(runtime,Translated);threads.SetErrorSink(error);runner=&threads;
 SignalHost signals([](uint64_t){std::fprintf(stderr,"unsupported unpolled combined signal delivery stage=%s\n",stage);std::abort();});signals.SetErrorSink(error);Semaphores semaphores(signals);semaphores.SetErrorSink(error);
 Zlib zlib([&](addr_t a,const std::vector<addr_t>&args){return threads.Run(a,args);});
 auto primordial=threads.Self();Require(!signals.RegisterThread(primordial)&&!signals.BindCurrent(primordial),"main signal binding failed");
 auto current=[&]{auto id=threads.Self();Require(bool(signals.Lookup(id)),"unregistered worker signal context");return id;};
 auto no_delivery=[](const SignalHost::Delivery&)->std::optional<uint64_t>{throw std::runtime_error("unpolled signal delivery unsupported");};
 struct Drain{Pthreads&t;~Drain(){if(t.Shutdown())std::abort();}}drain{threads};
 recomp::Runtime module_bridges;modules.Install(module_bridges);
 bool loading=false,closing_import=false;size_t actual_opens=0,actual_symbols=0,actual_errors=0,actual_closes=0;addr_t opened_handle=0;
 for(std::string name:{"dlopen","dlsym","dlclose","dlerror"}){
  auto marker=modules.Marker(name);
  runtime.AddImport(marker,[&,name,marker](State&s){
   try{
   auto argument=s.gpr.x0.qword;
   if(loading){
    if(name=="dlopen"){Require(recomp::ReadGuestString(argument)=="/data/app/bunker/lib/arm64/libil2cpp.so"&&s.gpr.x1.dword==2,"actual loader dlopen arguments differ");++actual_opens;}
    if(name=="dlsym"){Require(actual_symbols<std::size(il2cpp_image::kUnityRequestedExports)&&argument==opened_handle&&recomp::ReadGuestString(s.gpr.x1.qword)==il2cpp_image::kUnityRequestedExports[actual_symbols].name,"actual dlsym handle/name/order differs");++actual_symbols;}
    if(name=="dlerror")++actual_errors;
    Require(name!="dlclose","original loader entered failure cleanup");
   }
   if(closing_import&&name=="dlclose"){Require(argument==opened_handle,"guest cache closes another handle");++actual_closes;}
   module_bridges.Dispatch(s,marker,nullptr);
   if(loading&&name=="dlopen")opened_handle=s.gpr.x0.qword;
   }catch(const std::exception&e){std::fprintf(stderr,"module diagnostic %s stage=%s: %s\n",name.c_str(),stage,e.what());std::abort();}
  });
 }
 files.Install(runtime);libc.Install(runtime);logging.Install(runtime);threads.Install();zlib.Install(runtime);signals.Install(runtime,current,no_delivery);semaphores.Install(runtime,current,no_delivery);InstallJava(java,runtime);
 size_t missing=0;
 auto load=[&](const char*name,const auto&imports,addr_t base,uint64_t span,elf_image&image){
  resolved.clear();size_t provided=0,weak=0;
  for(auto&i:imports){std::string n=i.name;auto a=Try(signals,n);if(!a)a=Try(semaphores,n);
   if(!a)for(auto candidate:{Try(files,n),Try(threads,n),Try(libc,n),Try(logging,n),Try(modules,n),Try(zlib,n)})if(candidate){Require(!a||a==candidate,"ambiguous provider ownership");a=candidate;}
   if(a)++provided;else if(i.weak)++weak;else{Require(!i.object,"missing strong data import");a=0x7ffc30000000ULL+8*missing++;runtime.AddImport(a,[n](State&s){std::fprintf(stderr,"combined unsupported import:%s stage=%s LR=%#llx x0=%#llx x1=%#llx\n",n.c_str(),stage,(unsigned long long)s.gpr.x30.qword,(unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.x1.qword);std::fflush(stderr);std::abort();});}resolved.emplace(n,a);
  }
  std::fprintf(stderr,"%s imports:%zu provided,%zu weak-zero,cumulative%zu fail markers\n",name,provided,weak,missing);
  Require(!elf_load((dir/name).u8string().c_str(),base,Resolve,&image)&&image.span==span,"ELF image/span load failed");
 };
 elf_image u{},il{};load("libunity.so",unity_image::kCombinedImports,unity_image::kUnityBase,unity_image::kUnityImageSpan,u);load("libil2cpp.so",il2cpp_image::kCombinedImports,il2cpp_image::kIl2cppBase,il2cpp_image::kIl2cppSpan,il);
 auto add=[&](const char*name,const auto&exports,elf_image&image,Ledger&ledger){
  Module m;m.name=name;m.aliases={std::string("/data/app/bunker/lib/arm64/")+name};m.initializers=ledger.ctors;m.finalizers=ledger.finis;
  for(auto&s:exports){auto a=(addr_t)elf_symbol(&image,s.name);Require(a==s.address,"ELF export address differs");m.exports.emplace(s.name,a);}modules.Add(std::move(m));
 };
 add("libunity.so",unity_image::kUnityExports,u,unity);
 stage="Unity module-open";active=&unity;auto uh=modules.Open("/data/app/bunker/lib/arm64/libunity.so",2);active=nullptr;Require(uh&&unity.initialized==417,"Unity constructors incomplete");
 stage="Unity JNI_OnLoad";Require(threads.Run(modules.Symbol(uh,"JNI_OnLoad"),{java.VmAddress(),0})==bunker::jni::kVersion16,"JNI_OnLoad failed");
 auto unity_repeat=modules.Open("libunity.so",1);Require(unity_repeat==uh&&modules.ReferenceCount("libunity.so")==2&&unity.initialized==417&&!unity.finalized,"Unity repeat alias load changed lifecycle");
 Require(!modules.Close(unity_repeat)&&modules.ReferenceCount("libunity.so")==1&&!unity.finalized,"Unity nonfinal close changed lifecycle");
 Require(std::size(unity_image::kUnityRegistrations)==42,"native binding proof count differs");
 for(auto&b:unity_image::kUnityRegistrations)Require(java.NativeEntry(b.class_name,b.name,b.signature)==b.entry,"native binding differs");
 Require(!java_errors&&java.PendingException().empty(),"JNI_OnLoad Java exception");
 {LocalFrame frame(java);stage="Unity initJni(Context)";auto entry=java.NativeEntry("com/unity3d/player/UnityPlayer","initJni","(Landroid/content/Context;)V");Require(Translated(entry),"initJni unavailable");threads.Run(entry,{java.EnvAddress(),java.NewInstance("com/unity3d/player/UnityPlayer"),context.Activity()});Require(!java_errors&&java.PendingException().empty(),"initJni Java exception");}
 add("libil2cpp.so",il2cpp_image::kExports,il,il2cpp);
 addr_t ih=0;std::array<uint8_t,1784> published_slots{};
 {LocalFrame frame(java);auto app=Jni(java,6,(addr_t)"com/unity3d/player/UnityPlayer"),clazz=Jni(java,6,(addr_t)"java/lang/Class");
 auto method=Jni(java,33,clazz,(addr_t)"getClassLoader",(addr_t)"()Ljava/lang/ClassLoader;");auto loader=Jni(java,34,app,method);
 JavaNativeLibraries catalog(java,{loader,app,{{u"unity",u"/data/app/bunker/lib/arm64/libunity.so"},{u"il2cpp",u"/data/app/bunker/lib/arm64/libil2cpp.so"}}});
 std::array<uint8_t,1784> slots_before{},slots_after{};recomp::ReadGuestMemory(slots_before.data(),0x712bbfd0,slots_before.size());
 stage="Unity actual findLibrary helper";
 alignas(16)std::array<uint8_t,80> owned;owned.fill(0xa7);auto output=(addr_t)owned.data()+16;std::array<uint8_t,40> initial{};uint32_t tag=0x49;std::memcpy(initial.data()+32,&tag,4);recomp::WriteGuestMemory(output,initial.data(),initial.size());
 NativeStringOwner owner{threads,output};
 auto guards=[&]{for(size_t i=0;i<owned.size();++i)if(i<16||i>=56)Require(owned[i]==0xa7,"NativeString guard overwritten");};
 Require(recomp::ReadGuestString(0x70ed01b3)=="il2cpp","original literal differs");
 auto ok=threads.Run(0x7041a214,{0x70ed01b3,output});guards();
 std::string path;auto ptr=Read<addr_t>(output);auto length=Read<uint64_t>(output+24);auto actual_tag=Read<uint32_t>(output+32);path=recomp::ReadGuestString(ptr?ptr:output+8,4096);
 Require(ok==1&&!java_errors&&java.PendingException().empty(),"findLibrary helper failed/raised");
 Require(path=="/data/app/bunker/lib/arm64/libil2cpp.so","actual helper path differs");
 Require(length==path.size()&&actual_tag==0x49,"actual NativeString length/tag differs");
 std::fprintf(stderr,"Actual helper returned:%s; retaining owned40-byte NativeString for original APIloader\n",path.c_str());
 stage="original APIloader read-only preconditions";
 recomp::ReadGuestMemory(slots_before.data(),0x712bbfd0,slots_before.size());
 Require(std::all_of(slots_before.begin(),slots_before.end(),[](uint8_t b){return b==0;})&&Read<addr_t>(0x712bc6c0)==0,"original API slots/handle already resolved");
 Require(Read<addr_t>(0x712b97c0)==0,"Unity native module path cache is not pristine");EmptyQueue();
 auto before_jni=JniCache();
 // A nonempty list requires an independently audited virtual cleanup closure.
 // This first bounded profile accepts the proved empty closure only.
 Require(before_jni.empty(),"unproved nonempty JNI-cache cleanup closure; no APIloader executed");
 stage="original Unity APIloader";loading=true;active=&il2cpp;auto loaded=threads.Run(0x703b7650,{output});active=nullptr;loading=false;
 Require((loaded&1)&&actual_opens==1&&actual_symbols==222&&actual_errors==444,"original loader result/import journal differs");
 ih=Read<addr_t>(0x712bc6c0);Require(ih&&ih==opened_handle&&modules.ReferenceCount("libil2cpp.so")==1&&il2cpp.initialized==9&&!il2cpp.finalized,"original dlopen/module lifetime differs");
 for(size_t i=0;i<std::size(il2cpp_image::kUnityRequestedExports);++i){auto&r=il2cpp_image::kUnityRequestedExports[i];Require(Read<addr_t>(0x712bbfd0+i*8)==r.address&&(addr_t)elf_symbol(&il,r.name)==r.address&&Translated(r.address),"actual published slot differs from original export");}
 EmptyQueue();Require(JniCache()==before_jni,"APIloader mutated JNI-cache closure");
 owner.Destroy();guards();std::fprintf(stderr,"Original APIloader passed:dlopen1,dlsym222,dlerror444,9 constructors,refcount1,222 actual slots,empty queue/JNI closure; owned NativeString destructor once\n");
 recomp::ReadGuestMemory(published_slots.data(),0x712bbfd0,published_slots.size());
 catalog.Revoke();}
 stage="drain workers";Require(!threads.Shutdown(),"worker drain failed");
 stage="Unity JNI_OnUnload";Require(JniCache().empty(),"JNI cleanup closure changed before unload");auto unload=modules.Symbol(uh,"JNI_OnUnload");
 Require(unload==0x7043ab34&&Translated(unload)&&modules.ReferenceCount("libil2cpp.so")==1,"actual JNI_OnUnload entry/module lifetime differs");
 threads.Run(unload,{java.VmAddress(),0});Require(modules.ReferenceCount("libil2cpp.so")==1,"JNI_OnUnload changed IL2CPP lifetime");
 std::fprintf(stderr,"Actual JNI_OnUnload7043ab34 returned while IL2CPP remained live/refcount1\n");
 Require(JniCache().empty()&&!java_errors,"JNI_OnUnload left unproved cleanup/Java effects");
 stage="actual Unity cached handle close";il2cpp.closing=true;active=&il2cpp;closing_import=true;threads.Run(0x70384764,{ih});closing_import=false;active=nullptr;
 Require(actual_closes==1&&il2cpp.finalized==2&&modules.ReferenceCount("libil2cpp.so")==0,"actual guest cache close did not finalize IL2CPP once");
 auto cache=CheckedRead<addr_t>(0x712b97c0);Require(cache&&CheckedRead<addr_t>(cache)==cache+8&&CheckedRead<addr_t>(cache+8)==0&&CheckedRead<uint64_t>(cache+16)==0,"guest cache entry/node was not erased");
 Require(Read<addr_t>(0x712bc6c0)==ih,"unexpected top-level handle clearing");
 std::array<uint8_t,1784> retained_slots{};recomp::ReadGuestMemory(retained_slots.data(),0x712bbfd0,retained_slots.size());Require(retained_slots==published_slots,"unexpected API slot mutation at actual cache close");
 std::fprintf(stderr,"Real guest384764 closed IL2CPP and erased node; persistent empty map and stale top-level handle/API slots intentionally retained until process exit, never reused\n");
 stage="Unity final-close";unity.closing=true;active=&unity;Require(!modules.Close(uh),"Unity close failed");active=nullptr;Require(unity.finalized==2,"Unity finalizers incomplete");
 stage="TLS cleanup";libc.Finalize();Require(!threads.ReleaseCurrent(),"actual main thread TLS release failed");Require(!signals.DropThread(primordial),"actual main signal registration drop failed");
 std::fprintf(stderr,"ORIGINAL APILOADER bounded gate passed:417+9 constructors,JNI1.6/42 bindings,initJni,live helper NativeString,real dlopen/dlsym222/slot publication,empty queue/JNI closure,guest cache close,2+2 reverse finalizers; retained process-lifetime cache/slots; no IL2CPP API/init/GC/managed/RegisterModules execution\n");return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"combined gate failed stage=%s:%s\n",stage,e.what());return 1;}
}

// Original Managed-copy component diagnostic. Original boot/init remains separate.
#include "jni_host.h"
#include "android_context.h"
#include "apk_assets.h"
#include "java_native_libraries.h"
#include "android_internal_storage.h"
#include "managed_expected.h"
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
#include <set>
#include <optional>
#include <zlib.h>
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
constexpr addr_t kSRetAdapter=0x6ff00000,kOnceComponent=0x704250b8;
bool Translated(addr_t a){if(a==kSRetAdapter||a==kOnceComponent)return true;auto p=std::lower_bound(std::begin(kTraces),std::end(kTraces),a,[](const recomp::Trace&t,addr_t v){return t.address<v;});return p!=std::end(kTraces)&&p->address==a;}
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

extern "C" Memory *bunker_managed_once_704250b8(State&,addr_t,Memory*);
recomp::Runtime *adapter_runtime=nullptr;
struct SRetSpec{bool active=false;addr_t target=0,out=0,a0=0,a1=0;};
thread_local SRetSpec sret;
thread_local bool once_active=false;thread_local uint64_t once_sp=0;thread_local std::array<uint64_t,11> once_saved{};
extern "C" Memory*__real_sub_7024c6e4(State&,addr_t,Memory*);
extern "C" Memory*__real_sub_7024c36c(State&,addr_t,Memory*);
extern "C" Memory*__real_sub_70e71d10(State&,addr_t,Memory*);
extern "C" Memory*__real_sub_70e71dcc(State&,addr_t,Memory*);
size_t once_acquired=0,once_released=0;
Memory*OnceGuard(State&s,addr_t pc,Memory*m){try{
 const bool observed=once_active;const auto argument=s.gpr.x0.qword;
 if(observed)Require(argument==0x712c07f0,"once guard argument differs");
 if(pc==0x70e71d10){auto result=__real_sub_70e71d10(s,pc,m);if(observed){Require(once_acquired<2&&s.gpr.x0.dword==(once_acquired?0:1),"original once acquire result differs");++once_acquired;}return result;}
 Require(pc==0x70e71dcc,"unknown once guard observer");if(observed)Require(once_acquired==1&&once_released++==0,"original once release count differs");return __real_sub_70e71dcc(s,pc,m);
 }catch(const std::exception&e){std::fprintf(stderr,"MANAGED once guard failed:%s\n",e.what());std::abort();}}
struct FileEvents{std::map<addr_t,std::string>live;size_t opened=0,closed=0,renamed=0;}file_events;
recomp::Entry context_ctor=nullptr,context_dtor=nullptr,context_setter=nullptr;
struct ContextEvent{size_t slot;addr_t input,result;};std::vector<ContextEvent>context_events,constructor_events;
bool context_constructing=false,context_destroying=false,context_setting=false;size_t context_constructed=0,context_destroyed=0,context_set=0,initial_frees=0,final_frees=0,outer_frees=0,context_deleted_refs=0;
addr_t context_holder=0,context_payload=0,context_source=0,context_global=0,initial_payload=0,initial_global=0;
void ContextJni(bool vm,size_t slot,addr_t input,addr_t result){try{
 if(vm)return;
 if(context_setting&&(slot==21||slot==22))context_events.push_back({slot,input,result});
 if(context_constructing&&(slot==21||slot==22))constructor_events.push_back({slot,input,result});
 if(context_destroying&&slot==22)Require(context_deleted_refs++==0&&input==context_global,"original context DeleteGlobalRef ownership differs");
 }catch(const std::exception&e){std::fprintf(stderr,"MANAGED context JNI ownership failed:%s\n",e.what());std::abort();}}
Memory*ContextCtor(State&s,addr_t pc,Memory*m){try{
 Require(context_constructed++==0&&!context_constructing&&!Read<addr_t>(0x712bec00),"context constructor not sole observed cold owner");context_holder=s.gpr.x0.qword;context_constructing=true;auto result=context_ctor(s,pc,m);context_constructing=false;
 initial_payload=CheckedRead<addr_t>(context_holder);Require(initial_payload,"original context constructor omitted payload");initial_global=CheckedRead<addr_t>(initial_payload);auto refs=CheckedRead<uint32_t>(initial_payload+8);
 std::fprintf(stderr,"MANAGED observed initial context constructor stage=%s holder=%#llx payload=%#llx global=%#llx refcount=%u ctorJNIevents=%zu setterActive=%d\n",stage,(unsigned long long)context_holder,(unsigned long long)initial_payload,(unsigned long long)initial_global,refs,constructor_events.size(),int(context_setting));
 Require(refs==1,"actual initial context payload is shared");size_t created=0;for(auto&e:constructor_events)if(e.slot==21&&e.result==initial_global)++created;Require(initial_global?created==1:constructor_events.empty(),"initial context global ownership differs");return result;
 }catch(const std::exception&e){std::fprintf(stderr,"MANAGED context construction failed:%s\n",e.what());std::abort();}}
Memory*ContextSetter(State&s,addr_t pc,Memory*m){try{
 Require(pc==0x70439db0&&context_set++==0&&!context_setting&&!context_destroyed,"context initJni caller outside original one-prefix assignment");context_source=s.gpr.x2.qword;Require(context_source,"actual initJni context is NULL");context_setting=true;auto result=context_setter(s,pc,m);context_setting=false;
 Require(context_constructed==1&&Read<addr_t>(0x712bec00)==context_holder,"context setter lost observed holder");context_payload=CheckedRead<addr_t>(context_holder);context_global=CheckedRead<addr_t>(context_payload);auto refs=CheckedRead<uint32_t>(context_payload+8);
 size_t created=0,deleted_final=0,deleted_initial=0;for(auto&e:context_events){if(e.slot==21&&e.input==context_source&&e.result==context_global)++created;if(e.slot==22&&e.input==context_global)++deleted_final;if(e.slot==22&&e.input==initial_global)++deleted_initial;}
 std::fprintf(stderr,"MANAGED observed stable prefix context holder=%#llx payload=%#llx source=%#llx global=%#llx refcount=%u matchedNewRef=%zu deletedFinal=%zu initialPayloadFrees=%zu initialGlobalDeletes=%zu\n",(unsigned long long)context_holder,(unsigned long long)context_payload,(unsigned long long)context_source,(unsigned long long)context_global,refs,created,deleted_final,initial_frees,deleted_initial);
 Require(context_payload!=initial_payload&&context_global&&refs==1&&created==1&&!deleted_final&&initial_frees==1&&(initial_global?deleted_initial==1:deleted_initial==0),"original context setter handoff has unproved owner");return result;
 }catch(const std::exception&e){std::fprintf(stderr,"MANAGED context setter failed:%s\n",e.what());std::abort();}}
Memory*ContextFree(State&s,addr_t pc,Memory*m){try{
 auto pointer=s.gpr.x0.qword;if(pc==0x7024c6e4){if(context_setting&&initial_payload&&pointer==initial_payload)Require(initial_frees++==0,"initial context payload freed twice");if(context_destroying&&context_payload&&pointer==context_payload)Require(final_frees++==0,"final context payload freed twice");return __real_sub_7024c6e4(s,pc,m);}
 Require(pc==0x7024c36c,"unknown observed context free");if(context_destroying&&pointer==context_holder)Require(outer_frees++==0,"context holder freed twice");return __real_sub_7024c36c(s,pc,m);
 }catch(const std::exception&e){std::fprintf(stderr,"MANAGED context free ownership failed:%s\n",e.what());std::abort();}}
Memory*ContextDtor(State&s,addr_t pc,Memory*m){try{
 Require(context_constructed==1&&context_destroyed++==0&&s.gpr.x0.qword==0x712bec00&&Read<addr_t>(0x712bec00)==context_holder&&Read<addr_t>(context_holder)==context_payload&&Read<uint32_t>(context_payload+8)==1,"context destructor has unproved/shared owner");context_destroying=true;auto result=context_dtor(s,pc,m);context_destroying=false;Require(context_deleted_refs==1&&final_frees==1&&outer_frees==1&&!Read<addr_t>(0x712bec00),"original context cleanup did not release global/payload/holder once");return result;
 }catch(const std::exception&e){std::fprintf(stderr,"MANAGED context destruction failed:%s\n",e.what());std::abort();}}
std::array<uint64_t,11> Callee(const State&s){return {s.gpr.x19.qword,s.gpr.x20.qword,s.gpr.x21.qword,s.gpr.x22.qword,s.gpr.x23.qword,s.gpr.x24.qword,s.gpr.x25.qword,s.gpr.x26.qword,s.gpr.x27.qword,s.gpr.x28.qword,s.gpr.x29.qword};}
Memory*SRetEntry(State&s,addr_t pc,Memory*m){try{
 Require(pc==kSRetAdapter&&sret.active&&s.gpr.x0.qword==sret.target&&s.gpr.x1.qword==sret.out&&s.gpr.x2.qword==sret.a0&&s.gpr.x3.qword==sret.a1,"hidden-X8 harness adapter arguments differ");
 Require(sret.target==0x70371d90||sret.target==0x7037053c,"unapproved hidden-X8 original function");
 auto sp=s.gpr.sp.qword,thread=s.sr.tpidr_el0.qword;auto saved=Callee(s);
 s.gpr.x0.qword=sret.a0;s.gpr.x1.qword=sret.a1;s.gpr.x8.qword=sret.out;s.gpr.pc.qword=sret.target;
 std::fprintf(stderr,"MANAGED original hidden-X8 call target=%#llx out=%#llx a0=%#llx a1=%#llx stack=%#llx\n",(unsigned long long)sret.target,(unsigned long long)sret.out,(unsigned long long)sret.a0,(unsigned long long)sret.a1,(unsigned long long)sp);
 auto result=adapter_runtime->Dispatch(s,sret.target,m);
 Require(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==sp&&s.sr.tpidr_el0.qword==thread&&Callee(s)==saved,"original hidden-X8 return/stack/callee registers differ");return result;
 }catch(const std::exception&e){std::fprintf(stderr,"MANAGED X8 adapter failed:%s\n",e.what());std::abort();}}
void SRet(Pthreads&t,addr_t target,addr_t out,addr_t a0=0,addr_t a1=0){Require(!sret.active,"nested harness hidden return");sret={true,target,out,a0,a1};t.Run(kSRetAdapter,{target,out,a0,a1});sret.active=false;}
Memory*OnceEntry(State&s,addr_t pc,Memory*m){try{Require(pc==kOnceComponent&&!once_active,"once component reentry/address");once_active=true;once_sp=s.gpr.sp.qword;once_saved=Callee(s);auto result=bunker_managed_once_704250b8(s,pc,m);Require(!once_active&&s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==once_sp&&Callee(s)==once_saved,"once component boundary state differs");return result;}catch(const std::exception&e){std::fprintf(stderr,"MANAGED original once component failed:%s\n",e.what());std::abort();}}
struct EngineNode{addr_t address;std::array<uint8_t,0x38> bytes;bool operator==(const EngineNode&o)const{return address==o.address&&bytes==o.bytes;}};
std::vector<EngineNode>EngineList(){std::vector<EngineNode>result;auto node=CheckedRead<addr_t>(0x712b8e50);while(node){Require(result.size()<1024,"engine initializer list exceeds bounded inventory");for(auto&x:result)Require(x.address!=node,"engine list cycles");result.push_back({node,CheckedRead<std::array<uint8_t,0x38>>(node)});node=CheckedRead<addr_t>(node+0x28);}return result;}
void NoInit(){Require(!Read<uint8_t>(0x712b5078)&&!Read<uint32_t>(0x879a6190)&&!Read<uint8_t>(0x879a7998)&&!Read<uint32_t>(0x879a62e0),"component entered full engine/IL2CPP/GC initialization");}
struct OwnedString{
 Pthreads&t;alignas(16)std::array<uint8_t,80>bytes{};bool live=true;
 explicit OwnedString(Pthreads&t):t(t){bytes.fill(0xa6);std::array<uint8_t,40>value{};uint32_t tag=0x49;std::memcpy(value.data()+32,&tag,4);recomp::WriteGuestMemory(address(),value.data(),40);}
 addr_t address()const{return reinterpret_cast<addr_t>(bytes.data()+16);}
 void Guards()const{for(size_t n=0;n<bytes.size();++n)if(n<16||n>=56)Require(bytes[n]==0xa6,"NativeString guard changed");}
 std::string Text()const{Guards();auto ptr=Read<addr_t>(address()),length=Read<uint64_t>(address()+24);auto value=recomp::ReadGuestString(ptr?ptr:address()+8,4097);Require(value.size()==length&&value.size()<=4096,"NativeString actual length mismatch");return value;}
 void Set(addr_t text,uint64_t count){t.Run(0x700dff6c,{address(),text,count});Guards();}
 void Destroy(){Require(live,"NativeString double destroy");t.Run(0x700e0044,{address()});live=false;Guards();}
 ~OwnedString(){if(live)try{Destroy();}catch(...){std::abort();}}
};
struct OwnedPath{
 Pthreads&t;alignas(16)std::array<uint8_t,0x438+32>bytes{};bool live=false;
 explicit OwnedPath(Pthreads&t):t(t){bytes.fill(0x9b);}
 addr_t address()const{return reinterpret_cast<addr_t>(bytes.data()+16);}
 void Construct(const OwnedString&s){auto pointer=Read<addr_t>(s.address());std::array<uint64_t,2>view{pointer?pointer:s.address()+8,Read<uint64_t>(s.address()+24)};t.Run(0x702391a8,{address(),reinterpret_cast<addr_t>(view.data())});live=true;Guards();}
 void Guards()const{for(size_t n=0;n<bytes.size();++n)if(n<16||n>=16+0x438)Require(bytes[n]==0x9b,"Path guard changed");}
 void Destroy(){Require(live,"Path double destroy");t.Run(0x7023a378,{address()});live=false;Guards();}
 ~OwnedPath(){if(live)try{Destroy();}catch(...){std::abort();}}
};
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

uint32_t FileCrc(const std::filesystem::path&path){std::ifstream stream(path,std::ios::binary);Require(bool(stream),"CRC input absent");uint8_t bytes[65536];uint32_t crc=crc32(0,nullptr,0);while(stream.read((char*)bytes,sizeof(bytes))||stream.gcount())crc=crc32(crc,bytes,static_cast<uInt>(stream.gcount()));Require(stream.eof(),"CRC file read failed");return crc;}
std::pair<std::string,uint32_t>MappedDigest(addr_t address,uint64_t length){
 BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;std::vector<uint8_t>obj;
 struct Guard{BCRYPT_ALG_HANDLE&a;BCRYPT_HASH_HANDLE&h;~Guard(){if(h)BCryptDestroyHash(h);if(a)BCryptCloseAlgorithmProvider(a,0);}}guard{alg,hash};
 auto check=[](NTSTATUS value){Require(value>=0,"mapped SHA256 operation failed");};DWORD size=0,n=0;check(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0));check(BCryptGetProperty(alg,BCRYPT_OBJECT_LENGTH,(PUCHAR)&size,4,&n,0));obj.resize(size);check(BCryptCreateHash(alg,&hash,obj.data(),size,nullptr,0,0));
 uint8_t bytes[65536];uint32_t crc=crc32(0,nullptr,0);for(uint64_t offset=0;offset<length;){auto count=ULONG(std::min<uint64_t>(sizeof(bytes),length-offset));recomp::ReadGuestMemory(bytes,address+offset,count);check(BCryptHashData(hash,bytes,count,0));crc=crc32(crc,bytes,count);offset+=count;}
 uint8_t result[32];check(BCryptFinishHash(hash,result,32,0));std::string text;for(auto b:result){text+="0123456789abcdef"[b>>4];text+="0123456789abcdef"[b&15];}return {text,crc};
}
std::string Sha256(const std::filesystem::path&);
void ManagedCopy(Pthreads&t,FileSystem&files,const std::filesystem::path&storage){
 namespace fs=std::filesystem;stage="Managed-copy cold ownership preflight";NoInit();
 std::fprintf(stderr,"MANAGED preflight manager=%#llx registry=%#llx context=%#llx observedContext=%#llx ctor=%zu dtor=%zu nodeflags=%u/%u engine=%u once=%#llx guard=%#llx\n",(unsigned long long)Read<addr_t>(0x7125cdf0),(unsigned long long)Read<addr_t>(0x712bdf40),(unsigned long long)Read<addr_t>(0x712bec00),(unsigned long long)context_holder,context_constructed,context_destroyed,unsigned(Read<uint8_t>(0x712bdfb8)),unsigned(Read<uint8_t>(0x712bec78)),unsigned(Read<uint8_t>(0x712b5078)),(unsigned long long)Read<addr_t>(0x712c07e8),(unsigned long long)Read<uint64_t>(0x712c07f0));
 Require(Read<addr_t>(0x7125cdf0)==0&&Read<addr_t>(0x712bdf40)==0,"manager/archive component already owned before run");
 Require(context_constructed==1&&context_set==1&&!context_destroyed&&Read<addr_t>(0x712bec00)==context_holder&&Read<addr_t>(context_holder)==context_payload&&Read<uint32_t>(context_payload+8)==1,"prefix context has no sole observed owner");
 Require(!Read<uint8_t>(0x712bdfb8)&&!Read<uint8_t>(0x712bec78),"component engine-list node already initialized");
 Require(!Read<addr_t>(0x712c07e8)&&!Read<uint64_t>(0x712c07f0)&&recomp::ReadGuestString(0x7125c9a4,0x410).empty(),"custom backend/prefix/guard not cold");
 Require(JniCache().empty(),"unproved pre-copy JNI cleanup closure");auto nodes=EngineList();Require(!nodes.empty(),"no original engine initializer list");
 const auto destination=storage/"files"/"il2cpp";Require(!fs::exists(destination),"Managed destination must be genuinely absent in a fresh process");
 stage="original component filesystem-manager initialization";t.Run(0x7023907c);auto manager=Read<addr_t>(0x7125cdf0);Require(manager,"manager was not published");
 auto platform=CheckedRead<addr_t>(manager+8);Require(platform&&Read<addr_t>(platform)==0x7120a2e8&&Read<addr_t>(manager)==platform,"original manager/platform ownership differs");
 stage="original archive registry component initialization";t.Run(0x704151cc,{0x712bdf40});auto registry=Read<addr_t>(0x712bdf40);Require(registry&&!Read<uint64_t>(registry+0x40),"archive registry not fresh");
 stage="original APK registration/parser";const char*apk="/data/app/bunker/base.apk";Require(t.Run(0x70429c8c,{reinterpret_cast<addr_t>(apk)})&1,"original APK registration failed");
 Require(Read<uint64_t>(registry+0x40)==1&&recomp::ReadGuestString(0x7125c9a4,0x410)==apk,"real APK archive count/prefix differs");
 stage="original once cold component";t.Run(kOnceComponent);auto guard=Read<uint64_t>(0x712c07f0);Require((guard&1)&&Read<addr_t>(0x712c07e8)==0x7120a4d8,"real once guard/object publication failed");
 stage="original once warm component";t.Run(kOnceComponent);Require(Read<uint64_t>(0x712c07f0)==guard&&Read<addr_t>(0x712c07e8)==0x7120a4d8&&once_acquired==2&&once_released==1,"warm original once state/counts changed");
 stage="original custom ZIP registration";Require(t.Run(0x702380b4,{manager,0x712c07e8})&1,"custom ZIP backend registration failed");
 Require(Read<uint64_t>(manager+0x30)==1&&Read<addr_t>(Read<addr_t>(manager+0x20))==0x712c07e8,"actual custom vector ownership/count differs");
 {
 OwnedString prefix(t);stage="original hidden-X8 prefix virtual call";SRet(t,0x70371d90,prefix.address());Require(prefix.Text()==apk,"actual original prefix hidden return differs");prefix.Destroy();
 OwnedString assets(t),data(t),relative(t),managed(t),source(t),dest(t);
 Require(recomp::ReadGuestString(0x70ed9199)=="assets/bin/"&&recomp::ReadGuestString(0x70e7d5b6)=="Data"&&recomp::ReadGuestString(0x70eef4e1)=="Managed","original relative source literals differ");
 assets.Set(0x70ed9199,11);data.Set(0x70e7d5b6,4);SRet(t,0x7037053c,relative.address(),assets.address(),data.address());managed.Set(0x70eef4e1,7);SRet(t,0x7037053c,source.address(),relative.address(),managed.address());
 Require(source.Text()=="assets/bin/Data/Managed","original source joins differ");
 stage="actual files getter and owned context wrapper";auto files_path=t.Run(0x7041748c);Require(files_path&&recomp::ReadGuestString(files_path)=="/data/user/0/bunker/files","actual Unity files getter differs");
 Require(Read<addr_t>(0x712bec00)&&!Read<uint8_t>(0x712bec78)&&JniCache().empty(),"files getter ownership/JNI cleanup closure unproved");
 auto length=t.Run(0x700b80a0,{files_path});dest.Set(files_path,length);
 Require(recomp::ReadGuestString(0x70ed91bc)=="/il2cpp","original destination suffix differs");t.Run(0x700ee64c,{dest.address(),0x70ed91bc,7});Require(dest.Text()=="/data/user/0/bunker/files/il2cpp","original destination append differs");
 OwnedPath source_path(t),dest_path(t);stage="actual source/destination Path constructors and backend selection";source_path.Construct(source);dest_path.Construct(dest);
 Require(recomp::ReadGuestString(source_path.address(),0x410)=="assets/bin/Data/Managed"&&Read<addr_t>(source_path.address()+0x410)==0x712c07e8,"original relative source did not select custom ZIP backend");
 Require(recomp::ReadGuestString(dest_path.address(),0x410)==dest.Text()&&Read<addr_t>(dest_path.address()+0x410)==platform,"destination did not select original platform backend");
 Require(!fs::exists(destination),"destination unexpectedly exists before original copy");
 std::fprintf(stderr,"MANAGED original source ZIP=%#llx destination platform=%#llx; fresh destination absent; exact copy2392cc W2=1\n",(unsigned long long)Read<addr_t>(source_path.address()+0x410),(unsigned long long)platform);
 stage="actual original Managed directory copy2392cc";Require(t.Run(0x702392cc,{source_path.address(),dest_path.address(),1})&1,"actual original Managed copy returned failure");
 stage="actual copied APK byte inventory";std::set<std::string>expected,actual;uint64_t total=0;
 for(auto&e:kManagedExpected){auto path=destination/fs::u8path(e.name);Require(expected.insert(e.name).second&&fs::is_regular_file(path)&&fs::file_size(path)==e.size&&Sha256(path)==e.sha&&FileCrc(path)==e.crc,"actual copied Managed member bytes differ");total+=e.size;
  AndroidStat stat{};auto guest=dest.Text()+"/"+e.name;Require(!files.Stat(guest.c_str(),&stat)&&uint64_t(stat.size)==e.size,"copied member actual mounted stat differs");
 }
 for(auto&entry:fs::recursive_directory_iterator(destination)){Require(!fs::is_symlink(entry.symlink_status()),"unexpected copied symbolic link");if(entry.is_regular_file())actual.insert(entry.path().lexically_relative(destination).generic_u8string());else Require(entry.is_directory(),"unexpected copied file type");}
 Require(actual==expected&&expected.size()==24&&total==24570231,"actual copied tree membership/total differs");
 stage="actual copied metadata descriptor/read/mmap validation";const auto metadata=dest.Text()+"/Metadata/global-metadata.dat";auto descriptor=files.Open(metadata.c_str(),linux_flags::read_only);Require(descriptor>=0,"copied metadata open failed");std::array<uint32_t,4>header{};Require(files.Read(descriptor,header.data(),sizeof(header))==sizeof(header)&&header[0]==0xfab11baf&&header[1]==24,"actual copied metadata read/header differs");
 constexpr uint64_t metadata_size=23317064;auto mapping=files.Mmap(0,metadata_size,1,linux_flags::map_private,descriptor,0);Require(mapping!=~addr_t(0)&&files.MappingRegion(mapping,metadata_size,false).has_value(),"actual copied metadata mmap failed");Require(!files.Close(descriptor),"actual copied metadata descriptor close failed");auto digest=MappedDigest(mapping,metadata_size);std::string expected_metadata;for(auto&e:kManagedExpected)if(!std::strcmp(e.name,"Metadata/global-metadata.dat"))expected_metadata=e.sha;Require(!expected_metadata.empty()&&digest.first==expected_metadata&&digest.second==0xd1b42bda,"actual copied metadata mapping bytes/CRC differ");Require(!files.Munmap(mapping,metadata_size)&&!files.MappingRegion(mapping,1,false),"actual metadata mapping lifetime not retired");std::fprintf(stderr,"MANAGED copied metadata real fd/read/mmap after fd-close SHA256/CRC d1b42bda/version24 exact; mapping retired\n");
 std::fprintf(stderr,"MANAGED copied actual APK tree24 files24570231 bytes; every length/SHA256 and mounted Stat exact\n");
 source_path.Guards();dest_path.Guards();source_path.Destroy();dest_path.Destroy();
 }
 stage="original component-owned context teardown";Require(Read<addr_t>(0x712bec70)==0x70421934,"original context definition destructor differs");t.Run(0x70421934,{0x712bec00});Require(!Read<addr_t>(0x712bec00),"original context definition not cleared");
 stage="original component archive teardown while manager live";Require(Read<addr_t>(0x712bdfb0)==0x704151dc,"archive registered destructor differs");t.Run(0x704151dc,{0x712bdf40});Require(!Read<addr_t>(0x712bdf40)&&Read<addr_t>(0x7125cdf0)==manager,"archive teardown/lifetime failed");
 stage="original component manager teardown";t.Run(0x702390bc);Require(!Read<addr_t>(0x7125cdf0),"original manager not cleared");
 Require(file_events.opened&&file_events.opened==file_events.closed&&file_events.live.empty(),"original copy/archive FILE ownership not closed");std::fprintf(stderr,"MANAGED actual FILE lifetimes opened=%zu closed=%zu live=%zu renameCalls=%zu; original once acquire=2 release=1\n",file_events.opened,file_events.closed,file_events.live.size(),file_events.renamed);
 Require(EngineList()==nodes&&JniCache().empty()&&!java_errors,"component changed engine initialized nodes/JNI cleanup ownership");NoInit();
 Require(Read<uint64_t>(0x712c07f0)==guard&&Read<addr_t>(0x712c07e8)==0x7120a4d8&&recomp::ReadGuestString(0x7125c9a4,0x410)==apk,"genuine process-lifetime once/prefix state changed");
 std::fprintf(stderr,"MANAGED actual component teardown421934/4151dc/2390bc passed; no engine flags/reset/init/GC, genuine once/prefix retained until process exit\n");
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
  auto before=h.PendingException();auto context_input=s.gpr.x1.qword;try{if(vm)h.InvokeVm(slot,s);else h.InvokeEnv(slot,s);}
  catch(const std::exception&e){std::fprintf(stderr,"JNI slot%zu stage=%s:%s\n",slot,stage,e.what());std::abort();}
  ContextJni(vm,slot,context_input,s.gpr.x0.qword);auto after=h.PendingException();if(!after.empty()&&after!=before){++java_errors;std::fprintf(stderr,"new Java exception stage=%s LR=%#llx:%s\n",stage,(unsigned long long)s.gpr.x30.qword,after.c_str());}
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
 recomp::Runtime runtime;adapter_runtime=&runtime;std::vector<recomp::Trace>instrumented(std::begin(kTraces),std::end(kTraces));for(auto&trace:instrumented){if(trace.address==0x7042197c){context_ctor=trace.entry;trace.entry=ContextCtor;}if(trace.address==0x70421934){context_dtor=trace.entry;trace.entry=ContextDtor;}if(trace.address==0x70439db0){context_setter=trace.entry;trace.entry=ContextSetter;}}Require(context_ctor&&context_dtor&&context_setter,"original context ownership entries absent");runtime.AddTraces(instrumented.data(),instrumented.size());const recomp::Trace adapters[]={{kSRetAdapter,SRetEntry},{kOnceComponent,OnceEntry}};runtime.AddTraces(adapters,std::size(adapters));FileSystem files;
 files.MountFile("/data/app/bunker/base.apk",apk);files.MountDirectory("/data/app/bunker/lib/arm64",dir);files.MountDirectory("/data/user/0/bunker",storage,true);files.SetWorkingDirectory("/data/user/0/bunker");
 auto error=[&](int e){files.SetError(e);};Pthreads*runner=nullptr;Ledger*active=nullptr;
 Ledger unity{"Unity",{std::begin(unity_image::kConstructors),std::end(unity_image::kConstructors)},{std::begin(unity_image::kFinalizersOwned),std::end(unity_image::kFinalizersOwned)}};
 Ledger il2cpp{"IL2CPP",{std::begin(il2cpp_image::kConstructors),std::end(il2cpp_image::kConstructors)},{std::begin(il2cpp_image::kFinalizersOwned),std::end(il2cpp_image::kFinalizersOwned)}};
 ModuleRegistry modules([&](addr_t a){Require(active&&runner,"unowned module lifecycle");active->Run(a,*runner);});
 LibC libc([&](addr_t a,const std::vector<addr_t>&args){return runner->Run(a,args);});libc.SetErrorSink(error);libc.SetEnvironment({});
 Logging logging;logging.SetErrorSink(error);logging.SetAllocator([&](uint64_t n){return libc.Malloc(n);});logging.SetStream([&](addr_t f,std::string_view s){return files.FWrite(s.data(),1,s.size(),f);});
 bunker::jni::Host java(Translated);unity_image::DefineUnityJavaCatalog(java);
 AndroidContextConfig config;config.package_name=unity_image::kPackageName;config.target_sdk=unity_image::kTargetSdk;config.activity_class=unity_image::kLaunchActivity;unity_image::ApplyUnityPackageMetadata(config);config.prepare_internal_directory=MakeInternalDirectoryPreparer(files,config.data_dir);config.apk_assets=std::make_shared<ApkAssets>(apk);AndroidContext context(java,config);
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
 recomp::Runtime file_bridges;files.Install(file_bridges);std::set<addr_t>file_markers;
 auto journal_files=[&](const auto&imports){for(auto&i:imports){if(i.object)continue;std::string name=i.name;auto marker=Try(files,name);if(!marker||!file_markers.insert(marker).second)continue;
 runtime.AddImport(marker,[&,name,marker](State&s){try{auto argument=s.gpr.x0.qword;std::string path;
 if(name=="fopen")path=recomp::ReadGuestString(argument);
 if(name=="rename"){auto target=recomp::ReadGuestString(s.gpr.x1.qword);std::fprintf(stderr,"MANAGED actual rename stage=%s old=%s new=%s\n",stage,recomp::ReadGuestString(argument).c_str(),target.c_str());++file_events.renamed;}
 file_bridges.Dispatch(s,marker,nullptr);
 if(name=="fopen"&&s.gpr.x0.qword){Require(file_events.live.emplace(addr_t(s.gpr.x0.qword),path).second,"FILE token reused while live");++file_events.opened;}
 if(name=="fclose"&&file_events.live.count(argument)){Require(!s.gpr.x0.dword,"original fclose failed");file_events.live.erase(argument);++file_events.closed;}
 }catch(const std::exception&e){std::fprintf(stderr,"MANAGED FILE observer %s failed:%s\n",name.c_str(),e.what());std::abort();}});
 }};journal_files(unity_image::kCombinedImports);journal_files(il2cpp_image::kCombinedImports);libc.Install(runtime);logging.Install(runtime);threads.Install();zlib.Install(runtime);signals.Install(runtime,current,no_delivery);semaphores.Install(runtime,current,no_delivery);InstallJava(java,runtime);
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
 Require(!Read<addr_t>(0x712bec00)&&!Read<uint8_t>(0x712bec78)&&!context_constructed,"context definition must start cold before constructors/JNI");stage="Unity module-open";active=&unity;auto uh=modules.Open("/data/app/bunker/lib/arm64/libunity.so",2);active=nullptr;Require(uh&&unity.initialized==417,"Unity constructors incomplete");
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
 stage="original loaded log callback registration";addr_t log_api=0;
 for(size_t i=0;i<std::size(il2cpp_image::kUnityRequestedExports);++i)if(!std::strcmp(il2cpp_image::kUnityRequestedExports[i].name,"il2cpp_register_log_callback"))log_api=Read<addr_t>(0x712bbfd0+i*8);
 Require(log_api==0x8254ddb4,"original loaded log callback API differs");threads.Run(log_api,{0x70425524});Require(Read<addr_t>(0x87985068)==0x70425524,"original log callback storage differs");
 ManagedCopy(threads,files,storage);

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
 std::fprintf(stderr,"ORIGINAL MANAGED COPY bounded gate passed:417+9 constructors,JNI1.6/42 bindings,initJni,live helper NativeString,real dlopen/dlsym222/slot publication,empty queue/JNI closure,guest cache close,2+2 reverse finalizers; retained process-lifetime cache/slots; only original RegisterLogCallback API; original Managed files copied, no init/GC/managed-code/RegisterModules/full-engine-init/frame execution\n");return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"combined gate failed stage=%s:%s\n",stage,e.what());return 1;}
}

extern "C" Memory*bunker_managed_once_exit(State&s,addr_t pc,Memory*m){try{Require(once_active&&pc==0x70424ad8&&s.gpr.sp.qword==once_sp&&Callee(s)==once_saved,"original once join boundary differs");once_active=false;s.gpr.pc.qword=0xfeedffff;return m;}catch(const std::exception&e){std::fprintf(stderr,"MANAGED once exit failed:%s\n",e.what());std::abort();}}
extern "C" Memory*__wrap_sub_7024c6e4(State&s,addr_t pc,Memory*m){return ContextFree(s,pc,m);}
extern "C" Memory*__wrap_sub_7024c36c(State&s,addr_t pc,Memory*m){return ContextFree(s,pc,m);}
extern "C" Memory*__wrap_sub_70e71d10(State&s,addr_t pc,Memory*m){return OnceGuard(s,pc,m);}
extern "C" Memory*__wrap_sub_70e71dcc(State&s,addr_t pc,Memory*m){return OnceGuard(s,pc,m);}

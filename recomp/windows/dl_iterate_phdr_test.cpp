#include "module_registry.h"
#include "module_registry_elf.h"
#include "pthread_host.h"
#include "../fastaes/elfload.h"
#include "../whole/cooperative_poll.h"
#include "../whole/bridge.h"
#include "traces.h"
#include "original-phdr-expectations.h"
#include "original-phdr-heads.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>
using namespace bunker::windows;
extern "C" {
#define ORIGINAL(name) Memory*sub_##name(State&,addr_t,Memory*);
ORIGINAL_PHDR_HEADS(ORIGINAL)
#undef ORIGINAL
}
namespace {
constexpr addr_t kControl=0x7ff480000000ULL,kCopy=0x7ff480000008ULL;
unsigned checks=0,ndk_calls=0,callbacks=0,genuine_queries=0,mutations=0;
void Check(bool b,const char*w){++checks;if(!b)throw std::runtime_error(w);}
template<class F>void Reject(F f,const char*w){bool caught=false;try{f();}catch(const std::exception&){caught=true;}Check(caught,w);}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
struct Record {uint64_t addr,phdr,size,adds,subs,tlsid,tlsdata;uint32_t phnum,pad;char name[128];AndroidElf64Phdr headers[16];};
struct Output {uint64_t before=0x1122334455667788ULL;int32_t count=0,stop_after=0,stop_code=0,action=0;Record records[8]{};uint64_t after=0x8877665544332211ULL;};
static_assert(sizeof(Record)==1088&&sizeof(Output)==8736);
constexpr recomp::Trace originals[]={
#define ORIGINAL(name) {0x##name##ULL,sub_##name},
ORIGINAL_PHDR_HEADS(ORIGINAL)
#undef ORIGINAL
};
bool Translated(addr_t p){return std::any_of(std::begin(kTraces),std::end(kTraces),[&](const auto&t){return t.address==p;})||std::any_of(std::begin(originals),std::end(originals),[&](const auto&t){return t.address==p;});}
std::vector<uint8_t> File(const char*p){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("missing frozen original ELF");return {std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>()};}
std::function<addr_t(const char*)>resolve;
void*Resolve(const char*n){return reinterpret_cast<void*>(resolve(n));}
struct Harness {
  recomp::Runtime runtime;Pthreads threads{runtime,Translated};
  ModuleRegistry registry{[this](addr_t pc){Lifecycle(pc);},0x7ff400000000ULL};
  elf_image unity{},il{},guest{};ModuleAddressImage u_meta,i_meta;std::vector<uint8_t>u_snapshot,i_snapshot;
  addr_t call=0,recorder=0;uint64_t u_handle=0,i_handle=0;bool lifecycle_checks=false;unsigned loading_seen=0,closing_seen=0,nested_seen=0;Output nested{};
  Harness(){
    runtime.AddTraces(kTraces,std::size(kTraces));runtime.AddTraces(originals,std::size(originals));threads.SetErrorSink([](int){});threads.Install();registry.Install(runtime);
    // Metadata-only mappings use nonzero uncalled TEST import addresses. No
    // original module constructor or imported module API executes in this gate.
    resolve=[](const char*){return addr_t(0x7ff4fffffff0ULL);};
    Check(!elf_load_bionic(UNITY_IMAGE,0x70000000,Resolve,&unity)&&!elf_load_bionic(IL2CPP_IMAGE,0x80000000,Resolve,&il),"map both exact original relocated data images");
    auto u=File(UNITY_IMAGE),i=File(IL2CPP_IMAGE);u_meta=DescribeModuleElf(u.data(),u.size(),0x70000000,"/guest/lib/libunity.so");i_meta=DescribeModuleElf(i.data(),i.size(),0x80000000,"/guest/lib/libil2cpp.so");
    u_snapshot.assign(unity.base,unity.base+unity.span);i_snapshot.assign(il.base,il.base+il.span);
    Module um{"libunity.so",{}, {},{0x5e000001},{0x5e000002},[this]{recomp::WriteGuestMemory(reinterpret_cast<addr_t>(unity.base),u_snapshot.data(),u_snapshot.size());},u_meta};
    Module im{"libil2cpp.so",{}, {},{0x5e000003},{0x5e000004},[this]{recomp::WriteGuestMemory(reinterpret_cast<addr_t>(il.base),i_snapshot.data(),i_snapshot.size());},i_meta};
    registry.Add(std::move(um));registry.Add(std::move(im));Module typed{"typed-fixture-service",{},{{"probe",kControl}},{},{},{},std::nullopt};typed.kind=Module::Kind::TypedService;registry.Add(std::move(typed));
    resolve=[this](const char*n){if(!std::strcmp(n,"dl_iterate_phdr"))return registry.Marker(n);if(!std::strcmp(n,"phdr_fixture_control"))return kControl;if(!std::strcmp(n,"memcpy"))return kCopy;throw std::runtime_error(std::string("unexpected new guest import: ")+n);};
    Check(!elf_load(SAMPLE_IMAGE,0x76000000,Resolve,&guest),"load genuine NDK caller/callback");call=reinterpret_cast<addr_t>(elf_symbol(&guest,"phdr_call"));recorder=reinterpret_cast<addr_t>(elf_symbol(&guest,"phdr_record_callback"));Check(Translated(call)&&Translated(recorder),"NDK direct and callback heads selected");
    registry.SetProgramHeaderRunner([this](addr_t cb,addr_t info,uint64_t size,addr_t data){Check(Translated(cb)&&size==64,"actual callback entry and modern ABI extent");const auto value=Read<AndroidDlPhdrInfo>(info);Check(value.dlpi_phdr&&value.dlpi_phnum&&value.dlpi_name,"real module metadata pointers supplied");++callbacks;return static_cast<int32_t>(threads.Run(cb,{info,size,data}));});
    runtime.AddImport(kControl,recomp::MakeBridge<void(int32_t)>([this](int32_t action){Mutate(action);}));
    runtime.AddImport(kCopy,recomp::MakeBridge<addr_t(addr_t,addr_t,uint64_t)>([](addr_t dst,addr_t src,uint64_t n){std::vector<uint8_t>b(n);recomp::ReadGuestMemory(b.data(),src,b.size());recomp::WriteGuestMemory(dst,b.data(),b.size());return dst;}));
  }
  void Lifecycle(addr_t pc){if(!lifecycle_checks)return;Output out;Check(registry.IterateProgramHeaders(recorder,reinterpret_cast<addr_t>(&out))==0,"reentrant enumeration from TEST lifecycle");Check(out.count>=1,"Loading/Closing real ELF remains enumerable");if(pc==0x5e000001||pc==0x5e000003)++loading_seen;else ++closing_seen;}
  void Mutate(int32_t action){++mutations;if(action==1){i_handle=registry.Open("libil2cpp.so",1);Check(i_handle!=0,"nested callback opens real second ELF");nested=Output{};Check(registry.IterateProgramHeaders(recorder,reinterpret_cast<addr_t>(&nested))==0,"nested translated callback enumeration under recursive loader lock");++nested_seen;}else if(action==2){Check(i_handle&&registry.Close(i_handle)==0,"nested callback closes not-yet-visited real ELF");i_handle=0;}else throw std::runtime_error("unknown TEST mutation");}
  int32_t Call(Output&out,int mode){++ndk_calls;auto result=static_cast<int32_t>(threads.Run(call,{reinterpret_cast<addr_t>(&out),addr_t(mode)}));Check(out.before==0x1122334455667788ULL&&out.after==0x8877665544332211ULL,"NDK callback output canaries intact");return result;}
  void RecordMatches(const Record&r,const ModuleAddressImage&m){Check(r.addr==m.load_bias&&r.phdr==m.mapped_program_headers&&r.phnum==m.program_headers.size()&&r.size==64,"all original program headers use exact mapped address/count/bias");Check(std::string(r.name)==m.filename&&!r.tlsid&&!r.tlsdata,"actual module pathname and genuine no-TLS fields");Check(!std::memcmp(r.headers,m.program_headers.data(),m.program_headers.size()*sizeof(AndroidElf64Phdr)),"every original program-header byte preserved including GNU_EH_FRAME/DYNAMIC");}
  struct Search {uint64_t pc,text=0,data=0,function=0,fde=0;uint32_t cache=1,pad=0;};
  void Genuine(){
    for(unsigned repeat=0;repeat<2;++repeat)for(const auto&expected:kExpected){Search query{expected.pc};const auto before=callbacks;Check(registry.IterateProgramHeaders(0x82627024,reinterpret_cast<addr_t>(&query))==1,"genuine original callback stops at containing real image");Check(query.fde==expected.fde&&query.function==expected.function,"genuine EH-header search returns independent original FDE/function");Check(query.fde!=0&&callbacks>before,"nonzero original FDE obtained through real catalog callback");++genuine_queries;}
    Search outside{0x1234};const auto before=callbacks;Check(registry.IterateProgramHeaders(0x82627024,reinterpret_cast<addr_t>(&outside))==0&&outside.fde==0&&callbacks-before==2,"genuine outside-PC callback continues over both real modules");++genuine_queries;
  }
  void Run(){
    // Bounded fail-closed metadata controls. Both have a valid callback runner
    // and real mapped-table owner; neither may reach that runner on rejection.
    for(bool tls:{false,true}){
      ModuleRegistry rejected([](addr_t){});unsigned called=0;rejected.SetProgramHeaderRunner([&](addr_t,addr_t,uint64_t,addr_t){++called;return int32_t(0);});auto metadata=u_meta;
      if(tls){Check(!metadata.program_headers.empty(),"real source has program headers for TLS negative");metadata.program_headers.back().type=7;}else{metadata.program_headers.clear();metadata.mapped_program_headers=0;}
      Module module{"libunity.so",{},{},{},{},[]{},metadata};rejected.Add(std::move(module));const auto handle=rejected.Open("libunity.so",1);Check(handle!=0,"negative control is an active real ELF metadata catalog");
      std::string reason;try{rejected.IterateProgramHeaders(recorder,0);}catch(const std::exception&e){reason=e.what();}
      Check(reason.find(tls?"ELF TLS module":"without complete original mapped program headers")!=std::string::npos&&called==0,"TLS/incomplete catalog rejected for exact reason before callback");Check(rejected.Close(handle)==0,"negative metadata control lifetime closes");
    }
    auto typed=registry.Open("typed-fixture-service",1);Check(typed!=0,"explicit non-ELF typed service is active TEST control");
    lifecycle_checks=true;u_handle=registry.Open("libunity.so",1);Check(u_handle!=0,"first actual ELF opened");
    Output opened;opened.action=1;Check(Call(opened,0)==0&&opened.count==2,"live outer iteration sees nested-appended second module");RecordMatches(opened.records[0],u_meta);RecordMatches(opened.records[1],i_meta);Check(opened.records[1].adds==opened.records[0].adds+1&&opened.records[1].subs==opened.records[0].subs,"load counter is rebuilt per callback after nested open");Check(nested_seen==1&&nested.count==2,"nested recursive iteration sees actual two-module live list");
    for(int mode=0;mode<2;++mode){Output out;Check(Call(out,mode)==0&&out.count==2,"actual NDK direct/function-pointer enumeration visits two modules");RecordMatches(out.records[0],u_meta);RecordMatches(out.records[1],i_meta);Check(out.records[0].adds==out.records[1].adds&&out.records[0].subs==out.records[1].subs,"unchanged live catalog counters consistent");}
    for(int code:{37,-77}){Output out;out.stop_after=1;out.stop_code=code;Check(Call(out,code==37?0:1)==code&&out.count==1,"exact signed32 early-stop callback return propagated");}
    Genuine();const auto old_i=i_handle;Output removed;removed.action=2;Check(Call(removed,1)==0&&removed.count==1,"closing future module removes it from live iteration");i_handle=registry.Open("libil2cpp.so",1);Check(i_handle&&i_handle!=old_i,"reopened ELF obtains later live generation");Output reopened;Check(Call(reopened,0)==0&&reopened.count==2,"reopened generation appended after current first image");RecordMatches(reopened.records[0],u_meta);RecordMatches(reopened.records[1],i_meta);Check(reopened.records[0].adds==opened.records[1].adds+1&&reopened.records[0].subs==opened.records[1].subs+1,"actual reopen/unload counters observed");Genuine();
    const auto same=registry.Open("libunity.so",1);Check(same==u_handle&&registry.Close(same)==0,"repeat Open/Close is reference-only");Output refs;Check(Call(refs,1)==0&&refs.records[0].adds==reopened.records[0].adds&&refs.records[0].subs==reopened.records[0].subs,"reference-only Open/Close does not change load events");
    Reject([&]{registry.IterateProgramHeaders(0xdeadbeef,0);},"untranslated callback rejected before guest execution");
    Check(registry.Close(i_handle)==0&&registry.Close(u_handle)==0&&registry.Close(typed)==0,"real ELF and typed lifetimes close");Check(loading_seen==3&&closing_seen==3,"all real Loading/Closing TEST lifecycle callbacks can enumerate active image");Check(!threads.Shutdown()&&!threads.ReleaseCurrent(),"actual Pthreads callback lifetime closed");
    std::printf("DL-ITERATE-PHDR-PASS checks=%u ndk_calls=%u callbacks=%u genuine_queries=%u mutations=%u",checks,ndk_calls,callbacks,genuine_queries,mutations);std::putchar(10);
  }
};
}
extern "C" Memory*sub_820ca440(State&s,addr_t,Memory*m){addr_t p=s.gpr.x0.qword;uint64_t n=0;while(Read<uint8_t>(p+n)){++n;}s.gpr.x0.qword=n;s.gpr.pc.qword=s.gpr.x30.qword;return m;}
extern "C" Memory*sub_820cbb10(State&,addr_t,Memory*){std::fputs("genuine original unwind abort path reached\n",stderr);std::abort();}
int main(){try{Harness h;h.Run();return 0;}catch(const std::exception&e){std::fprintf(stderr,"DL-ITERATE-PHDR-FAIL %s\n",e.what());return 1;}}

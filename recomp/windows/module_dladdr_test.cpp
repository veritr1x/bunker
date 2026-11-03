#include "module_registry_elf.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0},calls{0};
thread_local int error_slot;
constexpr addr_t kErrno=0x7ffc20000000ULL,kAddress=0x7ffc20000008ULL;
ModuleRegistry*registry;
void Check(bool ok,const char*message){if(!ok){std::fprintf(stderr,"dladdr check: %s\n",message);std::abort();}++checks;}
std::vector<uint8_t> Bytes(const char*path){std::ifstream file(path,std::ios::binary);Check(bool(file),"fixture bytes opened");return {std::istreambuf_iterator<char>(file),{}};}
void*Resolve(const char*name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(kErrno);if(!std::strcmp(name,"dladdr"))return reinterpret_cast<void*>(kAddress);if(!std::strcmp(name,"dlsym"))return reinterpret_cast<void*>(registry->Marker("dlsym"));return reinterpret_cast<void*>(addr_t(0x7ffe10000000ULL));}
void Retire(elf_image&image){
#ifdef _WIN32
 Check(VirtualFree(image.base,0,MEM_RELEASE)!=0,"VirtualAlloc image retirement");
#else
 Check(!munmap(image.base,image.span),"mmap image retirement");
#endif
 std::free(const_cast<uint8_t*>(image.file));image={};
}
template<class F>void Reject(F f,const char*part){try{f();}catch(const std::exception&e){Check(std::strstr(e.what(),part)!=nullptr,"named unsupported boundary");return;}Check(false,"expected rejection");}
uint64_t SymbolValue(const ModuleAddressImage&m,const char*n){for(const auto&s:m.symbols)if(s.name==n&&s.section)return s.value;Check(false,"required raw symbol");return 0;}
struct Rela{uint64_t offset,info;int64_t addend;};
struct Section{uint32_t name,type;uint64_t flags,address,offset,size;uint32_t link,info;uint64_t align,entry;};
template<class T>T At(const std::vector<uint8_t>&b,size_t at){Check(at<=b.size()&&sizeof(T)<=b.size()-at,"test metadata independent bounds");T t;std::memcpy(&t,b.data()+at,sizeof(t));return t;}
void Relocations(const std::vector<uint8_t>&file,const ModuleAddressImage&m,const elf_image&raw,const elf_image&biased){
 const auto shoff=At<uint64_t>(file,40);const auto count=At<uint16_t>(file,60);unsigned abs64=0,glob=0,ordinary=0,relative=0;
 for(unsigned i=0;i<count;++i){auto sec=At<Section>(file,shoff+i*64);if(sec.type!=4)continue;auto syms=At<Section>(file,shoff+sec.link*64);
  for(uint64_t at=0;at<sec.size;at+=24){const auto r=At<Rela>(file,sec.offset+at);const auto type=uint32_t(r.info),index=uint32_t(r.info>>32);const auto sym=syms.offset+uint64_t(index)*24;auto section=At<uint16_t>(file,sym+6);auto value=At<uint64_t>(file,sym+8);uint64_t a,b;std::memcpy(&a,raw.base+r.offset,8);std::memcpy(&b,biased.base+r.offset,8);
   if(type==1027){Check(a==reinterpret_cast<addr_t>(raw.base)+r.addend&&b==reinterpret_cast<addr_t>(biased.base)+r.addend,"RELATIVE unchanged between profiles");++relative;}
   else if(section==0xfff1){Check(a==value+r.addend&&b==reinterpret_cast<addr_t>(biased.base)+value+r.addend,"actual SHN_ABS relocation raw versus Bionic bias/addend");if(type==257){Check(r.addend==7,"ABS64 actual nonzero addend");++abs64;}if(type==1025)++glob;}
   else{Check(a-reinterpret_cast<addr_t>(raw.base)==b-reinterpret_cast<addr_t>(biased.base),"ordinary relocation offset unchanged");++ordinary;}
  }
 }
 Check(abs64&&glob&&ordinary&&relative,"fixture contains ABS64/GLOB_DAT/ordinary/RELATIVE relocations");Check(SymbolValue(m,"fixture_abs")==0x1234,"actual SHN_ABS raw integrity value");
}
}
int main(int argc,char**argv){
#ifdef _WIN32
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
 ModuleRegistry modules({});registry=&modules;recomp::Runtime runtime;modules.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
 runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&error_slot);});
 runtime.AddImport(kAddress,[&](State&s){auto a=s.gpr.x0.qword,b=s.gpr.x1.qword;runtime.Dispatch(s,modules.Marker("dladdr"),nullptr);++calls;Check(s.gpr.x1.qword==b,"dladdr bridge keeps output argument");Check(s.gpr.x0.qword<=1,"real bridge W0 result zero-extends");(void)a;});
 elf_image caller{};Check(!elf_load(CALLER_LIBRARY,0x5d000000,Resolve,&caller),"NDK caller image");
 auto Run=[&](addr_t address,AndroidDlInfo*out,int indirect,int expected){alignas(16)std::array<uint8_t,65536>stack{};State state{};int error=0;state.gpr.x0.qword=address;state.gpr.x1.qword=reinterpret_cast<addr_t>(out);state.gpr.x2.dword=indirect;state.gpr.x3.qword=reinterpret_cast<addr_t>(&error);state.gpr.x19.qword=0x123456789abcdef0ULL;state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&caller,"guest_dladdr")));Check(state.gpr.x0.qword==addr_t(expected)&&error==731,"actual NDK direct/functionpointer return/errno");Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&state.gpr.x19.qword==0x123456789abcdef0ULL,"NDK PC/SP/saved GPR");};
 if(argc>1){const std::string mode=argv[1];Module m;m.name="negative";
  if(mode!="incomplete"){ModuleAddressImage image;image.filename="/guest/negative.so";image.base=image.load_bias=0x74000000;image.span=0x1000;image.loads={{0,0x1000}};ModuleAddressSymbol sym{"bad",0x100,8,1,uint8_t(mode=="tls"?6:10)};sym.binding=1;if(mode=="ambiguity"){sym.type=2;sym.version=2;}image.symbols.push_back(sym);if(mode=="ambiguity"){sym.version=3;sym.value=0x200;image.symbols.push_back(sym);}m.address_image=std::move(image);m.export_policy=Module::ExportPolicy::BionicRawSymbols;m.exports["bad"]=1;}
  modules.Add(std::move(m));auto handle=modules.Open("negative",1);
  if(mode=="incomplete")Run(1,nullptr,1,0);
  else{alignas(16)std::array<uint8_t,65536>stack{};State state{};state.gpr.x0.qword=handle;state.gpr.x1.qword=reinterpret_cast<addr_t>("bad");state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&caller,"guest_dlsym")));}
  return 2;
 }
 Check(modules.Marker("dladdr")==modules.Marker("dlerror")+8&&modules.Marker("dlerror")==0x7ff400000018ULL,"four old markers unchanged/fifth appended");
 unsigned fixture_index=0;
 for(const char*path:{SYSV_LIBRARY,GNU_LIBRARY}){
  const addr_t base=0x62000000ULL+fixture_index++*0x04000000ULL;auto bytes=Bytes(path);elf_image raw{},biased{};Check(!elf_load(path,base,Resolve,&raw)&&!elf_load_bionic(path,base+0x01000000,Resolve,&biased),"real raw and Bionic loader variants");auto metadata=DescribeModuleElf(bytes.data(),bytes.size(),base,"/guest/lib/fixture"+std::to_string(fixture_index)+".so");Relocations(bytes,metadata,raw,biased);
  auto original_metadata=metadata;Module m;m.name="fixture"+std::to_string(fixture_index);m.address_image=std::move(metadata);m.export_policy=Module::ExportPolicy::BionicRawSymbols;for(const auto&s:original_metadata.symbols)if(s.binding==1&&s.section)m.exports[s.name]=0;const auto name=m.name;modules.Add(std::move(m));auto h=modules.Open(name.c_str(),1);Check(h!=0,"registered real ELF opens");
  unsigned hidden=0,defaults=0;for(const auto&s:original_metadata.symbols)if(s.name=="fixture_versioned"){if(s.version&0x8000)++hidden;else ++defaults;}Check(hidden==1&&defaults==1,"actual NDK V1 hidden plus V2 default dynsym metadata");Check(modules.Symbol(h,"fixture_versioned")==base+SymbolValue(original_metadata,"fixture_v2"),"ordinary Bionic dlsym skips hidden V1 and selects actual V2 helper");Check(!modules.Error(),"default version success has no dlerror");Check(!modules.Symbol(h,"fixture_hidden_only")&&modules.Error()&&!modules.Error(),"hidden-only version is ordinary missing with one dlerror");std::printf("reference-%u version default=V2 hidden-only=missing\n",fixture_index);
  // Real hash-eligible GLOBAL dynsym entries with only st_other changed. Bionic
  // lookup checks binding/definition, not STV_HIDDEN/INTERNAL. No native code is
  // executed from these modified bytes; only owned factory metadata is used.
  auto visibility=bytes;const auto shoff=At<uint64_t>(bytes,40);const auto shnum=At<uint16_t>(bytes,60);unsigned changed=0;
  for(unsigned i=0;i<shnum;++i){auto sec=At<Section>(bytes,shoff+i*64);if(sec.type!=11)continue;auto strings=At<Section>(bytes,shoff+sec.link*64);for(uint64_t at=0;at<sec.size;at+=24){auto si=At<uint32_t>(bytes,sec.offset+at);const char*sn=reinterpret_cast<const char*>(bytes.data()+strings.offset+si);if(!std::strcmp(sn,"fixture_function")){visibility[sec.offset+at+5]=2;++changed;}if(!std::strcmp(sn,"fixture_data")){visibility[sec.offset+at+5]=1;++changed;}}}
  Check(changed==2,"actual dynamic symbol visibility-only fixture mutation");const auto vb=base+0x02000000;Module vm;vm.name="visibility"+std::to_string(fixture_index);vm.address_image=DescribeModuleElf(visibility.data(),visibility.size(),vb,"/guest/lib/visibility.so");vm.export_policy=Module::ExportPolicy::BionicRawSymbols;vm.exports={{"fixture_function",1},{"fixture_data",1}};const auto vn=vm.name;modules.Add(std::move(vm));auto vh=modules.Open(vn.c_str(),1);for(const char*symbol:{"fixture_function","fixture_data"})Check(modules.Symbol(vh,symbol)==vb+SymbolValue(original_metadata,symbol),"Bionic hash-eligible hidden/internal GLOBAL export remains resolvable");Check(modules.Close(vh)==0,"visibility-only metadata profile closed");
  std::fill(bytes.begin(),bytes.end(),0); // metadata must own bytes and names.
  for(const char*symbol:{"fixture_function","fixture_data"})for(unsigned offset=0;offset<2;++offset)for(int indirect:{0,1}){
   const auto value=SymbolValue(original_metadata,symbol);struct{uint64_t before;AndroidDlInfo out;uint64_t after;}guard{UINT64_C(0xa5a5a5a5a5a5a5a5),{},UINT64_C(0x5a5a5a5a5a5a5a5a)};auto&out=guard.out;Run(base+value+offset,&out,indirect,1);Check(out.base==base&&out.symbol_address==base+value&&!std::strcmp(reinterpret_cast<const char*>(out.symbol_name),symbol)&&!std::strcmp(reinterpret_cast<const char*>(out.filename),original_metadata.filename.c_str()),"exact real ELF address/symbol/path identity");Check(guard.before==UINT64_C(0xa5a5a5a5a5a5a5a5)&&guard.after==UINT64_C(0x5a5a5a5a5a5a5a5a),"known Dl_info exactly32 and no adjacent overwrite");Check(modules.Symbol(h,symbol)==base+value,"Bionic ordinary symbol address");
   std::printf("reference-%u known %s offset=%u indirect=%d return=1 errno=731 base-offset=%llu\n",fixture_index,symbol,offset,indirect,static_cast<unsigned long long>(out.symbol_address-out.base));
  }
  Check(modules.Symbol(h,"fixture_abs")==base+0x1234&&reinterpret_cast<addr_t>(elf_symbol(&raw,"fixture_abs"))==0x1234,"raw helper remains integrity lookup; optin Bionic ABS bias");Check(modules.Symbol(h,"fixture_zero")==base,"Bionic zero ABS has bias without changing explicit map contract");
  const auto tagged=(base+SymbolValue(original_metadata,"fixture_function"))|UINT64_C(0xab00000000000000);AndroidDlInfo tagged_out{};Run(tagged,&tagged_out,1,1);Check(tagged_out.filename&&tagged_out.base==base&&!tagged_out.symbol_name&&!tagged_out.symbol_address,"top byte removed for owner only, original tagged symbol lookup");
  const auto *stable=reinterpret_cast<const char*>(tagged_out.filename);
  for(const auto &load:original_metadata.loads)if(load.memory_size){AndroidDlInfo out{};Check(modules.Address(base+load.virtual_address+load.memory_size-1,&out)==1,"PT_LOAD last byte included");}
  const auto highest=std::max_element(original_metadata.loads.begin(),original_metadata.loads.end(),[](auto&a,auto&b){return a.virtual_address+a.memory_size<b.virtual_address+b.memory_size;});const auto end=base+highest->virtual_address+highest->memory_size;
  for(auto address:{addr_t(1),base-1,end,base+0x900000})for(int indirect:{0,1}){AndroidDlInfo out,before;std::memset(&out,0xa5,32);before=out;Run(address,&out,indirect,0);Check(!std::memcmp(&out,&before,32),"unknown/end/padding untouched exact32 bytes");if(address==1)std::printf("reference-%u unknown indirect=%d return=0 errno=731 untouched=32\n",fixture_index,indirect);}
  modules.Symbol(h,"missing");AndroidDlInfo out{};Check(modules.Address(base+SymbolValue(original_metadata,"fixture_function"),&out)==1&&modules.Address(1,nullptr)==0,"known and unknown do not consume dlerror");Check(std::strstr(reinterpret_cast<const char*>(modules.Error()),"unavailable")&&!modules.Error(),"dlerror slot preserved and clears normally");
  alignas(64)AndroidDlInfo tracked{};modules.Address(base+SymbolValue(original_metadata,"fixture_function"),&tracked);auto write=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked),8,[&]{Check(modules.Address(base+SymbolValue(original_metadata,"fixture_function"),&tracked)==1,"same-value query writes actual output");});Check(write.status==1,"tracked known32 write invalidates exclusive even same bytes");auto none=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked),8,[&]{Check(modules.Address(1,&tracked)==0,"unknown no write");});Check(none.status==0,"unknown preserves exclusive reservation");
  std::vector<std::thread>workers;for(unsigned n=0;n<4;++n)workers.emplace_back([&]{for(unsigned i=0;i<12;++i){AndroidDlInfo a{};Run(base+SymbolValue(original_metadata,"fixture_function"),&a,i&1,1);}});for(auto&t:workers)t.join();Check(modules.Close(h)==0&&!std::strcmp(stable,original_metadata.filename.c_str()),"owned metadata names stay stable after close until registry destruction");Check(modules.Address(base+SymbolValue(original_metadata,"fixture_function"),&out)==0,"unloaded image has no owner");Retire(raw);Retire(biased);
 }
 // Explicit, deliberately overlapping symbol metadata proves Bionic index order,
 // LOCAL inclusion, zero-size exclusion and forbidden resolver boundaries.
 Module m;m.name="ordered";ModuleAddressImage image;image.filename="/guest/lib/ordered.so";image.base=image.load_bias=0x72000000;image.span=0x4000;image.loads={{0,0x100},{0x2000,0x100}};image.symbols={{"zero",0x20,0,1,2},{"local-first",0x20,16,1,2},{"global-second",0x20,16,1,2},{"tls",0x40,8,1,6},{"ifunc",0x50,8,1,10}};m.address_image=image;modules.Add(std::move(m));auto h=modules.Open("ordered",1);AndroidDlInfo out{};Check(modules.Address(0x72000021,&out)==1&&!std::strcmp(reinterpret_cast<const char*>(out.symbol_name),"local-first"),"ordered first containing local symbol; zero-size excluded");Check(modules.Address(0x72000041,&out)==1&&!out.symbol_name,"TLS never address symbol");Check(!modules.Address(0x72000100,&out)&&!modules.Address(0x72001000,&out)&&!modules.Address(0x72002100,&out),"exact holes and endpoints never broad span owner");Reject([&]{modules.Address(0x72000051,&out);},"IFUNC");Reject([&]{modules.Address(0x72000021,nullptr);},"null output");Check(modules.Close(h)==0,"ordered module closed");
 auto bytes=Bytes(SYSV_LIBRARY);for(size_t n:{size_t(0),size_t(1),size_t(63),size_t(100)})Reject([&]{DescribeModuleElf(bytes.data(),n,0x76000000,"/bad");},"metadata");auto corrupt=bytes;corrupt[4]=1;Reject([&]{DescribeModuleElf(corrupt.data(),corrupt.size(),0x76000000,"/bad");},"header");Reject([&]{DescribeModuleElf(bytes.data(),bytes.size(),UINT64_MAX-4,"/bad");},"overflow");
 const auto phoff=At<uint64_t>(bytes,32);const auto phnum=At<uint16_t>(bytes,56);size_t first_load=0;for(unsigned i=0;i<phnum;++i)if(At<uint32_t>(bytes,phoff+i*56)==1){first_load=size_t(phoff+i*56);break;}Check(first_load!=0,"independently located actual PT_LOAD for corrupt bounds tests");
 for(size_t at:{size_t(32),first_load+8,first_load+32,first_load+40}){corrupt=bytes;uint64_t bad=UINT64_MAX;std::memcpy(corrupt.data()+at,&bad,8);Reject([&]{DescribeModuleElf(corrupt.data(),corrupt.size(),0x76000000,"/bad");},"metadata");}
 ModuleRegistry lifecycle([&](addr_t stage){AndroidDlInfo info{};Check(registry->Address(0x76000030,&info)==1,"dladdr available inside actual registry constructor/finalizer phase");Check(stage==1||stage==2,"real lifecycle callback value");});registry=&lifecycle;Module lm;lm.name="lifecycle";lm.initializers={1};lm.finalizers={2};auto lifeimage=image;lifeimage.base=lifeimage.load_bias=0x76000000;lm.address_image=std::move(lifeimage);lifecycle.Add(std::move(lm));auto lh=lifecycle.Open("lifecycle",1);Check(lh&&lifecycle.Close(lh)==0,"reentrant Address under existing recursive module lock");registry=&modules;
 // Actual original metadata plus both original absolute GOT relocations, no
 // original constructors, callbacks, functions or native ARM execution.
 auto original=Bytes(IL2CPP_LIBRARY);auto ilmeta=DescribeModuleElf(original.data(),original.size(),0x80000000,"/data/app/bunker/lib/arm64/libil2cpp.so");Module il;il.name="libil2cpp.so";il.address_image=ilmeta;il.export_policy=Module::ExportPolicy::BionicRawSymbols;il.exports={{"end",0x7cb1e78}};modules.Add(std::move(il));auto ih=modules.Open("libil2cpp.so",1);Check(modules.Symbol(ih,"end")==0x87cb1e78,"original Android ABS end resolved with bias");AndroidDlInfo sentinel,before;std::memset(&sentinel,0xa5,32);before=sentinel;Check(!modules.Address(0x7cb1e78,&sentinel)&&!modules.Address(0x87cb1e78,&sentinel)&&!std::memcmp(&sentinel,&before,32),"both original raw and Bionic end outside exact PT_LOAD");elf_image actual{};Check(!elf_load_bionic(IL2CPP_LIBRARY,0x80000000,Resolve,&actual),"original IL2CPP data-only Bionic relocation");uint64_t first,second;std::memcpy(&first,actual.base+0x72aeb08,8);std::memcpy(&second,actual.base+0x73f9770,8);Check(first==0x87cb1e78&&second==0x85408660,"both original actual SHN_ABS GLOB_DAT slots use Bionic bias");Check(modules.Close(ih)==0,"data-only original module closes without guest lifecycle");Retire(actual);
 auto unitybytes=Bytes(UNITY_LIBRARY);auto unity=DescribeModuleElf(unitybytes.data(),unitybytes.size(),0x70000000,"/data/app/bunker/lib/arm64/libunity.so");Module um;um.name="libunity.so";um.address_image=unity;um.export_policy=Module::ExportPolicy::BionicRawSymbols;um.exports={{"libunity",0}};modules.Add(std::move(um));auto uh=modules.Open("libunity.so",1);Check(uh&&modules.Symbol(uh,"libunity")==0x70000000,"actual Unity metadata and Bionic zero ABS export");AndroidDlInfo uinfo{};Check(modules.Address(0x70432cfc,&uinfo)==1&&!std::strcmp(reinterpret_cast<const char*>(uinfo.filename),"/data/app/bunker/lib/arm64/libunity.so"),"actual Unity predicate address has correct canonical slash filename");Check(modules.Close(uh)==0,"original Unity metadata-only closes without guest execution");
 Retire(caller);std::printf("DLADDR-SUCCESS checks=%u actual-NDK-calls=%u real-ELF-SysV-GNU/ABI/epochs/lifetime/ABS-relocations/original-data-only\n",checks.load(),calls.load());return 0;
}

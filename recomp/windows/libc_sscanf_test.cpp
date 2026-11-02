#include "libc.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "old_markers.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <stdexcept>
#include <thread>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif
namespace {
std::atomic<unsigned> checks{0},calls{0},errors_set{0};
bunker::windows::LibC *provider;
thread_local int32_t guest_error;
thread_local int32_t expected_count;
thread_local addr_t expected_output;
constexpr addr_t kErrno=0x7ffc00000000ULL,kScan=0x7ffc00000008ULL;
void Check(bool v,const char*w){if(!v){std::fprintf(stderr,"sscanf check failed: %s\n",w);std::abort();}++checks;}
void*Resolve(const char*n){if(!std::strcmp(n,"__errno"))return reinterpret_cast<void*>(kErrno);if(!std::strcmp(n,"sscanf"))return reinterpret_cast<void*>(kScan);return reinterpret_cast<void*>(provider->Marker(n));}
struct Case {const char*name;std::string text;int count;uint64_t value;bool overflow=false;};
constexpr uint64_t kSentinel=UINT64_C(0xa5a5a5a5a5a5a5a5);
struct Guard {uint64_t before=0x123456789abcdef0ULL,value=kSentinel,after=0xfedcba9876543210ULL;};
}
int main(int argc,char**argv){
#ifdef _WIN32
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
 bunker::windows::LibC libc;provider=&libc;libc.SetErrorSink([](int e){++errors_set;recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&e,4);});
 recomp::Runtime runtime;libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
 runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
 runtime.AddImport(kScan,[&](State&s){
  Check(s.gpr.x2.qword==expected_output,"actual NDK sscanf puts output in X2");
  auto x1=s.gpr.x1.qword,x2=s.gpr.x2.qword,x3=s.gpr.x3.qword;
  runtime.Dispatch(s,libc.Marker("sscanf"),nullptr);++calls;
  Check(s.gpr.x0.qword==uint32_t(expected_count),"installed typed bridge returns exact W0 bits and clears upper X0");
  Check(s.gpr.x1.qword==x1&&s.gpr.x2.qword==x2&&s.gpr.x3.qword==x3,"fixed bridge preserves other argument registers");
 });
 elf_image image{};Check(!elf_load(SSCANF_LIBRARY,0x5a000000,Resolve,&image),"actual NDK sscanf fixture loads");
 for(size_t i=0;i<std::size(kOldMarkers);++i)Check(libc.Marker(kOldMarkers[i])==0x7ffb00000000ULL+i*8,"all accepted old markers retain exact identity including free");
 Check(libc.Marker("sscanf")==libc.Marker("getpid")+8,"sscanf marker appends after getpid");
 auto Run=[&](const char*input,const char*format,uint64_t*output,int indirect,int sentinel,int count){
  alignas(16)std::array<uint8_t,65536>stack{};State s{};int error=-1;expected_count=count;expected_output=reinterpret_cast<addr_t>(output);
  s.gpr.x0.qword=reinterpret_cast<addr_t>(input);s.gpr.x1.qword=reinterpret_cast<addr_t>(format);s.gpr.x2.qword=reinterpret_cast<addr_t>(output);
  s.gpr.x3.dword=indirect;s.gpr.x4.dword=sentinel;s.gpr.x5.qword=reinterpret_cast<addr_t>(&error);
  s.gpr.x19.qword=0x123456789abcdef0ULL;s.gpr.x29.qword=0x1122334455667788ULL;
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
  runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_sscanf")));
  Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK preserves PC/SP");
  Check(s.gpr.x19.qword==0x123456789abcdef0ULL&&s.gpr.x29.qword==0x1122334455667788ULL,"NDK preserves callee-saved registers");
  Check(s.gpr.x0.qword==static_cast<uint64_t>(static_cast<int64_t>(count)),"NDK signed32 count sign-extends to int64 including EOF");
  Check(error==guest_error,"NDK reads actual guest errno after the call");return error;
 };
 if(argc>1){
  const std::string which=argv[1];Guard out;
  const char*format=which=="unsupported-int"?"%d":which=="unsupported-width"?"%20llu":which=="unsupported-tail"?"%llu ":"%llu%llu";
  Run("17",format,&out.value,1,123,1);return 2;
 }
 const std::vector<Case>cases={{"empty","",-1,kSentinel},{"space"," \t\n\r\v\f",-1,kSentinel},{"letter","x",0,kSentinel},{"plus","+",0,kSentinel},{"minus","-",0,kSentinel},{"plusspace","+ ",0,kSentinel},{"spacesign"," \t-",0,kSentinel},{"doubleplus","++1",0,kSentinel},{"minusplus","-+1",0,kSentinel},{"highbyte",std::string(1,char(0xa0))+"1",0,kSentinel},{"zero","0",1,0},{"leading"," \t\r\n\v\f42tail",1,42},{"hexdecimal","0x10",1,0},{"octdecimal","077",1,77},{"negative","-1",1,UINT64_MAX},{"max","18446744073709551615",1,UINT64_MAX},{"over","18446744073709551616",1,UINT64_MAX,true},{"negmax","-18446744073709551615",1,1},{"negover","-18446744073709551616",1,UINT64_MAX,true},{"builddate","638477124699603280",1,638477124699603280ULL},{"512zero1",std::string(512,'0')+"1",1,0},{"511zero1",std::string(511,'0')+"1",1,1},{"sign511zero1","+"+std::string(511,'0')+"1",1,0},{"sign510zero1","+"+std::string(510,'0')+"1",1,1},{"512nine",std::string(512,'9'),1,UINT64_MAX,true},{"space512zero1",std::string(600,' ')+std::string(512,'0')+"1",1,0},{"negativezero","-0",1,0},{"embeddedNUL",std::string("17\0notnumber",12),1,17}};
 for(int indirect=0;indirect<2;++indirect)for(const auto&t:cases){
  Guard out;auto before=errors_set.load();int err=Run(t.text.c_str(),"%llu",&out.value,indirect,123,t.count);
  Check(err==(t.overflow?34:123),"Bionic errno preserved except actual magnitude overflow");
  Check(out.value==t.value,"Bionic exact unsigned value/failure preservation/512 character token");
  Check(out.before==0x123456789abcdef0ULL&&out.after==0xfedcba9876543210ULL,"one eight-byte assignment leaves both canaries unchanged");
  Check(errors_set.load()==before+unsigned(t.overflow),"overflow is the sole error-sink publication");
 }
 for(const char*bad:{"", " ","+","-x"}){Check(Run(bad,"%llu",nullptr,1,177,*bad&&std::strcmp(bad," ")?0:-1)==177,"failed conversion does not dereference null output");}
 uint64_t value=17;
 auto written=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&value),8,[&]{Check(libc.ScanUnsignedLongLong("17","%llu",&value)==1,"same-value direct assignment count");});
 Check(written.status==1&&value==17,"same-value assignment invalidates real exclusive reservation via tracked output");
 auto untouched=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&value),8,[&]{Check(libc.ScanUnsignedLongLong("x","%llu",&value)==0,"mismatch direct count");});
 Check(untouched.status==0&&value==17,"mismatch publishes no output write or epoch invalidation");
 for(unsigned offset:{0u,4u,8u,16u}){
  alignas(8)std::array<unsigned char,64>bytes;bytes.fill(0xa5);std::memcpy(bytes.data()+8,"123456789012345",16);auto before=bytes;
  auto output=reinterpret_cast<uint64_t*>(bytes.data()+offset);Check(Run(reinterpret_cast<char*>(bytes.data()+8),"%llu",output,offset&1,123,1)==123,"input/output alias preserves errno");
  uint64_t parsed;std::memcpy(&parsed,output,8);Check(parsed==123456789012345ULL,"snapshots finish input parsing before overlapping assignment");
  for(size_t i=0;i<bytes.size();++i)if(i<offset||i>=offset+8)Check(bytes[i]==before[i],"alias changes only exact output bytes");
 }
 alignas(8)std::array<unsigned char,32>unaligned;unaligned.fill(0xa5);Run("42","%llu",reinterpret_cast<uint64_t*>(unaligned.data()+3),1,123,1);uint64_t parsed;std::memcpy(&parsed,unaligned.data()+3,8);Check(parsed==42&&unaligned[2]==0xa5&&unaligned[11]==0xa5,"unaligned output is a tracked eight-byte copy");
 uint64_t seed=0x243f6a8885a308d3ULL;
 for(unsigned i=0;i<128;++i){seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;auto text=std::string(i&1?"-":"+")+std::to_string(seed)+"tail";Guard out;Run(text.c_str(),"%llu",&out.value,i&1,199,1);Check(out.value==(i&1?uint64_t(0)-seed:seed),"random full64 decimal values and modulo negatives are not truncated");}
 std::vector<std::thread>threads;for(unsigned n=0;n<4;++n)threads.emplace_back([&,n]{for(unsigned i=0;i<8;++i){Guard out;Check(Run("638477124699603280","%llu",&out.value,i&1,210+n,1)==int(210+n)&&out.value==638477124699603280ULL,"concurrent actual NDK calls preserve thread errno and values");}});for(auto&t:threads)t.join();
 bool rejected=false;try{libc.ScanUnsignedLongLong("17","%u",&value);}catch(const std::runtime_error&e){rejected=std::strstr(e.what(),"exact %llu profile");}Check(rejected,"direct unsupported format throws named boundary");
 std::printf("sscanf exact %%llu: %u checks passed; %u actual NDK direct/indirect calls, Bionic counts/errno/token cap, tracked eight-byte output, aliases, ABI and threads\n",checks.load(),calls.load());
}

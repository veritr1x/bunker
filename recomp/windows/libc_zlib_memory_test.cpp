#include "libc.h"
#include "zlib_host.h"
#include "provider_memory.h"
#include <zlib.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <thread>

namespace pm=bunker::windows::provider_memory;
static unsigned checks;
static void check(bool condition,const char*why){++checks;if(!condition){std::fprintf(stderr,"provider memory check failed: %s\n",why);std::exit(1);}}
static thread_local const std::function<void(State&)> *body;
static Memory *trace(State&s,addr_t,Memory*m){(*body)(s);s.gpr.pc.qword=s.gpr.x30.qword;return m;}
alignas(64) static unsigned char bytes[512];
alignas(64) static unsigned char compressed[]={120,156,115,116,28,217,0,0,163,96,65,1};
alignas(64) static unsigned char inflated[512];
static void *pointer(uint64_t value){return reinterpret_cast<void*>(value);}

int main(){
  recomp::Runtime runtime;
  recomp::Trace entries[]={{0x1000,trace}};runtime.AddTraces(entries,1);
  bunker::windows::LibC libc;libc.Install(runtime);
  bunker::windows::Zlib zlib;zlib.Install(runtime);
  auto call=[&](addr_t entry,std::initializer_list<uint64_t>args){
    State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t i=0;
    for(auto arg:args)(s.gpr.*regs[i++]).qword=arg;runtime.Run(s,entry);return s;
  };
  auto imported=[&](const char*name,std::initializer_list<uint64_t>args){return call(libc.Marker(name),args);};
  auto reserve=[&](void *p,unsigned size,const std::function<void()>&write,bool invalidated,const char *why){
    std::function<void(State&)> test=[&](State&s){
      uint64_t old=__remill_aarch64_load_exclusive(s,pm::Address(p),size,0);
      std::thread writer(write);writer.join();
      check(__remill_aarch64_store_exclusive(s,pm::Address(p),old,size,0)==uint32_t(invalidated),why);
    };
    body=&test;State s{};runtime.Run(s,0x1000);body=nullptr;
  };
  unsigned char source[128];std::memset(source,'A',sizeof(source));
  for(const char*name:{"memcpy","memmove"}){
    pm::Fill(bytes,'A',sizeof(bytes));
    reserve(bytes+192,8,[&]{imported(name,{pm::Address(bytes+128),pm::Address(source),128});},true,"same-value memory copy invalidates deep destination reservation");
  }
  pm::Fill(bytes,'A',sizeof(bytes));
  reserve(bytes+192,8,[&]{imported("memset",{pm::Address(bytes+128),'A',128});},true,"same-value memset invalidates");
  pm::Fill(bytes,'A',sizeof(bytes));
  reserve(bytes+192,8,[&]{imported("memmove",{pm::Address(bytes+129),pm::Address(bytes+128),128});},true,"overlap copy invalidates");
  for(const char*name:{"strcpy","strncpy","strlcpy","strxfrm"}){
    pm::Fill(bytes,0,sizeof(bytes));pm::Write(bytes,static_cast<unsigned char>('A'));
    reserve(bytes,1,[&]{imported(name,{pm::Address(bytes),pm::Address("A"),128});},true,"same-value string output invalidates");
  }
  for(const char*name:{"strcat","strncat"}){
    pm::Fill(bytes,0,sizeof(bytes));pm::Write(bytes,static_cast<unsigned char>('A'));
    reserve(bytes+1,1,[&]{imported(name,{pm::Address(bytes),pm::Address(""),0});},true,"string append terminator is tracked");
  }
  char *save=reinterpret_cast<char*>(bytes);pm::Fill(bytes,0,sizeof(bytes));
  reserve(&save,8,[&]{imported("strtok_r",{0,pm::Address(","),pm::Address(&save)});},true,"same-value tokenizer save pointer tracked");
  pm::Fill(bytes,0,sizeof(bytes));recomp::WriteGuestMemory(pm::Address(bytes),"ABC",4);
  reserve(bytes,1,[&]{imported("strlen",{pm::Address(bytes)});},false,"tracked string snapshot does not invalidate read source");
  reserve(bytes,1,[&]{imported("strncpy",{pm::Address(bytes),0,0});},false,"zero-length string copy neither reads null source nor invalidates destination");
  const char *number="123";alignas(64) char *end=const_cast<char*>(number+3);
  reserve(&end,8,[&]{imported("strtol",{pm::Address(number),pm::Address(&end),10});},true,"parse end-pointer ABA invalidated");
  const char *decimal="1.25";end=const_cast<char*>(decimal+4);
  reserve(&end,8,[&]{imported("strtod",{pm::Address(decimal),pm::Address(&end)});},true,"floating parse end pointer tracked");
  alignas(64) int32_t error=34;
  libc.SetErrorSink([&](int value){pm::Write(&error,int32_t(value));});
  reserve(&error,4,[&]{libc.ParseInteger("184467440737095516160",nullptr,10,false);},true,"errno sink may safely publish under tracking");
  alignas(64) double integral=2.0;
  reserve(&integral,8,[&]{State s{};double input=2.25;std::memcpy(&s.simd.v[0],&input,8);s.gpr.x0.qword=pm::Address(&integral);runtime.Run(s,libc.Marker("modf"));},true,"same-value modf integral tracked");
  alignas(64) float integral32=3.0f;
  reserve(&integral32,4,[&]{State s{};float input=3.5f;std::memcpy(&s.simd.v[0],&input,4);s.gpr.x0.qword=pm::Address(&integral32);runtime.Run(s,libc.Marker("modff"));},true,"same-value modff integral tracked");
  alignas(64) int32_t exponent=4;
  reserve(&exponent,4,[&]{State s{};float input=12.0f;std::memcpy(&s.simd.v[0],&input,4);s.gpr.x0.qword=pm::Address(&exponent);runtime.Run(s,libc.Marker("frexpf"));},true,"same-value frexp exponent tracked");
  alignas(64) void *aligned=nullptr;
  reserve(&aligned,8,[&]{void *old=aligned;libc.PosixMemalign(&aligned,64,31);libc.Free(aligned);std::memcpy(&aligned,&old,8);},true,"posix output pointer ABA invalidated");
  reserve(&aligned,8,[&]{check(libc.PosixMemalign(&aligned,3,31)==22,"invalid posix alignment status");},false,"failed posix allocation leaves output untouched");
  for(bool overalign:{false,true}){
    auto allocation=static_cast<unsigned char*>(overalign?libc.Memalign(256,1024):libc.Malloc(1024));
    pm::Fill(allocation,0x37,1024);
    reserve(allocation+768,8,[&]{libc.Free(allocation);},true,"free invalidates full allocation beyond first granule");
  }
  auto external=static_cast<unsigned char*>(std::malloc(1024));pm::Fill(external,0x37,1024);
  reserve(external+768,8,[&]{libc.Free(external);},true,"external CRT/logging allocation full lifetime invalidated");
  auto allocation=static_cast<unsigned char*>(libc.Malloc(1024));pm::Fill(allocation,0x37,1024);void *resized=nullptr;
  reserve(allocation+768,8,[&]{resized=libc.Realloc(allocation,128);},true,"realloc invalidates entire old lifetime including truncated tail");check(resized,"realloc succeeded");libc.Free(resized);
  // Intentionally bypass tracked free, then demand fresh allocation invalidation
  // when CRT reuses exactly the old address. Restore bytes raw to make this ABA.
  auto old=static_cast<unsigned char*>(std::malloc(512));pm::Fill(old,0x41,512);std::vector<void*> held;void *reused=nullptr;
  reserve(old+384,8,[&]{
    std::free(old);
    for(unsigned i=0;i<4096;++i){auto next=libc.Malloc(512);check(next,"reuse allocation succeeded");if(next==old){reused=next;break;}held.push_back(next);}
    check(reused,"CRT reused address for deterministic freshness gate");uint64_t same=UINT64_C(0x4141414141414141);std::memcpy(static_cast<unsigned char*>(reused)+384,&same,8);
  },true,"fresh allocation invalidates reused address even if freed outside provider");
  libc.Free(reused);for(auto p:held)libc.Free(p);
  libc.SetEnvironment({{"KEY","old"}});auto old_value=libc.Getenv("KEY");
  reserve(old_value,1,[&]{libc.SetEnvironment({{"KEY","new"}});},true,"environment value lifetime tracked");
  auto environment_slot=pointer(libc.Marker("environ"));
  char **previous_environment=pm::Read(static_cast<char***>(environment_slot)),**published_environment=nullptr;
  reserve(environment_slot,8,[&]{libc.SetEnvironment({{"KEY","again"}});published_environment=pm::Read(static_cast<char***>(environment_slot));std::memcpy(environment_slot,&previous_environment,8);},true,"environment data-slot publication ABA tracked");
  pm::Write(static_cast<char***>(environment_slot),published_environment);

  auto setup=[&](bunker::windows::Zlib &host,bunker::windows::AndroidZStream &stream){
    stream={};check(host.Init(&stream,15,host.Version(),112)==Z_OK,"zlib setup");
    stream.next_in=pm::Address(compressed);stream.avail_in=sizeof(compressed);stream.next_out=pm::Address(inflated);stream.avail_out=256;pm::Fill(inflated,'A',sizeof(inflated));
  };
  alignas(64) bunker::windows::AndroidZStream stream{};setup(zlib,stream);
  reserve(inflated+128,8,[&]{check(zlib.Inflate(&stream,Z_NO_FLUSH)==Z_STREAM_END,"decompression reached end");},true,"same-value decompression output tracked");
  check(zlib.End(&stream)==Z_OK,"end decompression");setup(zlib,stream);
  reserve(const_cast<unsigned char*>(compressed),1,[&]{zlib.Inflate(&stream,Z_NO_FLUSH);},false,"zlib snapshots never write guest input");zlib.End(&stream);
  stream={};stream.zalloc=0;stream.zfree=0;
  reserve(&stream.total_in,8,[&]{zlib.Init(&stream,15,zlib.Version(),112);},true,"same-value zlib wire initialization tracked");zlib.End(&stream);
  setup(zlib,stream);stream.total_in=sizeof(compressed);
  reserve(&stream.total_in,8,[&]{stream.total_in=0;zlib.Inflate(&stream,Z_NO_FLUSH);},true,"zlib wire counter publication tracked");zlib.End(&stream);
  setup(zlib,stream);auto state_address=stream.state;
  reserve(&stream.state,8,[&]{zlib.End(&stream);std::memcpy(&stream.state,&state_address,8);},true,"zlib end state-pointer ABA tracked");stream.state=0;
  std::vector<std::pair<void*,size_t>> custom_blocks;
  bunker::windows::Zlib callbacks([&](addr_t callback,const std::vector<addr_t>&args)->uint64_t{
    // These operations take the memory lock; a lock across callbacks deadlocks.
    if(callback==0x1111){auto p=libc.Calloc(args[1],args[2]);custom_blocks.push_back({p,size_t(args[1]*args[2])});return pm::Address(p);}
    check(callback==0x2222,"custom free callback address");libc.Free(pointer(args[1]));return 0;
  });
  stream={};stream.zalloc=0x1111;stream.zfree=0x2222;check(callbacks.Init(&stream,15,callbacks.Version(),112)==Z_OK,"mirrored custom stream setup");
  auto custom=static_cast<unsigned char*>(custom_blocks[0].first);check(custom_blocks[0].second>512,"custom state size supports deep reservation");
  uint64_t before=pm::Read(reinterpret_cast<uint64_t*>(custom+256));
  stream.next_in=pm::Address(compressed);stream.avail_in=sizeof(compressed);stream.next_out=pm::Address(inflated);stream.avail_out=256;
  reserve(custom+256,8,[&]{check(callbacks.Inflate(&stream,Z_NO_FLUSH)==Z_STREAM_END,"custom stream output");std::memcpy(custom+256,&before,8);},true,"custom allocator mirror publication ABA tracked");
  reserve(custom+512,8,[&]{callbacks.End(&stream);},true,"custom allocator free lifetime tracked across callback");
  std::printf("LibC/zlib tracked provider memory: %u checks passed.\n",checks);
}

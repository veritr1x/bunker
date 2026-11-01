#include "zlib_host.h"
#include "libc.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "zlib_driver.h"
#include <memory>
static bunker::windows::Zlib *zlib_provider;
static bunker::windows::LibC *libc_provider;
static recomp::Runtime runtime;
static addr_t entry;
static void *resolve(const char *name){
  try{return reinterpret_cast<void*>(zlib_provider->Marker(name));}catch(...){}
  try{return reinterpret_cast<void*>(libc_provider->Marker(name));}catch(...){}
  std::fprintf(stderr,"missing zlib fixture import %s\n",name);return nullptr;
}
static uint64_t run(addr_t address,const std::vector<addr_t>&args){
  auto stack=std::make_unique<uint8_t[]>(1<<20);State s{};
  Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};
  for(size_t i=0;i<args.size();++i)(s.gpr.*registers[i]).qword=args[i];
  s.gpr.sp.qword=(reinterpret_cast<addr_t>(stack.get())+(1<<20))&~addr_t(15);s.gpr.x30.qword=0xfeedffff;
  auto sp=s.gpr.sp.qword;runtime.Run(s,address);
  if(s.gpr.pc.qword!=0xfeedffff||s.gpr.sp.qword!=sp)std::abort();return s.gpr.x0.qword;
}
static int call(ZlibFixture*f){return static_cast<int32_t>(run(entry,{reinterpret_cast<addr_t>(f)}));}
int main(){
  bunker::windows::Zlib zlib(run);zlib_provider=&zlib;
  bunker::windows::LibC libc(run);libc_provider=&libc;zlib.Install(runtime);libc.Install(runtime);
  runtime.AddTraces(kTraces,sizeof(kTraces)/sizeof(*kTraces));elf_image image;
  if(elf_load(ZLIB_LIBRARY,0x63000000,resolve,&image))return 1;
  entry=reinterpret_cast<addr_t>(elf_symbol(&image,"guest_inflate"));if(!entry)std::abort();
  return run_zlib_cases(call);
}

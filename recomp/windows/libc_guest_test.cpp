#include "libc.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
static bunker::windows::LibC *provider;
static int32_t guest_errno;
static uint64_t dso;
static void *resolve(const char *name){
  if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffc00000000ULL);
  if(!std::strcmp(name,"__dso_handle"))return &dso;
  try{return reinterpret_cast<void*>(provider->Marker(name));}catch(...){std::fprintf(stderr,"unresolved fixture import %s\n",name);return nullptr;}
}
int main(){
  recomp::Runtime runtime;
  auto run=[&](addr_t entry,const std::vector<addr_t>&args){
    auto stack=std::make_unique<uint8_t[]>(1<<18);State state{};
    Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};
    for(size_t i=0;i<args.size();++i)(state.gpr.*registers[i]).qword=args[i];
    state.gpr.sp.qword=(reinterpret_cast<addr_t>(stack.get())+(1<<18))&~addr_t(15);state.gpr.x30.qword=0xfeedffff;
    auto initial_sp=state.gpr.sp.qword;runtime.Run(state,entry);
    if(state.gpr.pc.qword!=0xfeedffff||state.gpr.sp.qword!=initial_sp)std::abort();return state.gpr.x0.qword;
  };
  bunker::windows::LibC libc(run);provider=&libc;libc.SetErrorSink([](int e){guest_errno=e;});libc.SetEnvironment({{"BUNKER_TEST","configured"}});
  libc.Install(runtime);runtime.AddImport(0x7ffc00000000ULL,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_errno);});
  runtime.AddTraces(kTraces,sizeof(kTraces)/sizeof(*kTraces));elf_image image;
  if(elf_load(LIBC_LIBRARY,0x62000000,resolve,&image))return 1;
  uint64_t order[16]{};unsigned checks=0;
  for(const char*name:{"guest_allocators","guest_strings","guest_parsing","guest_math","guest_lifecycle","guest_environment"}){
    auto address=reinterpret_cast<addr_t>(elf_symbol(&image,name));if(!address)std::abort();
    auto result=static_cast<int32_t>(run(address,std::strcmp(name,"guest_lifecycle")==0?std::vector<addr_t>{reinterpret_cast<addr_t>(order)}:std::vector<addr_t>{}));
    if(result){std::fprintf(stderr,"NDK libc fixture %s failed line %d\n",name,result);return 1;}++checks;
  }
  std::printf("Translated Android NDK libc: %u startup gates passed, including reentrant translated destructors.\n",checks);
}

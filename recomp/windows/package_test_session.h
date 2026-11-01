#pragma once
#include "android_context.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "sample.h"
#include <array>
#include <cstdio>
#include <climits>
#include <stdexcept>
#include <thread>
struct Session {
  recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};elf_image &image;
  explicit Session(elf_image &i):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));}
  addr_t call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
  addr_t find(const char *name){return call(6,reinterpret_cast<addr_t>(name));}
  addr_t method(const char *owner,const char *name,const char *sig){return call(33,find(owner),reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig));}
  addr_t field(const char *owner,const char *name,const char *sig,bool stat=false){return call(stat?144:94,find(owner),reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig));}
  addr_t run(const char *name,std::initializer_list<addr_t> args){alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6};size_t i=0;for(auto a:args)(s.gpr.*regs[i++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));if(s.gpr.sp.qword!=reinterpret_cast<addr_t>(stack.data()+stack.size())||s.gpr.pc.qword!=0xfeedffff)throw std::runtime_error("NDK package caller PC/SP changed");return s.gpr.x0.qword;}
  addr_t zero(addr_t o,addr_t m,addr_t mode){return run("package_zero",{host.EnvAddress(),o,m,mode});}
  addr_t one(addr_t o,addr_t m,addr_t n,addr_t mode){return run("package_one",{host.EnvAddress(),o,m,n,mode});}
  addr_t two(addr_t o,addr_t m,addr_t n,int32_t flags,addr_t mode){return run("package_two",{host.EnvAddress(),o,m,n,static_cast<uint32_t>(flags),mode});}
  addr_t construct(addr_t c,addr_t m,addr_t a,addr_t mode){return run("package_construct",{host.EnvAddress(),c,m,a,mode});}
  addr_t integer(addr_t o,addr_t m,int32_t a,addr_t mode){return run("package_integer",{host.EnvAddress(),o,m,static_cast<uint32_t>(a),mode});}
  bool empty(addr_t o,addr_t m,addr_t mode){return run("package_empty",{host.EnvAddress(),o,m,mode})!=0;}
  addr_t get(addr_t o,addr_t f){return run("package_field",{host.EnvAddress(),o,f});}
  std::u16string text(addr_t ref){auto value=host.StringValue(ref);if(!value)throw std::runtime_error("expected String");return *value;}
};

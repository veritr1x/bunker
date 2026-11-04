#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "st3_records.h"
#include <array>
#include <cstring>
#include <stdexcept>
#include <string>
static recomp::Runtime runtime;static elf_image image;alignas(16)static uint8_t stack[65536];
static void require(bool x,const char*why){if(!x)throw std::runtime_error(why);}
static void call(unsigned n,uint8_t*out,const uint8_t*in,uint8_t*memory,uint64_t step){State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(in);s.gpr.x2.qword=reinterpret_cast<addr_t>(memory);s.gpr.x3.qword=step;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;s.sr.tpidr_el0.qword=0x123456789;auto flags=get64(in+736);s.nzcv.flat=flags;s.sr.n=flags>>31&1;s.sr.z=flags>>30&1;s.sr.c=flags>>29&1;s.sr.v=flags>>28&1;auto sp=s.gpr.sp.qword;auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,cases[n].name));require(entry!=0,"core export");runtime.Run(s,entry);require(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==sp,"normal PC/SP and real stack restore");}
int main(){try{if(elf_load(ST3_LIB,0x38000000,nullptr,&image))return 1;runtime.AddTraces(kTraces,std::size(kTraces));
 for(unsigned n=0;n<CASE_COUNT;++n){const auto*c=&cases[n];State s{};for(unsigned r=0;r<32;++r)for(unsigned j=0;j<16;++j)reinterpret_cast<uint8_t*>(&s.simd.v[r])[j]=uint8_t(r*29+j*11+1);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;alignas(16)std::array<uint8_t,192>memory;memory.fill(0xcd);auto expected_memory=memory;auto base=reinterpret_cast<addr_t>(memory.data()+64);auto*regs=&s.gpr.x0;memcpy(reinterpret_cast<uint8_t*>(regs)+16*c->rn,&base,8);if(c->mode==2&&c->rm!=c->rn){uint64_t step=7;memcpy(reinterpret_cast<uint8_t*>(regs)+16*c->rm,&step,8);}auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,(std::string("raw_")+c->name).c_str()));require(entry!=0,"raw actual ST3 export");s.gpr.pc.qword=entry;State expected=s;uint64_t increment=c->mode==1?3*c->width:c->mode==2?(c->rm==c->rn?base:7):0;auto next=base+increment;memcpy(reinterpret_cast<uint8_t*>(&expected.gpr.x0)+16*c->rn,&next,8);expected.gpr.pc.qword=0xfeedffff;memory_oracle(expected_memory.data(),reinterpret_cast<uint8_t*>(&s.simd),c,64);alignas(16)std::array<uint8_t,64>token;token.fill(0x6d);auto oldtoken=token;auto*opaque=reinterpret_cast<Memory*>(token.data());require(runtime.Run(s,entry,opaque)==opaque&&token==oldtoken,"tracked stores preserve opaque token bytes");require(!memcmp(&s,&expected,sizeof(s)),"raw ST3/RET full1200State exact");require(memory==expected_memory,"raw real tracked interleaving/canaries");}
 int r=run_st3_records(call);if(r){fprintf(stderr,"ST3 host error %d\n",r);return r;}puts("ST3-HOST-SUCCESS raw_full1200=72");return 0;
 }catch(const std::exception&e){fprintf(stderr,"ST3 fixture: %s\n",e.what());return 1;}}

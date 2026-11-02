#include "filesystem.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <windows.h>
using bunker::windows::FileSystem;using namespace bunker::windows::linux_flags;
namespace {
unsigned checks=0;FileSystem*active;
void Check(bool p,const char*why){if(!p)throw std::runtime_error(why);++checks;}
void*Resolve(const char*n){return reinterpret_cast<void*>(active->Marker(n));}
bool Boundary(const std::function<void()>&f){try{f();}catch(const std::runtime_error&e){return std::string(e.what())=="unsupported mmap MAP_GROWSDOWN: owned downward expansion is not implemented";}return false;}
addr_t Call(recomp::Runtime&r,elf_image&i,const char*n,std::initializer_list<addr_t>args={}){alignas(16)std::array<uint8_t,65536>stack{};State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t at=0;for(auto a:args)(s.gpr.*regs[at++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;r.Run(s,reinterpret_cast<addr_t>(elf_symbol(&i,n)));Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"actual NDK malformed caller preserves PC/SP");return s.gpr.x0.qword;}
}
int main(int argc,char**argv){FileSystem f;active=&f;recomp::Runtime runtime;f.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));elf_image image{};Check(!elf_load(GROWDOWN_IMAGE,0x7a000000,Resolve,&image),"strict NDK original-flags ELF loaded");if(argc>1){Call(runtime,image,std::string(argv[1])=="--guest-zero-noreplace"?"growdown_zero_noreplace":"growdown_original");throw std::runtime_error("valid growth call silently returned");}
 Check(map_growdown==0x100,"recognized constant is exact ARM64 NDK value");
 auto before=f.Mmap(0,8192,3,map_private|map_anonymous,-1,0);Check(before!=UINT64_MAX,"ordinary anonymous mapping still works");const auto generation=f.MappingRegion(before,8192,true)->generation;*reinterpret_cast<uint64_t*>(before)=0x123456789abcdef0ULL;
 auto hole=VirtualAlloc(nullptr,0x40000,MEM_RESERVE,PAGE_NOACCESS);Check(hole&&VirtualFree(hole,0,MEM_RELEASE),"owned test address is genuinely free before rejected allocation");const auto address=reinterpret_cast<addr_t>(hole);MEMORY_BASIC_INFORMATION old{},now{};Check(VirtualQuery(hole,&old,sizeof(old))&&old.State==MEM_FREE,"native candidate starts free");
 for(int flags:{0x20122,0x122,0x120122,0x20132}){f.SetError(71);Check(Boundary([&]{f.Mmap(address,0x40000,3,flags,-1,0);}),"valid private anonymous growth has named capability boundary");Check(f.Error()==71&&!f.MappingRegion(address,1,false)&&!f.AcquireMappingUse(address,1,false),"unsupported valid growth neither mutates errno nor publishes owner/lease");Check(VirtualQuery(hole,&now,sizeof(now))&&now.State==MEM_FREE&&now.BaseAddress==old.BaseAddress&&now.RegionSize==old.RegionSize,"unsupported valid growth performs no native allocation/reservation");}
 f.SetError(71);Check(Boundary([&]{f.Mmap(0,8192,3,0x20122,-1,4096);})&&f.Error()==71,"valid aligned anonymous offset still reaches capability boundary without fake errno");
 auto after=f.Mmap(address,0x40000,3,map_private|map_anonymous|map_fixed_no_replace,-1,0);Check(after==address,"ordinary exact-address allocation succeeds after growth rejection");Check(f.MappingRegion(after,0x40000,true)->generation==generation+1,"rejected growth consumes no mapping generation");
 // Start the reservation helper's real native thread only after checking the
 // free address: Windows itself may reuse/cache that address for a new stack.
 auto reservation=bunker::test::ReserveAcrossOperation(before,8,[&]{if(!Boundary([&]{f.Mmap(0,8192,3,0x20122,-1,0);}))throw std::runtime_error("growth boundary missing");});Check(reservation.status==0&&*reinterpret_cast<uint64_t*>(before)==0x123456789abcdef0ULL,"rejected growth performs no tracked memory/epoch write to live guest data");Check(!f.Munmap(after,0x40000)&&!f.Munmap(before,8192),"ordinary owners release normally");
 struct Case{uint64_t size;int prot,flags;int64_t offset;};
 for(const auto&c:std::array<Case,9>{{{0,3,0x20122,0},{UINT64_MAX,3,0x20122,0},{8192,8,0x20122,0},{8192,3,0x20120,0},{8192,3,0x20123,0},{8192,3,0x420122,0},{8192,3,0x20122,-4096},{8192,3,0x20122,1},{8192,3,0x20121,0}}}){f.SetError(71);Check(f.Mmap(0,c.size,c.prot,c.flags,-1,c.offset)==UINT64_MAX&&f.Error()==22,"malformed length/protection/type/flags/offset or invalid shared growth preserves EINVAL");auto r=Call(runtime,image,"growdown_malformed",{c.size,uint32_t(c.prot),uint32_t(c.flags),uint64_t(c.offset)});Check(uint32_t(r)==1&&uint32_t(r>>32)==22,"real NDK malformed/shared growth observes genuine existing EINVAL");}
 const auto path=std::filesystem::u8path(GROWDOWN_ROOT)/"valid-file.bin";{std::ofstream file(path,std::ios::binary);for(unsigned i=0;i<8192;++i)file.put(char(i));}f.MountFile("/valid-file",path);const auto fd=f.Open("/valid-file",0);Check(fd>=0,"file growth validation uses a real valid readable descriptor");Check(f.Mmap(0,8192,1,map_private|map_growdown,fd,0)==UINT64_MAX&&f.Error()==22,"Linux-invalid file-backed growth retains EINVAL with valid file arguments");Check(!f.Close(fd),"validation fixture descriptor retires normally");
 f.SetError(71);Check(Boundary([&]{f.Mmap(0,8192,3,0x120122,-1,0);})&&f.Error()==71,"aligned zero NOREPLACE is not a malformed address; unsupported growth stops without fake EINVAL or EPERM");f.SetError(71);Check(f.Mmap(address+1,8192,3,0x120122,-1,0)==UINT64_MAX&&f.Error()==22,"malformed unaligned NOREPLACE address keeps EINVAL");
 std::printf("MAP_GROWSDOWN boundary: %u checks passed; real NDK original request stops explicitly, malformed calls retain EINVAL, no errno/native/owner/generation/epoch mutation\n",checks);
}

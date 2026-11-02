#include "filesystem.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <fstream>
#include <memory>
#include <thread>
#include <windows.h>
namespace {
using bunker::windows::FileSystem;using namespace bunker::windows::linux_flags;
FileSystem *active_files;
void *Resolve(const char *name){return reinterpret_cast<void*>(active_files->Marker(name));}
std::atomic<unsigned> checks{0};
void Check(bool ok,const char *why){if(!ok)throw std::runtime_error(why);++checks;}
bool Pinned(const std::function<void()> &operation,const char *name){try{operation();}catch(const std::runtime_error &error){return std::string(error.what())==std::string("unsupported ")+name+" of active mapping use";}return false;}
DWORD PageProtection(addr_t address){MEMORY_BASIC_INFORMATION info{};Check(VirtualQuery(reinterpret_cast<void*>(address),&info,sizeof(info))==sizeof(info),"native page query succeeds");return info.Protect;}
struct Runner{
 recomp::Runtime runtime;elf_image image{};FileSystem &files;
 explicit Runner(FileSystem &f):files(f){active_files=&f;Check(!elf_load(MAPPING_IMAGE,0x75000000,Resolve,&image),"actual NDK mapping fixture loads");f.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));}
 addr_t Run(const char *name,std::initializer_list<addr_t> args){alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t n=0;for(auto value:args)(s.gpr.*regs[n++]).qword=value;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK mapping caller preserves PC/SP");return s.gpr.x0.qword;}
};
}
int main(int argc,char **argv){try{
 if(argc>1){auto files=std::make_unique<FileSystem>();auto base=files->Mmap(0,8192,3,map_private|map_anonymous,-1,0);auto use=files->AcquireMappingUse(base,64,true);Check(use&&use->lease,"negative active use is a real pin");std::string mode=argv[1];
  if(mode=="--destroy-pinned"){files.reset();return 99;}
  Runner guest(*files);if(mode=="--guest-pinned-unmap")guest.Run("mapping_guest_unmap",{base,8192});else guest.Run("mapping_guest_protect",{base+4096,4096,1});return 98;
 }
 FileSystem files;Runner guest(files);auto base=guest.Run("mapping_guest_map",{8192});Check(base!=UINT64_MAX,"actual NDK mmap produces owned anonymous mapping");
 files.SetError(123);auto info=files.MappingRegion(base,8192,true);Check(info&&info->base==base&&info->size==8192&&info->generation,"snapshot has actual owned mmap identity");
 auto use=files.AcquireMappingUse(base+31,64,true);Check(use&&use->lease&&use->region.base==base&&use->region.size==8192&&use->region.generation==info->generation&&files.Error()==123,"lease validates interior span and pins complete owner without errno change");
 Check(guest.Run("mapping_guest_touch",{base,8192})==0x35a7,"actual NDK loads/stores use physically pinned mapping");auto protection=PageProtection(base+4096);
 auto preserve=[&]{auto now=files.MappingRegion(base,8192,true);Check(now&&now->generation==info->generation&&PageProtection(base+4096)==protection&&*reinterpret_cast<uint8_t*>(base)==0x35&&*reinterpret_cast<uint8_t*>(base+8191)==0xa7&&files.Error()==123,"blocked mutations preserve native pages, bytes, owner generation and errno");};
 Check(Pinned([&]{files.Munmap(base,8192);},"munmap"),"full unmap of pinned owner is explicit unsupported");preserve();
 Check(Pinned([&]{files.Mprotect(base+4096,4096,0);},"mprotect"),"disjoint page protection within pinned owner is rejected");preserve();
 Check(Pinned([&]{files.Mprotect(base+4096,8192,1);},"mprotect"),"partially overlapping unsupported range detects pin before any mutation");preserve();
 Check(Pinned([&]{files.Mprotect(base-4096,8192,1);},"mprotect"),"range starting before pinned owner cannot change intersecting pages");preserve();
 auto copied=*use;auto token=use->lease;std::weak_ptr<void> weak=token;auto independent=files.AcquireMappingUse(base+4096,128,true);use.reset();copied.lease.reset();
 Check(Pinned([&]{files.Munmap(base,8192);},"munmap")&&!weak.expired(),"copied lease retains physical pin after original MappingUse is released");token.reset();Check(weak.expired()&&Pinned([&]{files.Munmap(base,8192);},"munmap"),"independent acquire keeps its own real pin after final copied token release");independent.reset();
 auto reservation=bunker::test::ReserveAcrossOperation(base,8,[&]{auto transient=files.AcquireMappingUse(base,8,true);if(!transient)throw std::runtime_error("transient use missing");});Check(reservation.status==0,"acquire/release metadata never invalidates guest exclusive reservation");
 use=files.AcquireMappingUse(base,64,true);reservation=bunker::test::ReserveAcrossOperation(base,8,[&]{if(!Pinned([&]{files.Munmap(base,8192);},"munmap"))throw std::runtime_error("pinned unmap unexpectedly accepted");});Check(reservation.status==0,"rejected unmap performs no tracked epoch write");
 Check(files.Mmap(base,8192,3,map_private|map_anonymous|map_fixed_no_replace,-1,0)==UINT64_MAX&&files.Error()==17,"real MAP_FIXED_NOREPLACE cannot replace pinned native pages");Check(files.MappingRegion(base,64,true)->generation==info->generation,"failed replacement preserves actual generation");use.reset();
 Check(!guest.Run("mapping_guest_protect",{base,8192,1}),"actual NDK mprotect succeeds after final lease release");Check(!files.AcquireMappingUse(base,8192,true)&&files.AcquireMappingUse(base,8192,false).has_value(),"read-only owner accepts readable use and rejects writable use");
 Check(!files.AcquireMappingUse(base,0,false)&&!files.AcquireMappingUse(base+8191,2,false)&&!files.AcquireMappingUse(UINT64_MAX-3,8,false)&&!files.AcquireMappingUse(0,1,false),"empty, spanning, overflow and unknown uses reject");
 std::array<uint8_t,128> unknown{};Check(!files.AcquireMappingUse(reinterpret_cast<addr_t>(unknown.data()),unknown.size(),true),"committed external stack/heap pages are not inferred as owned mappings");
 Check(!files.Mprotect(base+4096,4096,0)&&!files.AcquireMappingUse(base,8192,false)&&files.AcquireMappingUse(base,64,false).has_value(),"acquire validates every native protection region");
 Check(!files.Mprotect(base,8192,3),"restore writable anonymous owner");DWORD previous;Check(VirtualProtect(reinterpret_cast<void*>(base+4096),4096,PAGE_READWRITE|PAGE_GUARD,&previous)&&!files.AcquireMappingUse(base,8192,false),"actual guarded page rejects use acquisition");Check(VirtualProtect(reinterpret_cast<void*>(base+4096),4096,PAGE_READWRITE,&previous),"restore guard test page");
 Check(!guest.Run("mapping_guest_unmap",{base,8192})&&!files.AcquireMappingUse(base,64,false),"actual NDK unmap after release revokes owner");
 // Actual file view retains its own lifetime even after the source fd closes.
 auto path=std::filesystem::u8path(MAPPING_ROOT)/"lease-file.bin";{std::ofstream output(path,std::ios::binary);for(unsigned n=0;n<16384;++n)output.put(static_cast<char>(n*17+3));}
 files.MountFile("/lease-file",path);auto fd=files.Open("/lease-file",0);auto file=files.Mmap(0,8192,1,map_private,fd,4096);Check(file!=UINT64_MAX&&!files.Close(fd),"real 4KiB-offset file mapping survives source fd close");
 auto file_use=files.AcquireMappingUse(file+7,100,false);Check(file_use&&file_use->lease&&file_use->region.base==file&&file_use->region.size==8192&&!files.AcquireMappingUse(file,1,true),"file mapping lease excludes hidden native view prefix and enforces actual read-only protection");
 Check(Pinned([&]{files.Mprotect(file,8192,3);},"mprotect")&&Pinned([&]{files.Munmap(file,8192);},"munmap"),"real file mapping protection and unmap remain guarded");file_use.reset();Check(!files.Mprotect(file,8192,3)&&!files.Munmap(file,8192),"file mapping native cleanup succeeds after release");
 // Acquire and mutation share one registry mutex. A winning acquire remains live
 // in the main thread until both racers finish, so mutation cannot slip through.
 unsigned acquired_wins=0,mutation_wins=0;
 for(bool protect:{false,true})for(unsigned trial=0;trial<64;++trial){auto address=files.Mmap(0,8192,3,map_private|map_anonymous,-1,0);Check(address!=UINT64_MAX,"race owner allocation");auto generation=files.MappingRegion(address,64,true)->generation;std::optional<FileSystem::MappingUse> acquired;std::atomic<unsigned> ready{0};std::atomic<bool> go{false};bool rejected=false;int changed=-2;
  std::thread acquire([&]{++ready;while(!go.load())std::this_thread::yield();acquired=files.AcquireMappingUse(address,8192,true);});
  std::thread mutate([&]{++ready;while(!go.load())std::this_thread::yield();try{changed=protect?files.Mprotect(address,8192,1):files.Munmap(address,8192);}catch(const std::runtime_error &error){rejected=std::string(error.what())==std::string("unsupported ")+(protect?"mprotect":"munmap")+" of active mapping use";}});
  while(ready.load()!=2){std::this_thread::yield();}
  go=true;acquire.join();mutate.join();Check(acquired?(rejected&&changed==-2):(!rejected&&changed==0),"atomic acquire-vs-unmap/protect permits exactly the safe ordering");
  if(acquired)++acquired_wins;else ++mutation_wins;
  if(acquired){Check(acquired->region.generation==generation&&files.MappingRegion(address,8192,true)->generation==generation,"winning pin preserves actual generation and writable pages");}
  acquired.reset();if(protect||rejected)Check(!files.Munmap(address,8192),"race owner releases normally after last use");
 }
 Check(acquired_wins+mutation_wins==128,"all128 atomic mapping races complete");
 Check(files.Error()==17,"metadata-only race queries do not overwrite caller errno");std::printf("Mapping race outcomes: acquired=%u mutation=%u\n",acquired_wins,mutation_wins);std::printf("Windows mapping use: %u checks; real anonymous/file mappings, physical pin copies, native NDK access, no mutation/epoch/errno changes while pinned, atomic races and release\n",checks.load());
}catch(const std::exception &error){std::fprintf(stderr,"mapping-use test: %s\n",error.what());return 1;}}

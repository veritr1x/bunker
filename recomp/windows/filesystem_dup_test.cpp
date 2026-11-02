#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "filesystem.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <limits>
#include <set>
#include <stdexcept>
#include <thread>
#include <vector>
namespace {
using bunker::windows::FileSystem;using namespace bunker::windows::linux_flags;
std::atomic<unsigned> checks{0},ndk_calls{0},ndk_dups{0};
void Check(bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;}
FileSystem *resolver_files;
void *Resolve(const char *name){return reinterpret_cast<void*>(resolver_files->Marker(name));}
struct Observation {uint64_t before=0x1122334455667788ULL;int32_t errno_before=-1,result=-2,errno_after=-1;uint32_t padding=0xa5c3e179;uint64_t after=0x8877665544332211ULL;};
static_assert(sizeof(Observation)==32&&offsetof(Observation,result)==12&&offsetof(Observation,after)==24);
struct Guest {
  FileSystem &files;recomp::Runtime runtime,provider;elf_image image{};
  explicit Guest(FileSystem &f):files(f){
    resolver_files=&f;Check(!elf_load(DUP_IMAGE,0x76000000,Resolve,&image),"strict actual NDK dup fixture loads");
    f.Install(provider);runtime.AddTraces(kTraces,std::size(kTraces));
    for(const char *name:{"dup","__errno","read","write","lseek","lseek64","close","mmap","munmap"}){
      auto marker=f.Marker(name);Check(marker!=0,"actual installed filesystem marker exists");
      const bool duplicate=!std::strcmp(name,"dup");
      runtime.AddImport(marker,[&,marker,duplicate](State &s){
        const auto source=static_cast<int32_t>(s.gpr.x0.dword);provider.Dispatch(s,marker,nullptr);
        if(duplicate){Check(s.gpr.x0.qword==uint64_t(s.gpr.x0.dword),"actual dup bridge returns signed int through W0 with zero upper bits");Check(source>=1000||static_cast<int32_t>(s.gpr.x0.dword)==-1,"invalid managed source never becomes native CRT fd");++ndk_dups;}
      });
    }
  }
  uint64_t Run(const char *name,std::initializer_list<uint64_t> args){
    alignas(16)std::array<uint8_t,65536>stack{};State state{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5};size_t n=0;
    for(auto value:args)(state.gpr.*regs[n++]).qword=value;
    const auto top=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.sp.qword=top;state.gpr.x30.qword=0xfeedffff;
    runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,name)));
    Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==top,"actual NDK caller returns on original PC/owned stack");++ndk_calls;return state.gpr.x0.qword;
  }
  int32_t Dup(int32_t fd,bool indirect=false){
    files.SetError(777);Observation out;
    auto returned=Run(indirect?"dup_guest_indirect":"dup_guest_direct",{uint64_t(uint32_t(fd))|0xa5a5a5a500000000ULL,reinterpret_cast<addr_t>(&out)});
    Check(out.before==0x1122334455667788ULL&&out.after==0x8877665544332211ULL&&out.padding==0xa5c3e179,"actual NDK errno/result stores preserve canaries and padding");
    const auto result=static_cast<int32_t>(returned);Check(out.result==result&&out.errno_before==777&&out.errno_after==(result<0?9:777)&&files.Error()==out.errno_after,"actual direct/function-pointer dup preserves success errno or reports EBADF");return result;
  }
  int64_t Read(int fd,void *p,size_t n){return static_cast<int64_t>(Run("dup_guest_read",{uint32_t(fd),reinterpret_cast<addr_t>(p),n}));}
  int64_t Write(int fd,const void *p,size_t n){return static_cast<int64_t>(Run("dup_guest_write",{uint32_t(fd),reinterpret_cast<addr_t>(p),n}));}
  int64_t Seek(int fd,int64_t n,int whence){return static_cast<int64_t>(Run("dup_guest_seek",{uint32_t(fd),uint64_t(n),uint32_t(whence)}));}
  int Close(int fd){return static_cast<int32_t>(Run("dup_guest_close",{uint32_t(fd)}));}
};
uint64_t Hash(const uint8_t *p,size_t n){uint64_t result=5381;while(n--)result=result*33+*p++;return result;}
void Mount(FileSystem &files,const std::filesystem::path &root){files.MountDirectory("/data",root,true);files.SetWorkingDirectory("/data");}
}
extern "C" __attribute__((noinline)) void DupStateWitness(FileSystem *owner,int32_t source,int32_t clone){asm volatile(""::"r"(owner),"r"(source),"r"(clone):"memory");}
int main(int argc,char **argv){try{
 const auto root=std::filesystem::u8path(argc>1?argv[1]:DUP_ROOT);std::vector<uint8_t>data(16384);for(size_t n=0;n<data.size();++n)data[n]=uint8_t(n*17+3);
 {std::ofstream f(root/"dup-data.bin",std::ios::binary);f.write(reinterpret_cast<const char*>(data.data()),data.size());}
 {std::ofstream f(root/"dup-other.bin",std::ios::binary);std::array<uint8_t,64>b{};b.fill(0xb2);f.write(reinterpret_cast<const char*>(b.data()),b.size());}
 {std::ofstream f(root/"dup-sequence.bin",std::ios::binary);for(uint32_t n=0;n<4096;++n)f.write(reinterpret_cast<const char*>(&n),sizeof(n));}
 FileSystem files;Mount(files,root);Guest guest(files);
 const char *old_names[]={"__errno","open","close","read","write","lseek","lseek64","stat","lstat","fstat","access","fopen","fclose","fread","fwrite","fseek","fseeko","ftell","ftello","feof","ferror","fflush","mmap","munmap","mprotect","madvise","mkdir","setvbuf","unlink","rmdir","opendir","readdir","closedir","rename"};
 for(size_t n=0;n<std::size(old_names);++n){Check(files.Marker(old_names[n])==0x7ff600000000ULL+n*8,"every accepted filesystem marker remains unchanged");}
 Check(files.Marker("dup")==0x7ff600000000ULL+std::size(old_names)*8,"dup marker is appended");
 int source=files.Open("dup-data.bin",read_only|close_on_exec);Check(source==1000,"fresh bounded namespace starts1000");int clone=guest.Dup(source);Check(clone==1001,"actual NDK duplicate occupies lowest available supported slot");DupStateWitness(&files,source,clone);
 bunker::windows::AndroidStat a{},b{};Check(!files.FStat(source,&a)&&!files.FStat(clone,&b)&&a.inode==b.inode&&a.device==b.device&&a.size==b.size,"source/duplicate share actual inode/device/size");
 std::array<uint8_t,32>bytes{};Check(guest.Read(source,bytes.data(),3)==3&&!std::memcmp(bytes.data(),data.data(),3),"actual NDK source read starts original offset");Check(guest.Read(clone,bytes.data(),5)==5&&!std::memcmp(bytes.data(),data.data()+3,5),"native duplicate shares advancing offset");Check(guest.Seek(clone,4097,0)==4097&&guest.Read(source,bytes.data(),7)==7&&!std::memcmp(bytes.data(),data.data()+4097,7),"seek through duplicate updates source position");
 int successor=guest.Dup(clone,true);Check(successor==1002,"function-pointer duplicate of duplicate is independently owned");int occupied=files.Open("dup-data.bin",0);Check(occupied==1003,"Open skips its next monotonic slot already occupied by Dup");Check(!files.Close(occupied),"collision probe closes independent Open");Check(guest.Write(successor,"x",1)==-1&&files.Error()==9,"read-only access survives duplication");Check(!guest.Close(source)&&guest.Read(clone,bytes.data(),1)==1&&bytes[0]==data[4104],"closing source preserves duplicate");Check(!guest.Close(clone)&&guest.Read(successor,bytes.data(),1)==1&&bytes[0]==data[4105],"closing first clone preserves duplicate-of-duplicate");Check(guest.Dup(source)==-1&&guest.Dup(clone,true)==-1,"retired source/clone reject before CRT");
 int hole=guest.Dup(successor);Check(hole==1000,"dup reuses lowest namespace hole");int opened=files.Open("dup-data.bin",0);Check(opened==1004,"monotonic Open skips live slots filled by Dup");Check(guest.Seek(successor,int64_t(data.size()-1),0)==int64_t(data.size()-1)&&guest.Read(hole,bytes.data(),1)==1&&bytes[0]==data.back()&&guest.Read(successor,bytes.data(),1)==0&&guest.Seek(hole,0,0)==0&&guest.Read(successor,bytes.data(),1)==1&&bytes[0]==data[0],"EOF through one alias and seek through the other share one offset");Check(!files.Close(opened)&&!guest.Close(hole)&&!guest.Close(successor),"every descriptor retires independently");
 for(int fd:{-1,0,1,2,42,999,std::numeric_limits<int>::max()}){Check(guest.Dup(fd)==-1&&guest.Dup(fd,true)==-1,"unknown/negative/native-looking descriptor rejects with real EBADF");}
 auto stream=files.FOpen("dup-data.bin","rb");auto directory=files.OpenDir("/data");Check(stream&&directory&&guest.Dup(int32_t(stream))==-1&&guest.Dup(int32_t(directory),true)==-1,"opaque FILE/DIR token lowW0 cannot become native descriptor");Check(!files.FClose(stream)&&!files.CloseDir(directory),"opaque stream/directory owners remain independent");
 int append_fd=files.Open("dup-append.bin",read_write|create|truncate|append|0x1000);Check(append_fd>=1000,"real append/sync file opens");int appended=guest.Dup(append_fd,true);Check(guest.Write(append_fd,"abc",3)==3&&guest.Seek(appended,0,0)==0&&guest.Write(appended,"DEF",3)==3&&guest.Seek(append_fd,0,0)==0&&guest.Read(append_fd,bytes.data(),6)==6&&!std::memcmp(bytes.data(),"abcDEF",6),"both aliases retain real append/status and offset behavior");Check(!guest.Close(appended)&&guest.Write(append_fd,"!",1)==1&&!guest.Close(append_fd),"reverse close order preserves original writable descriptor");
 // Map using the actual NDK duplicate/mapper/close path. The view owns a separate lifetime.
 for(bool original_first:{false,true}){
   int original=files.Open("dup-data.bin",0),copy=guest.Dup(original,original_first);auto mapped=guest.Run("dup_guest_map",{uint32_t(copy),4096,4096});Check(mapped!=UINT64_MAX,"actual NDK mmap uses duplicate descriptor");auto region=files.MappingRegion(mapped,4096,false);Check(region&&region->size==4096,"mapped view has an actual owned generation");
   auto verify=[&]{Check(guest.Run("dup_guest_hash",{mapped,4096})==Hash(data.data()+4096,4096)&&files.MappingRegion(mapped,4096,false)->generation==region->generation,"actual mapped bytes/generation survive descriptor close");};
   Check(!guest.Close(original_first?original:copy),"first chosen native descriptor closes");verify();Check(!guest.Close(original_first?copy:original),"second native descriptor closes");verify();Check(!guest.Run("dup_guest_unmap",{mapped,4096})&&!files.MappingRegion(mapped,1,false),"view retires only through actual unmap");
 }
 int epoch=files.Open("dup-data.bin",0),epoch_copy=-1;alignas(8)uint64_t sentinel=0xabcdef0123456789ULL;files.SetError(444);
 auto reservation=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&sentinel),8,[&]{epoch_copy=files.Dup(epoch);if(epoch_copy<0)throw std::runtime_error("metadata-only dup failed");});Check(!reservation.status&&sentinel==0xabcdef0123456789ULL&&files.Error()==444,"successful Dup changes no guest epoch/bytes/caller errno");Check(!files.Close(epoch)&&!files.Close(epoch_copy),"epoch probe descriptor owners close");
 // Atomic native shared offsets: every fixed-size record must appear exactly once.
 int sequence=files.Open("dup-sequence.bin",0);std::array<int,8>aliases{};aliases[0]=sequence;for(size_t n=1;n<aliases.size();++n)aliases[n]=files.Dup(sequence);
 std::array<std::vector<uint32_t>,8>observed;std::vector<std::thread>readers;
 for(size_t n=0;n<aliases.size();++n)readers.emplace_back([&,n]{for(;;){uint32_t value=0;auto got=guest.Read(aliases[n],&value,4);if(!got)break;Check(got==4,"concurrent actual NDK read gets one complete record");observed[n].push_back(value);}});
 for(auto &thread:readers){thread.join();}
 std::vector<uint32_t>all;for(auto &values:observed){all.insert(all.end(),values.begin(),values.end());}std::sort(all.begin(),all.end());Check(all.size()==4096,"all shared-offset native records observed");for(size_t n=0;n<all.size();++n){Check(all[n]==n,"shared-offset records neither overlap nor disappear");}Check(files.Seek(sequence,0,1)==16384,"all aliases share final offset");for(auto fd:aliases){Check(!files.Close(fd),"concurrent reader alias closes");}
 unsigned succeeded=0,closed_won=0,reused_a=0,reused_b=0,reused_bad=0;
 for(bool reuse:{false,true})for(unsigned trial=0;trial<128;++trial){
   FileSystem race;Mount(race,root);int old=race.Open("dup-data.bin",0),other=race.Open("dup-other.bin",0);Check(old==1000&&other==1001,"race has isolated exact supported slots");std::atomic<unsigned>ready{0};std::atomic<bool>go{false};int result=-2,error=0,replacement=-1;
   std::thread duplicate([&]{++ready;while(!go.load())std::this_thread::yield();race.SetError(777);result=race.Dup(old);error=race.Error();});
   std::thread retire([&]{++ready;while(!go.load())std::this_thread::yield();Check(!race.Close(old),"racing close retires source once");if(reuse){replacement=race.Dup(other);Check(replacement>=1000,"immediate reuse creates a real other-file alias");}});
   while(ready.load()!=2){std::this_thread::yield();}go=true;duplicate.join();retire.join();
   if(result<0){Check(result==-1&&error==9,"close winning lookup gap gives EBADF");if(reuse)++reused_bad;else ++closed_won;}
   else{uint8_t value=0;Check(error==777&&race.Read(result,&value,1)==1,"successful racing duplicate remains real/open and preserves errno");if(reuse){Check(value==data[0]||value==0xb2,"reused numeric source can refer only to real old/new description at lookup");if(value==data[0])++reused_a;else ++reused_b;}else{Check(value==data[0],"dup-vs-close success retains original file");++succeeded;}}
   // A lookup after new binding publication may legally duplicate the new file;
   // no private timing hook or claim about the invisible lookup instant is made.
   std::set<int>live{other};if(result>=0)live.insert(result);if(replacement>=0)live.insert(replacement);for(int fd:live)Check(!race.Close(fd),"race owns/closes each actual surviving fd exactly once");
 }
 Check(succeeded+closed_won==128&&reused_a+reused_b+reused_bad==128,"all close/reuse races finish with only allowed ownership outcomes");
 std::printf("Dup race outcomes: original=%u closed=%u; reuse original=%u replacement=%u EBADF=%u\n",succeeded,closed_won,reused_a,reused_b,reused_bad);
 std::printf("Windows filesystem dup: %u checks; %u actual NDK calls/%u dup calls; shared offsets/status, independent native closure, mapping lifetime, bounded namespace, concurrent reads/close/reuse and unchanged epochs\n",checks.load(),ndk_calls.load(),ndk_dups.load());
}catch(const std::exception &error){std::fprintf(stderr,"filesystem dup test: %s\n",error.what());return 1;}}

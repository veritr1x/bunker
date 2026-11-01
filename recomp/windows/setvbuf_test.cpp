#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "filesystem.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <thread>
#include <vector>
using bunker::windows::FileSystem;
static FileSystem *files;
static void *Resolve(const char *name){return reinterpret_cast<void*>(files->Marker(name));}
struct StreamResult {uint64_t stream;int32_t result,error;uint64_t count;uint8_t byte,next;};
int main(){try{
 unsigned checks=0;auto Check=[&](bool good,const char *why){if(!good)throw std::runtime_error(why);++checks;};
 namespace fs=std::filesystem;auto root=fs::u8path(SETVBUF_ROOT)/("run-"+std::to_string(GetCurrentProcessId())+"-"+std::to_string(GetTickCount64()));fs::create_directories(root);
 const auto path=root/"data.bin";std::vector<uint8_t> data(8192,'Q');data[0]='A';data[1]='B';data[2]='C';{std::ofstream out(path,std::ios::binary);out.write(reinterpret_cast<const char*>(data.data()),data.size());}
 FileSystem provider;files=&provider;provider.MountDirectory("/rw",root,true);recomp::Runtime runtime;provider.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));elf_image image{};
 Check(elf_load(SETVBUF_IMAGE,0x5a000000,Resolve,&image)==0,"load actual NDK fopen/setvbuf/read callers");
 auto Address=[](const void *p){return reinterpret_cast<addr_t>(p);};
 auto Run=[&](const char *name,std::initializer_list<addr_t> args={}){
  alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t i=0;for(auto a:args)(s.gpr.*regs[i++]).qword=a;
  s.gpr.sp.qword=Address(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;auto entry=elf_symbol(&image,name);Check(entry!=nullptr,"NDK fixture entry exists");runtime.Run(s,Address(entry));
  Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==Address(stack.data()+stack.size()),"NDK PC/SP and return ABI");return s.gpr.x0.qword;
 };
 int32_t constants[6]{};Run("stream_constants",{Address(constants)});
 Check(constants[0]==0&&constants[1]==1&&constants[2]==2&&constants[3]==8&&constants[4]==8&&constants[5]==-1,"installed NDK buffering constants, size_t and FILE-pointer widths");
 Check(provider.Marker("mkdir")==0x7ff600000000ULL+26*8&&provider.Marker("setvbuf")==provider.Marker("mkdir")+8,"new marker appended after all existing imports");
 constexpr uint64_t success=uint64_t(123)<<32;auto Error=[](uint32_t e){return(uint64_t(e)<<32)|0xffffffffU;};
 struct Guard{uint64_t before=0x1122334455667788ULL;StreamResult result{};uint64_t after=0x8877665544332211ULL;} plain,unbuffered;
 const char *guest="/rw/data.bin";Run("stream_open",{Address(guest),0,Address(&plain.result)});Run("stream_open",{Address(guest),1,Address(&unbuffered.result)});
 for(auto g:{&plain,&unbuffered})Check(g->before==0x1122334455667788ULL&&g->after==0x8877665544332211ULL&&g->result.stream&&g->result.result==0&&g->result.error==123&&g->result.count==1&&g->result.byte=='A',"fopen/immediate setvbuf/fread preserve errno and tracked output canaries");
 HANDLE writer=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,0,nullptr);Check(writer!=INVALID_HANDLE_VALUE,"independent host file writer opens concurrently");
 LARGE_INTEGER offset{};offset.QuadPart=2;DWORD written=0;const char update='Z';Check(SetFilePointerEx(writer,offset,nullptr,FILE_BEGIN)&&WriteFile(writer,&update,1,&written,nullptr)&&written==1&&FlushFileBuffers(writer),"independent same-file byte update flushed");CloseHandle(writer);
 Run("stream_read",{Address(&plain.result)});Run("stream_read",{Address(&unbuffered.result)});
 Check(plain.result.count==2&&plain.result.byte=='B'&&plain.result.next=='C',"buffered control really prefetched the old third byte");
 std::fprintf(stderr,"external update witness buffered=%c%c native-unbuffered=%c%c mode=%d\n",plain.result.byte,plain.result.next,unbuffered.result.byte,unbuffered.result.next,_IONBF);
 Check(unbuffered.result.count==2&&unbuffered.result.byte=='B'&&unbuffered.result.next=='Z',"translated native unbuffering avoids full-buffer prefetch: third byte observes host update");
 Check(Run("stream_seek",{Address(&unbuffered.result),0})==success,"NDK fseek succeeds and preserves guest errno on unbuffered stream");Run("stream_read",{Address(&unbuffered.result)});Check(unbuffered.result.byte=='A',"unbuffered seek/read position correct");
 auto Reject=[&](const std::function<void()> &op,const char *why){bool rejected=false;try{op();}catch(const std::runtime_error&){rejected=true;}Check(rejected,why);};
 Reject([&]{provider.FSetBuffer(unbuffered.result.stream,0,2,0);},"late stream reconfiguration rejected before native undefined contract");
 auto fresh=provider.FOpen(guest,"rb");Check(fresh!=0,"owned pre-I/O stream for unsupported shape checks");
 for(auto mode:{0,1})Reject([&]{provider.FSetBuffer(fresh,0,mode,4096);},"other legal Android buffering modes remain explicit unsupported");
 Reject([&]{provider.FSetBuffer(fresh,1,2,0);},"non-NULL guest buffer is never retained or dereferenced");
 Reject([&]{provider.FSetBuffer(fresh,0,2,UINT64_MAX);},"nonzero/high64 size remains explicit scope boundary");
 Check(Run("stream_mode",{fresh,0,uint32_t(-1),0})==Error(22)&&Run("stream_mode",{fresh,0,3,0})==Error(22),"invalid signed/positive mode produces actual EINVAL and nonzero return");
 Check(Run("stream_mode",{fresh,0,2,0})==success,"unsupported/invalid requests leave fresh stream genuinely usable");
 Check(provider.FClose(fresh)==0,"fresh stream closes");Check(Run("stream_mode",{fresh,0,2,0})==Error(9),"stale token fails EBADF without CRT pointer dereference");
 Check(Run("stream_mode",{0,0,2,0})==Error(9)&&Run("stream_mode",{0x123456789abcdef0ULL,0,2,0})==Error(9),"NULL/foreign FILE tokens are explicit guest errors");
 for(auto token:{plain.result.stream,unbuffered.result.stream}){Check(Run("stream_close",{token})==success,"each real stream closes once");Check(Run("stream_close",{token})==Error(9),"second close retains ownership diagnostics");}
 // Lease/io lock interaction: racing a valid operation with close produces
 // either one real success before close or EBADF, never a freed CRT access.
 for(unsigned n=0;n<16;++n){auto token=provider.FOpen(guest,"rb");std::atomic<bool> go{false};int a=7,b=7,e=0;
  std::thread one([&]{while(!go.load(std::memory_order_acquire))std::this_thread::yield();a=provider.FSetBuffer(token,0,2,0);e=provider.Error();});
  std::thread two([&]{while(!go.load(std::memory_order_acquire))std::this_thread::yield();b=provider.FClose(token);});go.store(true,std::memory_order_release);one.join();two.join();
  Check(b==0&&(a==0||(a==-1&&e==9)),"concurrent close and setvbuf use owned stream lease/io serialization");}
 fs::remove_all(root);std::printf("Windows setvbuf: %u checks passed; exact NDK _IONBF2 -> native%d, real unbuffered-vs-buffered external-update witness, errno/seek/lifetime/lease gates\n",checks,_IONBF);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"setvbuf gate failure: %s\n",e.what());return 1;}}

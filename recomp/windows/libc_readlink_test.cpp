#include "libc.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "old_markers.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif
namespace {
std::atomic<unsigned> checks{0},calls{0};
bunker::windows::LibC *provider;
thread_local int guest_error;
thread_local uint64_t expected_size;
thread_local addr_t expected_path,expected_output;
thread_local int64_t expected_result;
constexpr addr_t kErrno=0x7ffc00000000ULL,kReadlink=0x7ffc00000008ULL;
void Check(bool value,const char *message){if(!value){std::fprintf(stderr,"readlink check: %s\n",message);std::abort();}++checks;}
void *Resolve(const char *name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(kErrno);if(!std::strcmp(name,"readlink"))return reinterpret_cast<void*>(kReadlink);return reinterpret_cast<void*>(provider->Marker(name));}
std::string NativeImage(){
#ifdef _WIN32
 std::vector<wchar_t> wide(256);
 for(;;){DWORD n=GetModuleFileNameW(nullptr,wide.data(),static_cast<DWORD>(wide.size()));Check(n>0,"independent native image reference");if(n<wide.size()){int bytes=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide.data(),n,nullptr,0,nullptr,nullptr);Check(bytes>0,"independent strict Win32 UTF8 sizing");std::string text(bytes,'\0');Check(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide.data(),n,text.data(),bytes,nullptr,nullptr)==bytes,"independent native UTF8 reference");std::replace(text.begin(),text.end(),'\\','/');return text;}wide.resize(wide.size()*2);}
#else
 std::vector<char> bytes(256);for(;;){auto n=::readlink("/proc/self/exe",bytes.data(),bytes.size());Check(n>=0,"independent native Linux image reference");if(size_t(n)<bytes.size())return std::string(bytes.data(),size_t(n));bytes.resize(bytes.size()*2);}
#endif
}
}
int main(int argc,char **argv){
#ifdef _WIN32
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
 bunker::windows::LibC libc;provider=&libc;libc.SetErrorSink([](int e){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&e,sizeof(e));});
 recomp::Runtime runtime;libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
 runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
 runtime.AddImport(kReadlink,[&](State&s){Check(s.gpr.x0.qword==expected_path&&s.gpr.x1.qword==expected_output&&s.gpr.x2.qword==expected_size,"real NDK three GP arguments and full64 capacity");const auto x1=s.gpr.x1.qword,x2=s.gpr.x2.qword;runtime.Dispatch(s,libc.Marker("readlink"),nullptr);++calls;Check(s.gpr.x0.qword==uint64_t(expected_result),"installed bridge returns full signed64 ssize_t");Check(s.gpr.x1.qword==x1&&s.gpr.x2.qword==x2,"bridge preserves other arguments");});
 elf_image image{};Check(!elf_load(READLINK_LIBRARY,0x5c000000,Resolve,&image),"strict NDK image load");
 for(size_t i=0;i<std::size(kOldMarkers);++i){Check(libc.Marker(kOldMarkers[i])==0x7ffb00000000ULL+i*8,"all old markers unchanged");}Check(libc.Marker("readlink")==libc.Marker("bsearch")+8,"readlink appended marker");
 auto Run=[&](const char *path,void *output,uint64_t size,int indirect,int64_t expected,int sentinel=731){alignas(16)std::array<unsigned char,65536> stack{};State state{};int error=-1;expected_size=size;expected_path=reinterpret_cast<addr_t>(path);expected_output=reinterpret_cast<addr_t>(output);expected_result=expected;state.gpr.x0.qword=expected_path;state.gpr.x1.qword=expected_output;state.gpr.x2.qword=size;state.gpr.x3.dword=indirect;state.gpr.x4.dword=sentinel;state.gpr.x5.qword=reinterpret_cast<addr_t>(&error);state.gpr.x19.qword=0x123456789abcdef0ULL;state.gpr.x29.qword=0xfedcba9876543210ULL;state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_readlink")));Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK return PC/SP preserved");Check(state.gpr.x19.qword==0x123456789abcdef0ULL&&state.gpr.x29.qword==0xfedcba9876543210ULL,"NDK saved registers preserved");Check(state.gpr.x0.qword==uint64_t(expected)&&error==guest_error,"NDK full signed result and errno capture");return error;};
 const auto native=NativeImage();Check(!native.empty()&&native.find('\0')==std::string::npos,"real native image nonempty");const auto own="/proc/"+std::to_string(libc.ProcessId())+"/exe";
 if(argc>1){const std::string mode=argv[1];std::array<char,256> output{};const auto path=mode=="foreign"?"/proc/"+std::to_string(uint64_t(libc.ProcessId())+1)+"/exe":"/proc/self/fd/1";Run(path.c_str(),output.data(),output.size(),1,0);return 2;}
 for(const auto &path:std::vector<std::string>{"/proc/self/exe",own})for(int indirect:{0,1})for(uint64_t size:std::vector<uint64_t>{1,2,3,31,uint64_t(native.size()-1),uint64_t(native.size()),uint64_t(native.size()+1),4096,UINT64_C(0x100000001),UINT64_C(0x100001000)}){
  std::vector<unsigned char> bytes(native.size()+4098,0xa5);const auto count=std::min<uint64_t>(native.size(),uint32_t(size));Check(Run(path.c_str(),bytes.data()+1,size,indirect,int64_t(count))==731,"success preserves actual guest errno");Check(bytes[0]==0xa5&&bytes[count+1]==0xa5,"no NUL or canary overwrite");Check(!std::memcmp(bytes.data()+1,native.data(),count),"real image bytes truncated by bytecount exactly");
 }
 for(int indirect:{0,1}){
  for(uint64_t size:{UINT64_C(0),UINT64_C(0x80000000),UINT64_C(0x100000000),UINT64_MAX}){Check(Run(nullptr,nullptr,size,indirect,-1)==22,"signed low32 nonpositive precedes both null pointers");Check(Run(reinterpret_cast<const char*>(addr_t(1)),nullptr,size,indirect,-1)==22,"nonpositive capacity never reads invalid path");}
  Check(Run(nullptr,nullptr,1,indirect,-1)==14,"positive nullpath EFAULT");Check(Run("/proc/self/exe",nullptr,1,indirect,-1)==14,"positive validpath nulloutput EFAULT");Check(Run("",nullptr,1,indirect,-1)==2,"emptyname ENOENT before nulloutput");
 }
 std::vector<char> alias(std::max<size_t>(4096,native.size()+8),char(0xa5));std::strcpy(alias.data(),own.c_str());Check(Run(alias.data(),alias.data(),native.size()+1,1,int64_t(native.size()))==731&&!std::memcmp(alias.data(),native.data(),native.size())&&static_cast<unsigned char>(alias[native.size()])==0xa5,"path/output alias uses input snapshot and no appended NUL");
 alignas(64)std::array<uint8_t,64> tracked{};std::memcpy(tracked.data(),native.data(),std::min<size_t>(8,native.size()));auto same=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(tracked.data()),8,[&]{Check(libc.ReadLink("/proc/self/exe",tracked.data(),8)==8,"real same-value provider operation");});Check(same.status==1,"same-value readlink copy invalidates actual exclusive reservation");
 auto no_write=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(tracked.data()),8,[&]{Check(libc.ReadLink(nullptr,nullptr,0)==-1,"failed query does not touch output");});Check(no_write.status==0,"error path preserves reservation");
 std::vector<std::thread> workers;for(unsigned n=0;n<3;++n)workers.emplace_back([&,n]{for(unsigned i=0;i<8;++i){std::vector<char> output(native.size()+1,char(0xa5));Check(Run(own.c_str(),output.data(),output.size(),i&1,int64_t(native.size()),int(800+n))==int(800+n)&&!std::memcmp(output.data(),native.data(),native.size()),"real native image and independent worker errno");}});for(auto &t:workers)t.join();
#ifdef _WIN32
 Check(VirtualFree(image.base,0,MEM_RELEASE)!=0,"Windows loader image uses VirtualAlloc retirement");
#else
 Check(!munmap(image.base,image.span),"Linux loader image uses mmap retirement");
#endif
 std::free(const_cast<uint8_t*>(image.file));
 std::printf("READLINK-SUCCESS checks=%u actual-NDK-calls=%u image-bytes=%zu native-image-reference/truncation/no-NUL/errno/low32/overlap/exclusives/threads\n",checks.load(),calls.load(),native.size());return 0;
}

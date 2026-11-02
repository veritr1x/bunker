#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "filesystem.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <fstream>
#include <map>
#include <set>
#include <stdexcept>
#include <thread>
#include <vector>
using bunker::windows::FileSystem;
using bunker::windows::AndroidDirent;
using bunker::windows::AndroidStat;
namespace fs=std::filesystem;
static FileSystem *provider;
static void *Resolve(const char *name){return reinterpret_cast<void*>(provider->Marker(name));}
struct Observation{uint64_t pointer,inode;int64_t offset;uint32_t record_length,type;char name[256];};
static_assert(sizeof(Observation)==288);
static std::string NativeUtf8(const wchar_t *s,size_t size){
 if(!size)return {};
 auto count=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s,int(size),nullptr,0,nullptr,nullptr);
 if(!count)throw std::runtime_error("independent native UTF8 conversion failed");
 std::string out(count,0);if(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s,int(size),out.data(),count,nullptr,nullptr)!=count)throw std::runtime_error("independent native UTF8 copy failed");return out;
}
static uint64_t NativeInode(const fs::path &path){
 HANDLE file=CreateFileW(path.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
 if(file==INVALID_HANDLE_VALUE)throw std::runtime_error("independent entry handle failed");
 BY_HANDLE_FILE_INFORMATION info{};auto result=GetFileInformationByHandle(file,&info);CloseHandle(file);
 if(!result)throw std::runtime_error("independent entry inode failed");
 return uint64_t(info.nFileIndexHigh)<<32|info.nFileIndexLow;
}
static std::map<std::string,uint32_t> NativeNames(const fs::path &path){
 WIN32_FIND_DATAW data{};HANDLE search=FindFirstFileW((path/L"*").c_str(),&data);if(search==INVALID_HANDLE_VALUE)throw std::runtime_error("independent name enumeration failed");std::map<std::string,uint32_t> names;
 for(;;){const auto name=NativeUtf8(data.cFileName,std::wcslen(data.cFileName));names.emplace(name,data.dwFileAttributes);if(FindNextFileW(search,&data))continue;auto error=GetLastError();FindClose(search);if(error!=ERROR_NO_MORE_FILES)throw std::runtime_error("independent name enumeration error");return names;}
}
int main(){try{
 unsigned checks=0,ndk_calls=0;auto Check=[&](bool ok,const char *why){if(!ok)throw std::runtime_error(why);++checks;};
 const auto parent=fs::canonical(fs::u8path(DIRECTORY_ROOT));const auto root=parent/("run-"+std::to_string(GetCurrentProcessId())+"-"+std::to_string(GetTickCount64()));
 Check(root.is_absolute()&&root.parent_path()==parent,"fixture stays inside named absolute work directory");fs::create_directory(root);
 const auto read=root/"read",empty=root/"empty",outside=root/"outside";fs::create_directory(read);fs::create_directory(empty);fs::create_directory(outside);
 std::vector<fs::path> files;
 auto Put=[&](const fs::path &p){HANDLE h=CreateFileW(p.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_TEMPORARY,nullptr);if(h==INVALID_HANDLE_VALUE)throw std::runtime_error("fixture file creation failed");CloseHandle(h);files.push_back(p);};
 for(unsigned n=0;n<700;++n)Put(read/("file-"+std::to_string(n)+".bin"));
 Put(read/fs::u8path(u8"é.bin"));Put(outside/"keep");fs::create_directory(read/fs::u8path(u8"目录"));
 const auto expected=NativeNames(read);Check(expected.size()>=704,"native source inventory spans more than one 64KiB record batch");
 FileSystem system;provider=&system;system.MountDirectory("/read",read);system.MountDirectory("/empty",empty,true);system.MountFile("/file",files[0]);system.SetWorkingDirectory("/read");
 recomp::Runtime runtime;system.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));elf_image image{};
 Check(!elf_load(DIRECTORY_IMAGE,0x58000000,Resolve,&image),"actual NDK directory caller image loads");
 Check(system.Marker("opendir")==system.Marker("rmdir")+8&&system.Marker("readdir")==system.Marker("opendir")+8&&system.Marker("closedir")==system.Marker("readdir")+8,"all three directory imports append without changing old marker indices");
 auto Address=[](const void *p){return reinterpret_cast<addr_t>(p);};
 auto Run=[&](const char *name,std::initializer_list<addr_t> args){alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t i=0;for(auto x:args)(s.gpr.*regs[i++]).qword=x;s.gpr.sp.qword=Address(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,Address(elf_symbol(&image,name)));++ndk_calls;Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==Address(stack.data()+stack.size()),"NDK directory PC/SP and return ABI");return s.gpr.x0.qword;};
 const uint64_t success=uint64_t(123)<<32,read_success=(uint64_t(321)<<32)|1,read_eof=uint64_t(321)<<32;
 auto Error=[](uint32_t error){return uint64_t(error)<<32|0xffffffffU;};
 auto Open=[&](const char *path,int indirect){int32_t error=-1;auto token=Run("guest_directory_open",{Address(path),addr_t(indirect),Address(&error)});return std::pair<addr_t,int32_t>{token,error};};
 for(int indirect=0;indirect<2;++indirect){
  auto [token,error]=Open(indirect?".":"/read",indirect);Check(token&&error==123,"actual NDK opendir succeeds on read-only mount with unchanged errno");
  std::set<std::string> found;addr_t record=0;int64_t cursor=0;
  for(;;){struct Guard{uint64_t before=0x123456789abcdef0ULL;Observation value{};uint64_t after=0xfedcba9876543210ULL;} out;
   std::memset(&out.value,0x5a,sizeof(out.value));auto result=Run("guest_directory_read",{token,addr_t(indirect),Address(&out.value)});
   Check(out.before==0x123456789abcdef0ULL&&out.after==0xfedcba9876543210ULL,"NDK dirent decode preserves output guards");
   if(!out.value.pointer){Check(result==read_eof,"actual EOF leaves guest errno unchanged");break;}
   Check(result==read_success,"actual NDK readdir success preserves errno");if(!record)record=out.value.pointer;Check(out.value.pointer==record,"one stable record per live directory stream");
   const auto name=std::string(out.value.name);auto entry=expected.find(name);Check(entry!=expected.end()&&found.insert(name).second,"native enumeration has exactly the real names without duplicates");
   Check(out.value.inode==NativeInode(read/fs::u8path(name)),"actual 64-bit FileId matches independent native handle inode");
   Check(out.value.offset==++cursor,"d_off is a forward-only opaque stream cookie");
   Check(out.value.record_length==((19+name.size()+1+7)&~size_t(7)),"Android record length follows its serialized name footprint");
   Check(out.value.type==((entry->second&FILE_ATTRIBUTE_DIRECTORY)?4u:8u),"normal native entry attributes give actual type");
   if(name!="."&&name!=".."){AndroidStat stat{};const auto path="/read/"+name;Check(Run("guest_directory_stat",{Address(path.c_str()),Address(&stat)})==success&&stat.inode==out.value.inode&&((stat.mode&0170000)==(out.value.type==4?0040000u:0100000u)),"NDK stat and dirent agree on real identity/classification");}
  }
  Check(found.size()==expected.size()&&found.count(u8"é.bin")&&found.count(u8"目录"),"complete native multi-batch/Unicode inventory returned");
  auto unchanged=bunker::test::ReserveAcrossOperation(record,8,[&]{system.SetError(777);Check(system.ReadDir(token)==0&&system.Error()==777,"repeated EOF preserves errno");});Check(unchanged.status==0,"EOF performs no record publication");
  auto retired=bunker::test::ReserveAcrossOperation(record,8,[&]{Check(system.CloseDir(token)==0,"close actually succeeds");});Check(retired.status==1,"close invalidates returned record lifetime before freeing");
  Observation bad{};Check(Run("guest_directory_read",{token,addr_t(indirect),Address(&bad)})==uint64_t(9)<<32&&Run("guest_directory_close",{token,addr_t(indirect)})==Error(9),"stale directory token never reaches a native handle");
 }
 auto a=Open("/read",0),b=Open("/read",1);Observation first{},second{};Run("guest_directory_read",{a.first,0,Address(&first)});Run("guest_directory_read",{b.first,1,Address(&second)});
 Check(a.first!=b.first&&first.pointer!=second.pointer&&first.offset==1&&second.offset==1&&std::string(first.name)==second.name,"independent streams own distinct tokens, cursors and result records");
 auto updated=bunker::test::ReserveAcrossOperation(first.pointer,8,[&]{Check(system.ReadDir(a.first)!=0,"next record genuinely publishes");});Check(updated.status==1,"each successful readdir uses tracked publication");
 auto file=system.FOpen("/read/file-0.bin","rb");Check(file&&file!=a.first&&file!=b.first,"FILE and DIR tokens use a shared non-reused allocator");
 system.SetError(123);Check(system.ReadDir(file)==0&&system.Error()==9&&system.CloseDir(file)==-1&&system.FClose(a.first)==-1,"FILE/DIR wrong-type operations fail without native pointer confusion");Check(!system.FClose(file)&&!system.CloseDir(a.first)&&!system.CloseDir(b.first),"real resource owners remain usable after wrong-type rejection");
 for(auto [path,want]:{std::pair<const char*,int>{nullptr,14},{"",2},{"/missing",2},{"/file",20},{"/read/file-0.bin",20},{"/read/file-0.bin/child",20},{"/read/../outside",2},{"/read/a:stream",22},{"\xc0\xaf",84}}){auto [token,error]=Open(path,0);Check(!token&&error==want,"invalid/nondirectory/unmounted path returns its actual guest error");}
 std::array<char,4096> long_path;long_path.fill('x');Check(Open(long_path.data(),1).second==36,"bounded nonterminated path rejected");
 auto [empty_token,empty_error]=Open("/empty",0);Check(empty_token&&empty_error==123,"empty directory opens as a real stream");std::set<std::string> empty_names;
 for(;;){Observation out{};auto value=Run("guest_directory_read",{empty_token,0,Address(&out)});if(!out.pointer){Check(value==read_eof,"empty directory ends with real EOF");break;}empty_names.insert(out.name);}
 Check(!empty_names.count("file-0.bin")&&empty_names.size()<=2,"empty stream contains only native dot entries if supplied");Check(Run("guest_directory_close",{empty_token,1})==success,"actual NDK closedir succeeds and preserves errno");
 DWORD before=0,after=0;Check(GetProcessHandleCount(GetCurrentProcess(),&before),"independent native handle count available");for(unsigned n=0;n<32;++n){auto token=system.OpenDir("/empty");Check(token&&!system.CloseDir(token),"repeated real directory handle ownership closes");}Check(GetProcessHandleCount(GetCurrentProcess(),&after)&&before==after,"directory streams do not leak native handles");
 // Provider-operation racing is serialized. No returned record is dereferenced
 // after close or while another thread consumes the same stream.
 for(unsigned n=0;n<16;++n){auto token=system.OpenDir("/empty");std::atomic<bool> go{false};addr_t value=0;int read_error=0,closed=7;
  std::thread reader([&]{system.SetError(123);while(!go)std::this_thread::yield();value=system.ReadDir(token);read_error=system.Error();});
  std::thread closer([&]{while(!go)std::this_thread::yield();closed=system.CloseDir(token);});go=true;reader.join();closer.join();
  Check(closed==0&&(read_error==123||(!value&&read_error==9)),"read/close shared lease preserves real handle lifetime");}
 const auto huge=empty/std::wstring(90,L'界');Put(huge);auto unsupported=system.OpenDir("/empty");bool rejected=false;
 for(unsigned n=0;n<4;++n)try{if(!system.ReadDir(unsupported))break;}catch(const std::runtime_error &e){rejected=std::string(e.what()).find("UTF8 capacity")!=std::string::npos;break;}
 Check(rejected,"valid native Unicode name exceeding Android UTF8 capacity is decisive, never false EOF");Check(!system.CloseDir(unsupported),"unsupported entry still has normal owned close");
 for(const auto &p:files)Check(fs::remove(p),"explicit fixture file cleanup");
 Check(fs::remove(read/fs::u8path(u8"目录")),"explicit Unicode directory cleanup");
 for(auto p:{read,empty,outside,root})Check(fs::remove(p),"explicit empty fixture directory cleanup");
 std::printf("Windows directories: %u checks passed; %u actual NDK calls; real multi-batch FileId enumeration, stat/native identity, Unicode, errno/EOF, tracked record lifetime and handle leases\n",checks,ndk_calls);return 0;
 }catch(const std::exception &e){std::fprintf(stderr,"directory gate failed: %s\n",e.what());return 1;}}

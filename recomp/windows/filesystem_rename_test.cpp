#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "filesystem.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <thread>
#include <atomic>
using bunker::windows::FileSystem;
static FileSystem *provider;
static void *Resolve(const char *name){return reinterpret_cast<void*>(provider->Marker(name));}
static uint64_t Inode(const std::filesystem::path &p){HANDLE h=CreateFileW(p.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,nullptr);if(h==INVALID_HANDLE_VALUE)throw std::runtime_error("independent native inode open failed");BY_HANDLE_FILE_INFORMATION info{};auto ok=GetFileInformationByHandle(h,&info);CloseHandle(h);if(!ok)throw std::runtime_error("independent native inode query failed");return uint64_t(info.nFileIndexHigh)<<32|info.nFileIndexLow;}
int main(){try{
 unsigned checks=0;auto Check=[&](bool ok,const char *why){if(!ok)throw std::runtime_error(why);++checks;};namespace fs=std::filesystem;
 const auto parent=fs::canonical(fs::u8path(RENAME_ROOT)),root=parent/("run-"+std::to_string(GetCurrentProcessId())+"-"+std::to_string(GetTickCount64()));Check(root.is_absolute()&&root.parent_path()==parent,"fixture absolute root stays in work directory");fs::create_directory(root);
 const auto rw=root/"rw",ro=root/"ro",other=root/"other";for(auto p:{rw,ro,other})fs::create_directory(p);
 auto Put=[](const fs::path &p){std::ofstream out(p,std::ios::binary);out<<"original payload";if(!out)throw std::runtime_error("fixture write failed");};
 Put(ro/"keep");Put(other/"keep");FileSystem files;provider=&files;files.MountDirectory("/rw",rw,true);files.MountDirectory("/ro",ro);files.MountDirectory("/other",other,true);files.SetWorkingDirectory("/rw");
 recomp::Runtime runtime;files.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));elf_image image{};Check(!elf_load(RENAME_IMAGE,0x57000000,Resolve,&image),"actual NDK rename fixture loads");Check(files.Marker("rename")==files.Marker("closedir")+8,"rename marker append-only");
 auto Run=[&](const char *from,const char *to,int indirect){alignas(16)std::array<uint8_t,65536> stack{};State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(from);s.gpr.x1.qword=reinterpret_cast<addr_t>(to);s.gpr.x2.dword=indirect;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_rename")));Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK rename return PC/SP");return s.gpr.x0.qword;};
 const uint64_t success=uint64_t(123)<<32;auto Error=[](uint32_t n){return uint64_t(n)<<32|0xffffffffU;};
 for(int indirect=0;indirect<2;++indirect){
  Check(Run("/rw/il2cpp","/rw/il2cpp_tmp",indirect)==Error(2)&&!fs::exists(rw/"il2cpp")&&!fs::exists(rw/"il2cpp_tmp"),"reached absent-old quarantine rename returns genuine ENOENT");
  Put(rw/"old");auto id=Inode(rw/"old");Check(Run("old","new",indirect)==success&&!fs::exists(rw/"old")&&Inode(rw/"new")==id,"real file move preserves native identity and errno");
  std::ifstream read(rw/"new",std::ios::binary);std::string bytes((std::istreambuf_iterator<char>(read)),{});Check(bytes=="original payload","renamed file retains exact contents");read.close();Check(fs::remove(rw/"new"),"remove moved fixture file");
  fs::create_directory(rw/"tree");fs::create_directory(rw/"tree"/"nested");Put(rw/"tree"/"nested"/"file");auto dir_id=Inode(rw/"tree"),child_id=Inode(rw/"tree"/"nested"/"file");
  Check(Run("/rw/tree","/rw/tree_tmp",indirect)==success&&!fs::exists(rw/"tree")&&Inode(rw/"tree_tmp")==dir_id&&Inode(rw/"tree_tmp"/"nested"/"file")==child_id,"native directory move preserves whole subtree identities without copy/delete");
  for(auto p:{rw/"tree_tmp"/"nested"/"file",rw/"tree_tmp"/"nested",rw/"tree_tmp"})Check(fs::remove(p),"explicit moved-tree cleanup");
  Put(rw/fs::u8path(u8"é.bin"));Check(Run(u8"/rw/é.bin",u8"/rw/目录.bin",indirect)==success&&fs::exists(rw/fs::u8path(u8"目录.bin")),"real UTF8 path move");Check(fs::remove(rw/fs::u8path(u8"目录.bin")),"Unicode fixture cleanup");
  Put(rw/"keep");Check(Run("/rw/keep","/other/new",indirect)==Error(18)&&fs::exists(rw/"keep")&&!fs::exists(other/"new"),"different virtual mounts fail EXDEV without moving data");
  Check(Run("/ro/keep","/rw/new",indirect)==Error(30)&&Run("/rw/keep","/ro/new",indirect)==Error(30),"both source and destination require writable mounts");
  Check(Run("/rw","/rw/new",indirect)==Error(16)&&Run("/rw/keep","/rw",indirect)==Error(16),"configured mount roots retained");
  Check(Run("/rw/../other/keep","/rw/new",indirect)==Error(13)&&Run("/rw/keep","/rw/../other/new",indirect)==Error(13),"parent traversal denied on both paths");
  Check(Run("/rw/keep","/rw/missing/new",indirect)==Error(2)&&Run("/rw/keep/child","/rw/new",indirect)==Error(20)&&Run("/rw/keep","/rw/keep/child",indirect)==Error(20),"absent and nondirectory parents preserve actual errors");
  Check(Run(nullptr,"/rw/new",indirect)==Error(14)&&Run("/rw/keep",nullptr,indirect)==Error(14)&&Run("","/rw/new",indirect)==Error(2),"NULL/empty rename paths");
  Check(fs::remove(rw/"keep"),"fixture remains removable after failed moves");
 }
 auto Reject=[&](auto operation,const char *why){bool rejected=false;try{operation();}catch(const std::runtime_error &e){rejected=std::string(e.what()).find("rename")!=std::string::npos;}Check(rejected,why);};
 Put(rw/"old");Put(rw/"existing");const auto old_id=Inode(rw/"old"),existing_id=Inode(rw/"existing");Reject([&]{files.Rename("/rw/old","/rw/existing");},"replacement remains decisive unsupported");Check(Inode(rw/"old")==old_id&&Inode(rw/"existing")==existing_id,"unsupported replacement preserves both objects");
 Reject([&]{files.Rename("/rw/old","/rw/new/");},"trailing separator is an explicit unsupported shape");
 HANDLE held=CreateFileW((rw/"old").c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);Check(held!=INVALID_HANDLE_VALUE,"native no-delete-sharing handle opens");Check(Run("/rw/old","/rw/new",0)==Error(13)&&Inode(rw/"old")==old_id&&!fs::exists(rw/"new"),"real sharing failure leaves source intact");CloseHandle(held);Check(Run("/rw/old","/rw/new",1)==success,"closed source is genuinely movable");
 Check(fs::remove(rw/"new")&&fs::remove(rw/"existing"),"file cleanup");
 for(unsigned n=0;n<8;++n){Put(rw/"race");std::atomic<bool> go{false};int result[2]{},error[2]{};std::thread a([&]{files.SetError(123);while(!go)std::this_thread::yield();result[0]=files.Rename("/rw/race","/rw/a");error[0]=files.Error();}),b([&]{files.SetError(124);while(!go)std::this_thread::yield();result[1]=files.Rename("/rw/race","/rw/b");error[1]=files.Error();});go=true;a.join();b.join();Check((result[0]==0&&error[0]==123&&result[1]==-1&&error[1]==2)||(result[1]==0&&error[1]==124&&result[0]==-1&&error[0]==2),"one real source move wins; other gets actual absence with isolated errno");Check(fs::remove(rw/(result[0]==0?"a":"b")),"race fixture cleanup");}
 Check(fs::exists(ro/"keep")&&fs::exists(other/"keep"),"excluded native targets preserved");for(auto p:{ro/"keep",other/"keep",rw,ro,other,root})Check(fs::remove(p),"explicit bounded fixture cleanup");
 std::printf("Windows rename: %u checks passed; actual NDK direct/indirect absent-target moves, ENOENT quarantine, native file/subtree identity, Unicode, errno/mount/share/races\n",checks);return 0;
 }catch(const std::exception &e){std::fprintf(stderr,"rename gate failed: %s\n",e.what());return 1;}}

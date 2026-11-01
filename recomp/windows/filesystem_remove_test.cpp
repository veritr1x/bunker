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
int main(){try{
 unsigned checks=0;auto Check=[&](bool ok,const char *why){if(!ok)throw std::runtime_error(why);++checks;};
 namespace fs=std::filesystem;
 const auto parent=fs::canonical(fs::u8path(REMOVE_ROOT));
 const auto root=parent/("run-"+std::to_string(GetCurrentProcessId())+"-"+std::to_string(GetTickCount64()));
 Check(root.is_absolute()&&root.parent_path()==parent,"isolated absolute fixture directory stays in work root");
 fs::create_directory(root);const auto rw=root/"rw",ro=root/"ro",outside=root/"outside";
 fs::create_directory(rw);fs::create_directory(ro);fs::create_directory(outside);
 auto Put=[](const fs::path &p){std::ofstream f(p,std::ios::binary);f<<"original bytes";if(!f)throw std::runtime_error("fixture write failed");};
 Put(ro/"keep");Put(outside/"keep");Put(root/"mounted-file");
 FileSystem files;provider=&files;files.MountDirectory("/rw",rw,true);files.MountDirectory("/ro",ro);files.MountFile("/file",root/"mounted-file",true);files.SetWorkingDirectory("/rw");
 recomp::Runtime runtime;files.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));elf_image image{};
 Check(!elf_load(REMOVE_IMAGE,0x59000000,Resolve,&image),"actual NDK removal fixture loads");
 Check(files.Marker("unlink")==files.Marker("setvbuf")+8&&files.Marker("rmdir")==files.Marker("unlink")+8,"markers append after setvbuf");
 auto Run=[&](const char *path,int directory,int indirect){
  alignas(16)std::array<uint8_t,65536> stack{};State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(path);s.gpr.x1.dword=directory;s.gpr.x2.dword=indirect;
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
  runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_remove")));
  Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK remove return PC/SP");return s.gpr.x0.qword;
 };
 const uint64_t success=uint64_t(123)<<32;auto Error=[](uint32_t e){return uint64_t(e)<<32|0xffffffffU;};
 for(int indirect=0;indirect<2;++indirect){
  Put(rw/"plain");Check(Run("/rw/plain",0,indirect)==success&&!fs::exists(rw/"plain"),"unlink removes real file and preserves success errno");
  fs::create_directory(rw/"empty");Check(Run("empty",1,indirect)==success&&!fs::exists(rw/"empty"),"relative rmdir removes actual empty directory");
  fs::create_directory(rw/"full");Put(rw/"full"/"child");
  Check(Run("/rw/full",1,indirect)==Error(39)&&fs::exists(rw/"full"/"child"),"nonempty rmdir reports ENOTEMPTY without recursive deletion");
  Check(Run("/rw/full",0,indirect)==Error(21)&&fs::is_directory(rw/"full"),"unlink refuses directory with EISDIR");
  Check(Run("/rw/full/child",1,indirect)==Error(20)&&fs::exists(rw/"full"/"child"),"rmdir refuses regular file with ENOTDIR");
  Check(Run("/rw/full/child/",0,indirect)==Error(20),"trailing slash on regular file is ENOTDIR");
  Check(Run("/rw/full/child/sub",0,indirect)==Error(20),"file ancestor is ENOTDIR");
  Check(Run("/rw/full/.",1,indirect)==Error(22)&&fs::exists(rw/"full"/"child"),"rmdir dot does not normalize into deleting its parent");
  Check(Run("/rw/full/child",0,indirect)==success&&Run("/rw/full/",1,indirect)==success,"guest owns recursive walk; each remove remains single-entry");
  for(int directory=0;directory<2;++directory){
   Check(Run("/rw/missing",directory,indirect)==Error(2),"missing target is a genuine ENOENT failure");
   Check(Run(nullptr,directory,indirect)==Error(14)&&Run("",directory,indirect)==Error(2),"NULL and empty paths retain Android errors");
   Check(Run("/rw",directory,indirect)==Error(16)&&fs::is_directory(rw),"configured mount root is protected with EBUSY");
   Check(Run("/ro/keep",directory,indirect)==Error(30)&&fs::exists(ro/"keep"),"read-only mount cannot remove contents");
   Check(Run("/rw/../outside/keep",directory,indirect)==Error(13)&&fs::exists(outside/"keep"),"parent traversal cannot become a write outside the mount");
   Check(Run("/outside/keep",directory,indirect)==Error(2)&&fs::exists(outside/"keep"),"unmounted file remains inaccessible");
   Check(Run("/rw/file:alias",directory,indirect)==Error(22),"ADS alias rejected");
  }
  Check(Run("/file",0,indirect)==Error(16)&&fs::exists(root/"mounted-file"),"explicit mounted file capability retained");
  Put(rw/fs::u8path(u8"é.bin"));Check(Run(u8"/rw/é.bin",0,indirect)==success&&!fs::exists(rw/fs::u8path(u8"é.bin")),"UTF8 file path removes its actual Unicode target");
  fs::create_directory(rw/fs::u8path(u8"目录"));Check(Run(u8"/rw/目录",1,indirect)==success&&!fs::exists(rw/fs::u8path(u8"目录")),"UTF8 directory path removes actual Unicode directory");
 }
 std::array<char,4096> long_name;long_name.fill('x');Check(Run(long_name.data(),0,0)==Error(36),"unterminated bounded path produces ENAMETOOLONG");
 Put(rw/"locked");HANDLE locked=CreateFileW((rw/"locked").c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
 Check(locked!=INVALID_HANDLE_VALUE,"independent non-delete-sharing file handle opens");
 Check(Run("/rw/locked",0,0)==Error(13)&&fs::exists(rw/"locked"),"actual native sharing failure maps to EACCES; open-unlink equivalence not invented");CloseHandle(locked);
 Check(Run("/rw/locked",0,0)==success,"closed file becomes genuinely removable");
 unsigned link_checks=0;Put(outside/"target");
 if(CreateSymbolicLinkW((rw/"link").c_str(),(outside/"target").c_str(),2)){
  Check(Run("/rw/link",0,0)==Error(95)&&fs::exists(outside/"target"),"final symbolic link cannot be followed or removed as ordinary file");
  Check(DeleteFileW((rw/"link").c_str()),"fixture removes only its created symbolic link");++link_checks;
 }else Check(GetLastError()==ERROR_PRIVILEGE_NOT_HELD,"symbolic link fixture either runs or reports actual privilege absence");
 // A concurrent duplicate removal has exactly one success, one genuine absence.
 for(unsigned n=0;n<8;++n){Put(rw/"race");std::atomic<bool> go{false};int result[2]{},error[2]{};std::thread workers[2];
  for(unsigned i=0;i<2;++i)workers[i]=std::thread([&,i]{files.SetError(123+int(i));while(!go)std::this_thread::yield();result[i]=files.Unlink("/rw/race");error[i]=files.Error();});
  go=true;for(auto &worker:workers)worker.join();
  Check((result[0]==0&&error[0]==123&&result[1]==-1&&error[1]==2)||(result[1]==0&&error[1]==124&&result[0]==-1&&error[0]==2),"concurrent removal and errno are serialized per actual call/thread");
 }
 Check(fs::exists(ro/"keep")&&fs::exists(outside/"keep")&&fs::exists(outside/"target"),"all excluded fixture targets preserved");
 // Every cleanup target is explicitly constructed under the checked fixture root.
 for(auto p:{ro/"keep",outside/"keep",outside/"target",root/"mounted-file"})Check(fs::remove(p),"explicit fixture file cleanup");
 for(auto p:{rw,ro,outside,root})Check(fs::remove(p),"explicit empty fixture directory cleanup");
 std::printf("Windows unlink/rmdir: %u checks passed; real NDK direct/indirect deletion, errno, containment, Unicode, native sharing, race; symbolic-link checks=%u\n",checks,link_checks);return 0;
 }catch(const std::exception &e){std::fprintf(stderr,"removal gate failed: %s\n",e.what());return 1;}}

#include "filesystem.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <thread>
#include <vector>
#include <windows.h>
#include <aclapi.h>
#include "../fastaes/elfload.h"
#include "traces.h"

namespace fs=std::filesystem;
using bunker::windows::FileSystem;
using bunker::windows::AndroidStat;
static FileSystem *provider;
static void *Resolve(const char *name){return reinterpret_cast<void*>(provider->Marker(name));}
static std::vector<uint8_t> Security(const fs::path &path){
  DWORD size=0;GetFileSecurityW(path.c_str(),OWNER_SECURITY_INFORMATION|DACL_SECURITY_INFORMATION,nullptr,0,&size);
  std::vector<uint8_t> bytes(size);
  if(!size||!GetFileSecurityW(path.c_str(),OWNER_SECURITY_INFORMATION|DACL_SECURITY_INFORMATION,bytes.data(),size,&size))throw std::runtime_error("independent security descriptor query failed");
  return bytes;
}
static bool Private(const fs::path &path,bool protected_acl){
  auto bytes=Security(path);auto sd=static_cast<PSECURITY_DESCRIPTOR>(bytes.data());
  HANDLE token=nullptr;if(!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token))return false;
  DWORD size=0;GetTokenInformation(token,TokenUser,nullptr,0,&size);std::vector<uint8_t> user(size);
  auto queried=GetTokenInformation(token,TokenUser,user.data(),size,&size);CloseHandle(token);if(!queried)return false;
  const auto sid=reinterpret_cast<TOKEN_USER*>(user.data())->User.Sid;
  PSID owner=nullptr;BOOL defaulted=FALSE,present=FALSE;PACL acl=nullptr;
  SECURITY_DESCRIPTOR_CONTROL control=0;DWORD revision=0;
  if(!GetSecurityDescriptorOwner(sd,&owner,&defaulted)||!EqualSid(owner,sid)||
     !GetSecurityDescriptorDacl(sd,&present,&acl,&defaulted)||!present||!acl||acl->AceCount!=1||
     !GetSecurityDescriptorControl(sd,&control,&revision)||
     (protected_acl&&!(control&SE_DACL_PROTECTED)))return false;
  void *raw=nullptr;if(!GetAce(acl,0,&raw))return false;
  const auto ace=static_cast<ACCESS_ALLOWED_ACE*>(raw);
  return ace->Header.AceType==ACCESS_ALLOWED_ACE_TYPE&&EqualSid(&ace->SidStart,sid)&&
    ace->Mask==FILE_ALL_ACCESS&&(!protected_acl||
      (ace->Header.AceFlags&(OBJECT_INHERIT_ACE|CONTAINER_INHERIT_ACE))==(OBJECT_INHERIT_ACE|CONTAINER_INHERIT_ACE));
}
int main(){
  unsigned checks=0;auto require=[&](bool good,const char *message){if(!good)throw std::runtime_error(message);++checks;};
  const auto root=fs::u8path(MKDIR_TEST_ROOT)/("run-"+std::to_string(GetCurrentProcessId())+"-"+std::to_string(GetTickCount64()));
  fs::create_directories(root/"rw");fs::create_directory(root/"ro");fs::create_directory(root/"rw/existing");
  std::ofstream(root/"rw/file")<<"existing file";
  FileSystem files;provider=&files;files.MountDirectory("/rw",root/"rw",true);files.MountDirectory("/ro",root/"ro");files.SetWorkingDirectory("/rw");
  recomp::Runtime runtime;files.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));elf_image image;
  require(elf_load(MKDIR_GUEST_IMAGE,0x5c000000,Resolve,&image)==0,"load strict NDK mkdir and stat callers");
  auto invoke=[&](const char *name,std::initializer_list<addr_t> arguments){
    alignas(16) static thread_local std::array<uint8_t,65536> stack;
    State s{};Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2};size_t at=0;
    for(auto argument:arguments)(s.gpr.*registers[at++]).qword=argument;
    s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
    auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));if(!entry)throw std::runtime_error("missing NDK export");
    runtime.Run(s,entry);if(s.gpr.pc.qword!=0xfeedffff||s.gpr.sp.qword!=reinterpret_cast<addr_t>(stack.data()+stack.size()))throw std::runtime_error("NDK caller PC/SP corrupted");
    return s.gpr.x0.qword;
  };
  constexpr uint64_t ok=uint64_t(123)<<32;auto error=[](uint32_t number){return(uint64_t(number)<<32)|0xffffffffU;};
  auto mkdir=[&](const char *path,uint32_t mode){return invoke("guest_mkdir",{reinterpret_cast<addr_t>(path),mode});};
  for(auto mode:{0700U,0755U,0777U}){
    auto leaf="mode-"+std::to_string(mode);auto guest="/rw/"+leaf;
    require(mkdir(guest.c_str(),mode)==ok&&fs::is_directory(root/"rw"/leaf),"actual NDK mkdir creates exactly one real directory and preserves errno");
    require(Private(root/"rw"/leaf,true),"independent Windows owner/protected inheritable current-user-only full-control DACL");
    struct Guard{uint64_t before=0x1122334455667788ULL;AndroidStat stat{};uint64_t after=0x8877665544332211ULL;} guard;
    require(invoke("guest_mkdir_stat",{reinterpret_cast<addr_t>(guest.c_str()),reinterpret_cast<addr_t>(&guard.stat)})==ok&&
      guard.before==0x1122334455667788ULL&&guard.after==0x8877665544332211ULL&&guard.stat.mode==(0040000|0755),"tracked NDK128-byte stat preserves canaries and reports existing virtual directory metadata");
    auto security=Security(root/"rw"/leaf);
    require(mkdir(guest.c_str(),mode)==error(17)&&Security(root/"rw"/leaf)==security,"existing directory EEXIST leaves owner and ACL byte-identical");
  }
  auto existing=Security(root/"rw/existing"),file_security=Security(root/"rw/file");
  require(mkdir("existing",0755)==error(17)&&Security(root/"rw/existing")==existing,"preexisting host directory ACL is never changed");
  require(mkdir("file",0755)==error(17)&&Security(root/"rw/file")==file_security,"existing regular file EEXIST is never altered");
  require(mkdir("missing/child",0755)==error(2)&&!fs::exists(root/"rw/missing"),"missing parent ENOENT without implicit parent creation");
  require(mkdir("file/child",0755)==error(20)&&fs::is_regular_file(root/"rw/file"),"regular file ancestor ENOTDIR");
  require(mkdir("/ro/child",0755)==error(30)&&!fs::exists(root/"ro/child"),"read-only mount EROFS");
  require(mkdir("/unknown/child",0755)==error(2),"unmounted path ENOENT");
  require(mkdir("../escaped",0755)==error(13)&&!fs::exists(root/"escaped"),"parent traversal EACCES without native escape");
  require(mkdir("missing/../skipped",0755)==error(13)&&!fs::exists(root/"rw/skipped"),"parent traversal cannot normalize away a missing ancestor");
  require(mkdir("NUL",0755)==error(22)&&mkdir("bad.",0755)==error(22)&&mkdir("C:\\Windows\\new",0755)==error(22),"native device/alias/host paths explicitly rejected");
  require(mkdir("",0755)==error(2)&&mkdir(nullptr,0755)==error(14),"empty path ENOENT and null path EFAULT");
  std::string long_path(4096,'a');require(mkdir(long_path.c_str(),0755)==error(36),"overlong path ENAMETOOLONG");
  for(auto mode:{0U,0600U,01777U,040755U})require(mkdir("unsupported",mode)==error(95)&&!fs::exists(root/"rw/unsupported"),"unsupported restrictive/special mode cannot create any directory");
  require(mkdir("parent",0755)==ok&&mkdir("parent/child",0700)==ok&&fs::is_directory(root/"rw/parent/child"),"explicit parent-first recursive helper pattern");
  auto fd=files.Open("parent/child/bytes",bunker::windows::linux_flags::write_only|bunker::windows::linux_flags::create,0600);
  require(fd>=0&&files.Close(fd)==0&&Private(root/"rw/parent/child/bytes",false),"new files inherit the real private directory DACL");
  require(mkdir("caf\xc3\xa9",0755)==ok&&fs::is_directory(root/"rw"/fs::u8path("caf\xc3\xa9")),"real Unicode directory path");
  require(mkdir("trailing/",0755)==ok&&fs::is_directory(root/"rw/trailing"),"trailing slash directory creation");
  std::atomic<unsigned> wins{0},exists{0},failures{0};std::thread a([&]{auto r=mkdir("race",0755);if(r==ok)++wins;else if(r==error(17))++exists;else ++failures;});
  std::thread b([&]{auto r=mkdir("race",0755);if(r==ok)++wins;else if(r==error(17))++exists;else ++failures;});a.join();b.join();
  require(wins==1&&exists==1&&failures==0&&Private(root/"rw/race",true),"concurrent translated creators produce one private directory and one EEXIST with per-thread errno");
  std::printf("Rooted mkdir: %u checks passed; actual NDK mkdir/stat, native creation and independent Windows owner/DACL proof\n",checks);
  std::printf("Preserved test artifacts: %s\n",root.u8string().c_str());
}

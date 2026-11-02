#include "package_test_session.h"
#include <atomic>
#include <map>
#include <mutex>
#ifdef _WIN32
#include "filesystem.h"
#include "unicode.h"
#include <filesystem>
#include <windows.h>
#endif
using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};
void Check(bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;}
AndroidContextConfig Config(){AndroidContextConfig c;c.package_name=kPackageName;c.target_sdk=kTargetSdk;c.activity_class=kLaunchActivity;return c;}
addr_t Get(Session &h,addr_t context,bool single,unsigned mode){return h.run("obb_get",{h.host.EnvAddress(),context,single,mode});}
addr_t Element(Session &h,addr_t array,int index){return h.run("obb_element",{h.host.EnvAddress(),array,static_cast<uint32_t>(index)});}
int Length(Session &h,addr_t array){return static_cast<int32_t>(h.run("obb_array_length",{h.host.EnvAddress(),array}));}
std::u16string Path(Session &h,addr_t file,unsigned mode=0){return h.text(h.run("obb_path",{h.host.EnvAddress(),file,mode}));}
void Error(Session &h,const char *type){Check(h.host.PendingException().find(type)!=std::string::npos,"expected named Java failure");h.host.ClearException();}
}
int main(){try{
  elf_image image{};Check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual NDK OBB fixture loads");
  {Session h(image);auto config=Config();AndroidContext context(h.host,config);for(unsigned m=0;m<3;++m)for(bool single:{false,true}){Check(!Get(h,context.Activity(),single,m),"unset OBB catalog never supplies a directory or empty array");Error(h,"UnsupportedOperationException");}}
  {Session h(image);auto config=Config();config.external_obb_volumes=std::vector<ExternalObbVolume>{};unsigned calls=0;config.prepare_obb_directory=[&](const auto &){++calls;return 0;};AndroidContext context(h.host,config);addr_t previous=0;for(unsigned m=0;m<3;++m){auto array=Get(h,context.Activity(),false,m);Check(array&&Length(h,array)==0&&h.call(232,array)==1,"explicit closed zero-volume catalog returns real typed empty caller-local File[]");Check(!previous||!h.call(24,array,previous),"each getter publishes a fresh mutable array");previous=array;Check(!Get(h,context.Activity(),true,m)&&h.host.PendingException().empty(),"legacy getter returns null for zero catalog entries");}Check(!calls,"closed zero catalog performs no invented filesystem operation");}
  {Session h(image);auto config=Config();config.external_obb_volumes=std::vector<ExternalObbVolume>{{u"/storage/unavailable",false}};AndroidContext context(h.host,config);for(unsigned m=0;m<3;++m){auto array=Get(h,context.Activity(),false,m);Check(array&&Length(h,array)==1&&!Element(h,array,0)&&!Get(h,context.Activity(),true,m)&&h.host.PendingException().empty(),"explicit unavailable volume preserves one null slot without inventing backing or requiring a verifier");}}
  {Session h(image);auto config=Config();config.external_obb_volumes=std::vector<ExternalObbVolume>{{u"/storage/off",false},{u"/storage/one",true},{u"/storage/two",true}};
    const auto one=ObbDirectoryPath(u"/storage/one",config.package_name),two=ObbDirectoryPath(u"/storage/two",config.package_name);std::atomic<int> response{13};std::atomic<unsigned> calls{0};std::atomic<bool> join{false};addr_t shared=0;
    config.prepare_obb_directory=[&](const std::u16string &path){++calls;Check(path==one||path==two,"verifier sees only available catalog-derived package paths");
      if(join.exchange(false)){std::exception_ptr failed;std::thread child([&]{try{addr_t env=0;State s{};s.gpr.x0.qword=h.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,s);auto array=h.run("obb_get",{env,shared,0,2});Check(array&&Length(h,array)==3,"backing callback may attach/join a real JNI worker that reenters OBB getter");s={};s.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,s);}catch(...){failed=std::current_exception();}});child.join();if(failed)std::rethrow_exception(failed);}
      return path==two?response.load():0;};
    addr_t retained_array=0,retained_file=0,weak_array=0,weak_file=0,path_string=0;
    {AndroidContext context(h.host,config);(*config.external_obb_volumes)[1].root=u"/caller-mutated";shared=h.host.NewGlobalReference(context.Activity());h.call(19,512);
      for(unsigned m=0;m<3;++m){auto before=calls.load();auto array=Get(h,context.Activity(),false,m);Check(array&&Length(h,array)==3&&!Element(h,array,0)&&!Element(h,array,2),"unavailable and failed volumes preserve null slots and total order");auto file=Element(h,array,1);Check(file&&Path(h,file,m)==one&&calls==before+2,"available slot exposes exact File path after verifier success");Check(!Get(h,context.Activity(),true,m)&&h.host.PendingException().empty(),"legacy getter uses first null slot rather than first successful secondary");
        h.run("obb_replace",{h.host.EnvAddress(),array,0,file});auto fresh=Get(h,context.Activity(),false,m);Check(!Element(h,fresh,0)&&Length(h,fresh)==3&&!h.call(24,array,fresh),"caller array mutation cannot alter immutable configured volume snapshot");
        h.run("obb_replace",{h.host.EnvAddress(),fresh,1,h.host.NewString(u"not a File")});Error(h,"ArrayStoreException");auto still=Element(h,fresh,1);Check(still&&Path(h,still)==one,"failed typed store preserves backed File element");
      }
      response=0;auto array=Get(h,context.Activity(),false,0),file=Element(h,array,2);Check(file&&Path(h,file)==two,"availability is reverified rather than caching earlier failure");response=13;auto unavailable=Get(h,context.Activity(),false,0);Check(!Element(h,unavailable,2),"later verifier failure removes current slot without returning a cached File");
      auto first=Element(h,array,1);retained_array=h.host.NewGlobalReference(array);retained_file=h.host.NewGlobalReference(first);weak_array=h.call(226,array);weak_file=h.call(226,first);path_string=h.host.NewGlobalReference(h.run("obb_path",{h.host.EnvAddress(),first,2}));
      join=true;Check(Get(h,context.Activity(),false,0)&&!join,"verifier executes outside JNI/provider/cache locks");response=-1;Check(!Get(h,context.Activity(),false,0),"invalid negative verifier status cannot publish success");Error(h,"IllegalStateException");response=13;
      h.call(20);h.host.DeleteGlobalReference(shared);
    }
    Check(Length(h,retained_array)==3&&Path(h,retained_file,1)==one&&h.text(path_string)==one,"File/array/String graph survives Context wrapper and creator local-frame teardown");
    h.host.DeleteGlobalReference(retained_array);Check(h.call(24,weak_array,0)&&!h.call(24,weak_file,0),"array retires without keeping a hidden root while explicit File global survives");h.host.DeleteGlobalReference(retained_file);Check(h.call(24,weak_file,0)&&h.text(path_string)==one,"File retires independently while an actual String global retains path value");h.host.DeleteGlobalReference(path_string);h.call(227,weak_array);h.call(227,weak_file);
  }
  {Session h(image);auto config=Config();config.external_obb_volumes=std::vector<ExternalObbVolume>{{u"/storage/one",true}};AndroidContext context(h.host,config);Check(!Get(h,context.Activity(),false,0),"available catalog without verifier remains unsupported");Error(h,"UnsupportedOperationException");}
  for(const auto &root:{u"relative",u"/storage/../escape",u"/storage//bad",u"/storage/trailing/",u"/"}){bool rejected=false;try{ObbDirectoryPath(root,kPackageName);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"noncanonical catalog root rejected before filesystem work");}
#ifdef _WIN32
  namespace fs=std::filesystem;auto base=fs::absolute(fs::u8path(OBB_ROOT));fs::create_directories(base/"one");fs::create_directories(base/"two");fs::create_directories(base/"conflict");FileSystem files;files.MountDirectory("/storage/one",base/"one",true);files.MountDirectory("/storage/two",base/"two",true);files.MountDirectory("/storage/conflict",base/"conflict",true);
  auto config=Config();config.external_obb_volumes=std::vector<ExternalObbVolume>{{u"/storage/one",true},{u"/storage/missing",true},{u"/storage/two",true}};auto prepare=MakeObbDirectoryPreparer(files,*config.external_obb_volumes,config.package_name);config.prepare_obb_directory=prepare;
  const auto one=ObbDirectoryPath(u"/storage/one",config.package_name),two=ObbDirectoryPath(u"/storage/two",config.package_name);Check(!prepare(one)&&!prepare(two),"real FS creates/verifies exact OBB descendants under owned mounted roots");AndroidStat stat{};Check(!files.Stat(Utf8(one).c_str(),&stat)&&(stat.mode&0170000)==0040000&&fs::is_directory(base/"one"/"Android"/"obb"/Utf8(config.package_name)),"OBB File reflects actual rooted native directory");
  Check(prepare(u"/storage/one/arbitrary")==22&&!fs::exists(base/"one"/"arbitrary"),"adapter cannot create arbitrary caller paths");Check(prepare(ObbDirectoryPath(u"/storage/missing",config.package_name))==2,"unmounted root produces actual ENOENT without fabricated path");
  {Session h(image);AndroidContext context(h.host,config);for(unsigned m=0;m<3;++m){auto array=Get(h,context.Activity(),false,m);Check(array&&Length(h,array)==3&&!Element(h,array,1)&&Path(h,Element(h,array,0),m)==one&&Path(h,Element(h,array,2),m)==two,"actual NDK getter exposes only real mounted directories with missing root null in-place");Check(Path(h,Get(h,context.Activity(),true,m),m)==one,"real legacy getter returns primary slot");}}
  FileSystem readonly;readonly.MountDirectory("/storage/one",base/"one",false);auto ro=MakeObbDirectoryPreparer(readonly,{{u"/storage/one",true}},config.package_name);Check(ro(one)==30,"read-only mount never claims writable OBB directory despite existing native path");
  Check(files.Mkdir("/storage/conflict/Android",0700)==0,"real conflict ancestor created");auto fd=files.Open("/storage/conflict/Android/obb",linux_flags::write_only|linux_flags::create,0600);Check(fd>=0&&!files.Close(fd),"real file blocks OBB parent directory");auto conflict=MakeObbDirectoryPreparer(files,{{u"/storage/conflict",true}},config.package_name);Check(conflict(ObbDirectoryPath(u"/storage/conflict",config.package_name))==20,"existing ordinary file cannot masquerade as OBB directory");
  auto unavailable=MakeObbDirectoryPreparer(files,{{u"/storage/one",false}},config.package_name);Check(unavailable(one)==22,"explicit unavailable root is excluded from preparer whitelist");
  // Change real backing after successful getter: no stale File is returned.
  Check(!files.Rmdir(Utf8(one).c_str()),"actual package OBB directory removed");fd=files.Open(Utf8(one).c_str(),linux_flags::write_only|linux_flags::create,0600);Check(fd>=0&&!files.Close(fd),"real regular file replaces previously verified OBB directory");
  {Session h(image);AndroidContext context(h.host,config);auto array=Get(h,context.Activity(),false,2);Check(array&&Length(h,array)==3&&!Element(h,array,0)&&!Get(h,context.Activity(),true,0)&&Path(h,Element(h,array,2))==two,"real backing failure preserves null primary and secondary directory; legacy does not search ahead");}
#endif
  std::printf("OBB Context: %u checks; actual NDK direct/V/A ordered typed arrays, optional closed catalog, verified File paths and reference lifetimes; portable verifier injected, Windows backed by real mounted FS\n",checks.load());
}catch(const std::exception &e){std::fprintf(stderr,"OBB Context: %s\n",e.what());return 1;}}

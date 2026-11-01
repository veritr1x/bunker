#include "java_native_libraries.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <exception>
#include <stdexcept>
#include <thread>
using bunker::windows::JavaNativeLibraries;
using bunker::jni::Host;
namespace {
unsigned checks=0;
void Check(bool value,const char *why){++checks;if(!value)throw std::runtime_error(why);}
template<class F>void Reject(F f,const char *why){bool failed=false;try{f();}catch(const std::invalid_argument&){failed=true;}Check(failed,why);}
addr_t Call(Host&h,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){
  State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;
  h.InvokeEnv(slot,s);return s.gpr.x0.qword;
}
addr_t Find(Host&h,const char*n){return Call(h,6,(addr_t)n);}
addr_t Method(Host&h,addr_t clazz,const char*n,const char*sig){return Call(h,33,clazz,(addr_t)n,(addr_t)sig);}
addr_t Loader(Host&h,addr_t clazz){return Call(h,34,clazz,Method(h,Find(h,"java/lang/Class"),"getClassLoader","()Ljava/lang/ClassLoader;"));}
void Attach(Host&h){addr_t env=0;State s{};s.gpr.x0.qword=h.VmAddress();s.gpr.x1.qword=(addr_t)&env;h.InvokeVm(4,s);if(s.gpr.x0.qword||!env)throw std::runtime_error("JNI attach failed");}
void Detach(Host&h){State s{};s.gpr.x0.qword=h.VmAddress();h.InvokeVm(5,s);if(s.gpr.x0.qword)throw std::runtime_error("JNI detach failed");}
}
int main(int argc,char**argv){
  recomp::Runtime runtime;Host host([](addr_t){return false;});host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
  host.DefineClass("test/App");host.DefineClass("test/OtherLoader",{},"java/lang/ClassLoader");
  auto app=Find(host,"test/App"),loader=Loader(host,app),bootstrap=Loader(host,Find(host,"java/lang/String"));
  auto other=host.NewInstance("java/lang/ClassLoader"),subclass=host.NewInstance("test/OtherLoader");
  JavaNativeLibraries::Config config{loader,app,{{u"unity",u"/data/app/bunker/lib/arm64/libunity.so"},{u"il2cpp",u"/data/app/bunker/lib/arm64/libil2cpp.so"},
    {u"sound_\U0001f600",u"/data/native/libsound_\U0001f600.so"}}};
  for(auto pair:std::initializer_list<std::pair<std::u16string,std::u16string>>{
      {u"",u"/native/lib.so"},{u"..",u"/native/lib...so"},{u"a/b",u"/native/liba/b.so"},
      {u"a",u"relative/liba.so"},{u"a",u"/native/../liba.so"},{u"a",u"/native//liba.so"},
      {u"a",u"/native/./liba.so"},{u"a",u"C:\\native\\liba.so"},{u"a",u"/native/libb.so"},
      {u"a",u"/base.apk!/lib/liba.so"},{std::u16string{u'a',0},u"/native/liba.so"},
      {std::u16string{char16_t(0xd800)},u"/native/liba.so"}}){
    auto invalid=config;invalid.libraries={{pair.first,pair.second}};
    Reject([&]{JavaNativeLibraries value(host,invalid);},"invalid catalog name/path rejected");
    Check(host.PendingException().empty(),"invalid path config does not manufacture Java exceptions");
  }
  auto duplicate=config;duplicate.libraries.push_back(config.libraries[0]);
  Reject([&]{JavaNativeLibraries value(host,duplicate);},"duplicate logical module name rejected");
  for(auto wrong:{addr_t(0),other,bootstrap,host.NewString(u"not a loader")}){
    auto invalid=config;invalid.application_loader=wrong;
    Reject([&]{JavaNativeLibraries value(host,invalid);},"non-app loader binding rejected");
    Check(host.PendingException().empty(),"valid-object identity rejection leaves no pending exception");
  }
  auto invalid=config;invalid.application_class=Find(host,"java/lang/String");invalid.application_loader=bootstrap;
  Reject([&]{JavaNativeLibraries value(host,invalid);},"bootstrap class cannot prove app loader");
  invalid=config;invalid.application_class=host.NewString(u"not a class");
  Reject([&]{JavaNativeLibraries value(host,invalid);},"class reference type checked");
  Check(host.PendingException().find("IllegalArgumentException")!=std::string::npos,"wrong class Java exception retained");host.ClearException();
  invalid=config;invalid.application_class=Find(host,"test/App");host.DeleteLocalReference(invalid.application_class);
  Reject([&]{JavaNativeLibraries value(host,invalid);},"stale class reference rejected");
  Check(host.PendingException().find("IllegalArgumentException")!=std::string::npos,"stale class exception retained");host.ClearException();
  host.ThrowException("java/lang/UnsupportedOperationException",u"preserve me");auto pending=host.PendingException();
  auto pending_object=Call(host,15);
  Reject([&]{JavaNativeLibraries value(host,config);},"preexisting exception forbids constructor identity calls");
  Check(host.PendingException()==pending,"constructor never clears/replaces preexisting exception");
  Check(Call(host,24,pending_object,Call(host,15))==1,"constructor preserves the exact exception object identity");host.ClearException();
  auto catalog=std::make_unique<JavaNativeLibraries>(host,config);
  Check(catalog->Active(),"catalog active after complete installation");
  Reject([&]{JavaNativeLibraries value(host,config);},"duplicate service cannot overwrite existing handler");
  Check(catalog->Active()&&host.PendingException().empty(),"duplicate service preserves original and exception state");
  auto method=Method(host,Find(host,"java/lang/ClassLoader"),"findLibrary","(Ljava/lang/String;)Ljava/lang/String;");
  Check(method!=0,"exact ClassLoader method descriptor");
  elf_image image{};Check(!elf_load(JAVA_LIBRARIES_IMAGE,0x5d000000,nullptr,&image),"actual NDK caller image");
  auto entry=(addr_t)elf_symbol(&image,"guest_find_library");Check(entry!=0,"actual NDK caller export");
  auto run=[&](addr_t env,addr_t receiver,addr_t name,addr_t mode){
    alignas(16)std::array<uint8_t,65536> stack{};State s{};s.gpr.x0.qword=env;s.gpr.x1.qword=receiver;
    s.gpr.x2.qword=method;s.gpr.x3.qword=name;s.gpr.x4.qword=mode;s.gpr.sp.qword=(addr_t)(stack.data()+stack.size());
    s.gpr.x30.qword=0xfeedfff0;runtime.Run(s,entry);return s.gpr.x0.qword;
  };
  auto main_env=host.EnvAddress(),global=host.NewGlobalReference(loader),global_class=host.NewGlobalReference(app);
  if(argc>1){
    if(!std::strcmp(argv[1],"--fatal-detached")){auto name=host.NewString(u"unity");Detach(host);run(main_env,global,name,0);return 99;}
    std::thread worker([&]{Attach(host);run(main_env,global,host.NewString(u"unity"),0);});worker.join();return 99;
  }
  for(unsigned mode=0;mode<4;++mode){
    for(auto &library:config.libraries){
      auto name=host.NewString(library.name);auto result=run(host.EnvAddress(),loader,name,mode);
      Check(result&&host.StringValue(result)==library.guest_path,"NDK direct/V/A/stack-V exact configured path");
      Check(Call(host,232,result)==1,"returned path is caller-local, not provider global");
      host.DeleteLocalReference(result);
      auto second=run(host.EnvAddress(),loader,name,mode);Check(second&&host.StringValue(second)==library.guest_path,"deleting result does not invalidate catalog string");
      host.DeleteLocalReference(second);host.DeleteLocalReference(name);
    }
    for(auto name:{u"missing",u"",u"libil2cpp.so",u"../il2cpp",u"il2cpp/other"}){
      Check(!run(host.EnvAddress(),loader,host.NewString(name),mode)&&host.PendingException().empty(),"unavailable name returns null without exception");
      Check(catalog->Active(),"unavailable lookup does not revoke service");
    }
    auto nul=host.NewString(std::u16string{u'i',0,u'l'});Check(!run(host.EnvAddress(),loader,nul,mode),"embedded NUL logical name never becomes a configured path");
    for(auto receiver:{bootstrap,other,subclass}){
      Check(!run(host.EnvAddress(),receiver,host.NewString(u"unity"),mode)&&host.PendingException().empty(),"base/non-app/derived loaders preserve default null");
      Check(!run(host.EnvAddress(),receiver,0,mode)&&host.PendingException().empty(),"base loader does not apply app-only null-name semantics");
    }
    Check(!run(host.EnvAddress(),loader,0,mode)&&host.PendingException().find("NullPointerException")!=std::string::npos,"app null-name matches mapLibraryName NPE");host.ClearException();
    auto weak=Call(host,226,host.NewString(u"orphan")); // Retire the only local below.
    auto orphan=host.NewString(u"orphan2"),cleared=Call(host,226,orphan);host.DeleteLocalReference(orphan);
    Check(!run(host.EnvAddress(),loader,cleared,mode)&&host.PendingException().find("NullPointerException")!=std::string::npos,"cleared weak name is null");host.ClearException();Call(host,227,cleared);Call(host,227,weak);
    auto bad=host.NewInstance("java/lang/Object");
    Check(!run(host.EnvAddress(),loader,bad,mode)&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"name argument type checked by JNI");host.ClearException();
    Check(!run(host.EnvAddress(),bad,host.NewString(u"unity"),mode)&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"receiver type checked");host.ClearException();
    Check(!run(host.EnvAddress(),0,host.NewString(u"unity"),mode)&&host.PendingException().find("NullPointerException")!=std::string::npos,"null receiver checked");host.ClearException();
    auto dead=host.NewString(u"unity");host.DeleteLocalReference(dead);
    Check(!run(host.EnvAddress(),loader,dead,mode)&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"deleted argument reference checked");host.ClearException();
    auto valid=host.NewString(u"unity");host.ThrowException("java/lang/IllegalStateException",u"keep this");pending=host.PendingException();
    Check(!run(host.EnvAddress(),loader,valid,mode)&&host.PendingException()==pending,"lookup leaves preexisting exception unchanged");host.ClearException();
    Call(host,19,8);auto promoted=run(host.EnvAddress(),loader,valid,mode);promoted=Call(host,20,promoted);
    Check(host.StringValue(promoted)==config.libraries[0].guest_path,"path survives local frame promotion");
  }
  auto creator_name=host.NewString(u"unity"),creator_loader=host.NewLocalReference(loader),creator_result=run(main_env,loader,creator_name,0);
  std::exception_ptr failure;addr_t dead_worker_result=0;
  std::thread worker([&]{try{
    bool rejected=false;try{JavaNativeLibraries value(host,{global,global_class,config.libraries});}catch(const std::invalid_argument&){rejected=true;}
    if(!rejected||host.EnvAddress())throw std::runtime_error("detached constructor accepted");
    Attach(host);
    for(unsigned mode=0;mode<4;++mode){
      auto result=run(host.EnvAddress(),global,host.NewString(u"il2cpp"),mode);
      if(!result||host.StringValue(result)!=config.libraries[1].guest_path||Call(host,232,result)!=1)throw std::runtime_error("worker path not caller-local");
      if(run(host.EnvAddress(),global,creator_name,mode)||host.PendingException().find("IllegalArgumentException")==std::string::npos)throw std::runtime_error("foreign local name accepted");host.ClearException();
      if(run(host.EnvAddress(),creator_loader,host.NewString(u"unity"),mode)||host.PendingException().find("IllegalArgumentException")==std::string::npos)throw std::runtime_error("foreign local receiver accepted");host.ClearException();
    }
    host.StringValue(creator_result);if(host.PendingException().find("IllegalArgumentException")==std::string::npos)throw std::runtime_error("creator local result leaked across threads");host.ClearException();
    dead_worker_result=run(host.EnvAddress(),global,host.NewString(u"unity"),2);Detach(host);
  }catch(...){failure=std::current_exception();}});worker.join();if(failure)std::rethrow_exception(failure);++checks;
  host.StringValue(dead_worker_result);Check(host.PendingException().find("IllegalArgumentException")!=std::string::npos,"worker result retired on detach");host.ClearException();
  host.DeleteLocalReference(loader);host.DeleteLocalReference(app);Detach(host);Attach(host);
  Check(run(host.EnvAddress(),global,host.NewString(u"unity"),1)!=0,"creator detach does not invalidate retained loader/path identities");
  host.DeleteGlobalReference(global);host.DeleteGlobalReference(global_class);
  app=Find(host,"test/App");loader=Loader(host,app);
  Check(host.StringValue(run(host.EnvAddress(),loader,host.NewString(u"il2cpp"),2))==config.libraries[1].guest_path,"caller global deletion does not own catalog binding");
  std::atomic<unsigned> ready{0},calls{0},found{0};std::atomic<bool> go{false};std::vector<std::thread> workers;std::mutex failures;
  global=host.NewGlobalReference(loader);
  for(unsigned index=0;index<4;++index)workers.emplace_back([&,index]{try{
    Attach(host);auto name=host.NewString(u"unity");++ready;while(!go.load())std::this_thread::yield();
    for(unsigned i=0;i<128;++i){auto result=run(host.EnvAddress(),global,name,(index+i)%4);if(result){if(host.StringValue(result)!=config.libraries[0].guest_path)throw std::runtime_error("revoke raced with invalid result");++found;}if(!host.PendingException().empty())throw std::runtime_error("revoke left Java exception");++calls;}
    Detach(host);
  }catch(...){std::lock_guard lock(failures);failure=std::current_exception();}});
  auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
  while(ready!=4&&std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
  go=true;
  while(calls<32&&std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
  catalog->Revoke();for(auto&w:workers)w.join();if(failure)std::rethrow_exception(failure);
  Check(found>=32,"concurrent revocation gate exercises actual retained path results before revocation");
  Check(calls==512&&!catalog->Active(),"concurrent service revocation is safe and explicit");
  for(unsigned mode=0;mode<4;++mode)Check(!run(host.EnvAddress(),loader,host.NewString(u"unity"),mode)&&host.PendingException().empty(),"revoked known name is unavailable without stale references");
  catalog.reset();Check(!run(host.EnvAddress(),loader,host.NewString(u"unity"),0),"installed callback remains safe after component destruction");
  host.DeleteGlobalReference(global);
  Check(host.PendingException().empty(),"test ends without pending exception");
  {
    Host empty([](addr_t){return false;});empty.DefineClass("empty/App");auto clazz=Find(empty,"empty/App"),app_loader=Loader(empty,clazz);
    JavaNativeLibraries none(empty,{app_loader,clazz,{}});auto lookup=Method(empty,Find(empty,"java/lang/ClassLoader"),"findLibrary","(Ljava/lang/String;)Ljava/lang/String;");
    Check(!Call(empty,34,app_loader,lookup,empty.NewString(u"unity"))&&none.Active()&&empty.PendingException().empty(),"empty explicit catalog is unavailable without revocation");
  }
  std::printf("Java native libraries: %u checks, direct/V/A/stack-V JNI, worker lifetimes and 512 concurrent lookups pass; path lookup only.\n",checks);
}

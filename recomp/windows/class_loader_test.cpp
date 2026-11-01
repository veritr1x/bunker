#include "jni_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <thread>
int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(15));std::fprintf(stderr,"JNI callback test watchdog expired\n");std::_Exit(94);}).detach();
  unsigned checks=0;auto check=[&](bool b,const char *m){if(!b)throw std::runtime_error(m);++checks;};
  recomp::Runtime runtime; bunker::jni::Host host([](addr_t){return false;});
  host.DefineClass("example/Game");host.DefineClass("example/Other");host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
  elf_image image{};check(!elf_load(CLASS_LOADER_IMAGE,0x71000000,nullptr,&image),"NDK image load");
  auto call=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0,addr_t d=0,addr_t e=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;s.gpr.x4.qword=d;s.gpr.x5.qword=e;host.InvokeEnv(slot,s);return s.gpr.x0.qword;};
  auto text=[&](addr_t string){auto bytes=call(169,string);if(!bytes)throw std::runtime_error("toString did not return a string");std::string result(reinterpret_cast<const char*>(bytes));call(170,string,bytes);return result;};
  auto find=[&](const char *n){return call(6,reinterpret_cast<addr_t>(n));};
  alignas(16) std::array<uint8_t,65536> stack{};
  auto run=[&](const char *n,std::initializer_list<addr_t> args){State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5};size_t i=0;for(auto a:args)(s.gpr.*regs[i++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,n)));return s.gpr.x0.qword;};
  auto game=find("example/Game"),clazz=find("java/lang/Class"),object=find("java/lang/Object");
  auto string_method=call(33,object,reinterpret_cast<addr_t>("toString"),reinterpret_cast<addr_t>("()Ljava/lang/String;"));
  auto ordinary=host.NewInstance("java/lang/Object"),ordinary_alias=host.NewGlobalReference(ordinary);
  std::string identity;
  for(addr_t mode=0;mode<3;++mode){
    auto result=run("guest_invoke_loader",{host.EnvAddress(),ordinary_alias,string_method,mode});auto value=text(result);
    if(identity.empty())identity=value;
    check(value==identity&&value.rfind("java.lang.Object@",0)==0&&value.size()>17&&value.find_first_not_of("0123456789abcdef",17)==std::string::npos,"Object.toString has stable binary class name and lowercase identity hash");
    host.DeleteLocalReference(result);
    auto original=host.NewString(u"string self");result=run("guest_invoke_loader",{host.EnvAddress(),original,string_method,mode});
    check(result!=original&&call(232,result)==1&&call(24,result,original)&&text(result)=="string self","virtual String.toString returns an independent local to the same string");host.DeleteLocalReference(result);host.DeleteLocalReference(original);
    for(const char *message:{static_cast<const char*>(nullptr),"","detail"}){
      auto exception_class=find("java/lang/IllegalArgumentException");
      check(call(14,exception_class,reinterpret_cast<addr_t>(message))==0,"ThrowNew initializes checked throwable detail state");
      auto exception=call(15);call(17);
      auto formatted=run("guest_invoke_loader",{host.EnvAddress(),exception,string_method,mode});
      auto expected=std::string("java.lang.IllegalArgumentException")+(message?std::string(": ")+message:"");
      check(formatted&&text(formatted)==expected&&call(32,exception,find("java/lang/Throwable"))&&call(32,exception,find("java/lang/RuntimeException")),"virtual Throwable.toString distinguishes null and empty messages with real hierarchy");
      host.DeleteLocalReference(formatted);host.DeleteLocalReference(exception);
    }
  }
  host.DeleteGlobalReference(ordinary_alias);
  host.DefineClass("example/LocalizedException",{},"java/lang/RuntimeException");
  host.DefineObjectMethod("example/LocalizedException","getLocalizedMessage","()Ljava/lang/String;",[&](addr_t){return host.NewString(u"localized detail");});
  call(14,find("example/LocalizedException"),reinterpret_cast<addr_t>("raw detail"));auto localized=call(15);call(17);
  check(text(run("guest_invoke_loader",{host.EnvAddress(),localized,string_method,1}))=="example.LocalizedException: localized detail","Throwable.toString dispatches an implemented getLocalizedMessage override");
  host.DefineClass("example/JavaHash",{{"hashCode","()I"}});
  check(!call(34,host.NewInstance("example/JavaHash"),string_method)&&host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"Object.toString does not fabricate Java hashCode override effects");host.ClearException();
  host.DefineClass("example/JavaString",{{"toString","()Ljava/lang/String;"}});
  bool java_string_rejected=false;try{call(34,host.NewInstance("example/JavaString"),string_method);}catch(const std::runtime_error &){java_string_rejected=true;}
  check(java_string_rejected,"Object.toString does not bypass an unimplemented Java toString override");
  check(!call(34,game,string_method)&&host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"Class.toString requires unavailable interface metadata explicitly");host.ClearException();
  check(!call(34,host.NewInstance("java/lang/RuntimeException"),string_method)&&host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"uninitialized Throwable instances cannot fabricate message state");host.ClearException();
  auto loader=run("guest_loader",{host.EnvAddress(),game,0});check(loader!=0,"application loader");
  auto global=host.NewGlobalReference(loader);host.DeleteLocalReference(loader);
  for(addr_t mode=0;mode<3;++mode){
    auto other=run("guest_loader",{host.EnvAddress(),find("example/Other"),mode});
    check(call(24,global,other),"stable loader across class/call variants");host.DeleteLocalReference(other);
    auto boot_loader=run("guest_loader",{host.EnvAddress(),object,mode});
    check(boot_loader&&!call(24,boot_loader,global)&&host.PendingException().empty(),"Android bootstrap loader object");
    auto name=host.NewString(u"example.Game");
    auto result=run("guest_name",{host.EnvAddress(),clazz,name,0,global,mode});
    check(result&&call(24,result,game),"forName false exact catalog lookup");
    check(!run("guest_name",{host.EnvAddress(),clazz,name,1,global,mode})&&host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"metadata initialization rejected");host.ClearException();
    check(!run("guest_name",{host.EnvAddress(),clazz,name,0,0,mode})&&host.PendingException().find("ClassNotFoundException")!=std::string::npos,"bootstrap loader cannot resolve application class");host.ClearException();
    auto boot=host.NewString(u"java.lang.Object");
    check(call(24,run("guest_name",{host.EnvAddress(),clazz,boot,1,0,mode}),object),"initialized host bootstrap class");
    check(call(24,run("guest_name",{host.EnvAddress(),clazz,boot,1,boot_loader,mode}),object),"Android BootClassLoader lookup");
    check(!run("guest_name",{host.EnvAddress(),clazz,name,0,boot_loader,mode})&&host.PendingException().find("ClassNotFoundException")!=std::string::npos,"BootClassLoader application isolation");host.ClearException();
    for(auto bad:{u"missing.Game",u"example/Game",u"[Ljava.lang.Object;",u"int",u""}){
      check(!run("guest_name",{host.EnvAddress(),clazz,host.NewString(bad),0,global,mode})&&host.PendingException().find("ClassNotFoundException")!=std::string::npos,"unknown/malformed name exception");host.ClearException();
    }
    check(!run("guest_name",{host.EnvAddress(),clazz,0,0,global,mode})&&host.PendingException().find("NullPointerException")!=std::string::npos,"null name");host.ClearException();
    check(!run("guest_name",{host.EnvAddress(),clazz,game,0,global,mode})&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"wrong name reference type");host.ClearException();
    check(!run("guest_name",{host.EnvAddress(),clazz,name,0,game,mode})&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"wrong loader type");host.ClearException();
    check(!run("guest_name",{host.EnvAddress(),clazz,name,0,host.NewInstance("java/lang/ClassLoader"),mode})&&host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unconfigured custom loader");host.ClearException();
  }
  host.MarkClassInitialized("example/Game");
  check(call(24,run("guest_name",{host.EnvAddress(),clazz,host.NewString(u"example.Game"),1,global,1}),game),"explicit host initialization state");
  call(19,8);auto temporary=run("guest_loader",{host.EnvAddress(),game,1});auto promoted=call(20,temporary);
  check(call(232,temporary)==0&&call(24,promoted,global),"loader frame promotion and expired local");
  auto method=call(113,clazz,reinterpret_cast<addr_t>("forName"),reinterpret_cast<addr_t>("(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;"));
  check(!call(114,game,method,host.NewString(u"example.Game"),0,global)&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"wrong static class receiver");host.ClearException();
  auto global_game=host.NewGlobalReference(game);
  auto loader_method=call(33,clazz,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
  std::exception_ptr failure;
  std::thread worker([&]{try{
    State attach{};attach.gpr.x0.qword=host.VmAddress();addr_t env=0;attach.gpr.x1.qword=reinterpret_cast<addr_t>(&env);host.InvokeVm(4,attach);
    if(!env||attach.gpr.x0.dword)throw std::runtime_error("thread attach");
    auto result=run("guest_loader",{env,global_game,1});
    if(!result||!call(24,result,global))throw std::runtime_error("global loader across attached threads");
    if(run("guest_invoke_loader",{env,game,loader_method,2})||host.PendingException().find("IllegalArgumentException")==std::string::npos)throw std::runtime_error("foreign local accepted");
    host.ClearException();State detach{};detach.gpr.x0.qword=host.VmAddress();host.InvokeVm(5,detach);
  }catch(...){failure=std::current_exception();}});worker.join();if(failure)std::rethrow_exception(failure);++checks;
  host.DeleteGlobalReference(global_game);
  host.DefineClass("example/Callback");
  host.DefineObjectMethod("example/Callback","make","()Ljava/lang/Object;",[&](addr_t){
    addr_t returned=0;std::exception_ptr callback_failure;
    std::thread callback_worker([&]{try{
      State attach{};addr_t env=0;attach.gpr.x0.qword=host.VmAddress();attach.gpr.x1.qword=reinterpret_cast<addr_t>(&env);host.InvokeVm(4,attach);
      returned=host.NewGlobalReference(host.NewInstance("java/lang/Object"));
      State detach{};detach.gpr.x0.qword=host.VmAddress();host.InvokeVm(5,detach);
    }catch(...){callback_failure=std::current_exception();}});
    callback_worker.join();if(callback_failure)std::rethrow_exception(callback_failure);
    auto result=host.NewLocalReference(returned);host.DeleteGlobalReference(returned);return result;
  });
  auto callback_class=find("example/Callback"),callback=host.NewInstance("example/Callback");
  auto cached_local=host.NewString(u"cached result"),cached_global=host.NewGlobalReference(cached_local);
  host.DefineObjectMethod("example/Callback","cachedLocal","()Ljava/lang/String;",[&](addr_t){return cached_local;});
  host.DefineObjectMethod("example/Callback","cachedGlobal","()Ljava/lang/String;",[&](addr_t){return cached_global;});
  auto local_method=call(33,callback_class,reinterpret_cast<addr_t>("cachedLocal"),reinterpret_cast<addr_t>("()Ljava/lang/String;"));
  auto global_method=call(33,callback_class,reinterpret_cast<addr_t>("cachedGlobal"),reinterpret_cast<addr_t>("()Ljava/lang/String;"));
  for(addr_t mode=0;mode<3;++mode){
    for(auto entry:{std::make_pair(local_method,cached_local),std::make_pair(global_method,cached_global)}){
      auto result=run("guest_invoke_loader",{host.EnvAddress(),callback,entry.first,mode});
      check(result&&result!=entry.second&&call(232,result)==1&&call(24,result,entry.second),"callback result is a fresh caller-local reference");
      host.DeleteLocalReference(result);
      check(call(232,result)==0&&call(232,entry.second)==(entry.first==local_method?1:2)&&host.PendingException().empty(),"deleting result preserves callback local/global reference");
    }
  }
  auto retained=call(34,callback,local_method);host.DeleteLocalReference(cached_local);
  check(call(232,retained)==1&&call(24,retained,cached_global),"deleting callback local preserves independent result");
  // A callback cannot transfer another thread's local reference by returning it.
  cached_local=host.NewString(u"thread-owned callback result");
  auto global_callback=host.NewGlobalReference(callback);addr_t worker_result=0;failure=nullptr;
  std::thread result_worker([&]{try{
    State attach{};addr_t env=0;attach.gpr.x0.qword=host.VmAddress();attach.gpr.x1.qword=reinterpret_cast<addr_t>(&env);host.InvokeVm(4,attach);
    worker_result=run("guest_invoke_loader",{env,global_callback,global_method,1});
    if(!worker_result||call(232,worker_result)!=1||!call(24,worker_result,cached_global))throw std::runtime_error("global callback result was not localized to worker");
    if(run("guest_invoke_loader",{env,global_callback,local_method,2})||host.PendingException().find("IllegalArgumentException")==std::string::npos)throw std::runtime_error("foreign callback local accepted");
    host.ClearException();State detach{};detach.gpr.x0.qword=host.VmAddress();host.InvokeVm(5,detach);
  }catch(...){failure=std::current_exception();}});result_worker.join();if(failure)std::rethrow_exception(failure);++checks;
  check(!call(25,worker_result)&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"detached caller result cannot be reused by another thread");host.ClearException();
  host.DeleteGlobalReference(global_callback);host.DeleteLocalReference(cached_local);
  auto global_result=call(34,callback,global_method);host.DeleteGlobalReference(cached_global);
  check(call(232,global_result)==1&&call(24,global_result,retained),"deleting callback global preserves independent result");
  auto callback_method=call(33,callback_class,reinterpret_cast<addr_t>("make"),reinterpret_cast<addr_t>("()Ljava/lang/Object;"));
  for(addr_t mode=0;mode<3;++mode)check(run("guest_invoke_loader",{host.EnvAddress(),callback,callback_method,mode})&&host.PendingException().empty(),"callback can join an attached JNI worker without holding host lock");
  host.DefineObjectMethod("example/Callback","fail","()Ljava/lang/Object;",[](addr_t)->addr_t{throw std::runtime_error("callback failure");});
  auto failing_method=call(33,callback_class,reinterpret_cast<addr_t>("fail"),reinterpret_cast<addr_t>("()Ljava/lang/Object;"));
  bool caught=false;try{call(34,callback,failing_method);}catch(const std::runtime_error &e){caught=std::string(e.what())=="callback failure";}
  check(caught&&call(34,callback,callback_method),"callback exceptions restore lock ownership");
  host.DefineObjectMethod("example/Callback","wrong","()Ljava/lang/ClassLoader;",[&](addr_t){return host.NewString(u"wrong return type");});
  auto wrong_method=call(33,callback_class,reinterpret_cast<addr_t>("wrong"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
  check(!call(34,callback,wrong_method)&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"callback result type checked after reacquiring lock");host.ClearException();
  host.DeleteGlobalReference(global);check(call(232,global)==0,"global lifetime");
  check(call(24,promoted,run("guest_loader",{host.EnvAddress(),game,2})),"loader root survives references");
  std::printf("JNI class-loader checks passed: %u (actual NDK direct/V/A callers)\n",checks);
}

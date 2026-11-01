#include "jni_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cstdio>
#include <stdexcept>
#include <thread>
int main(){
  unsigned checks=0;auto check=[&](bool b,const char *s){if(!b)throw std::runtime_error(s);++checks;};
  recomp::Runtime runtime;bunker::jni::Host host([](addr_t){return false;});host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
  elf_image image{};check(!elf_load(STRING_BUILDER_IMAGE,0x72000000,nullptr,&image),"NDK StringBuilder image");
  auto call=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0,addr_t d=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;s.gpr.x4.qword=d;host.InvokeEnv(slot,s);return s.gpr.x0.qword;};
  auto find=[&](const char *name){return call(6,reinterpret_cast<addr_t>(name));};
  auto method=[&](addr_t clazz,const char *name,const char *sig){return call(33,clazz,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig));};
  auto text=[&](addr_t string){auto n=call(164,string),p=call(165,string);if(!p)throw std::runtime_error("missing UTF16 result");std::u16string result(reinterpret_cast<const char16_t*>(p),n);call(166,string,p);return result;};
  alignas(16) std::array<uint8_t,65536> stack{};
  auto run=[&](const char *name,std::initializer_list<addr_t> args){State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};size_t i=0;for(auto a:args)(s.gpr.*regs[i++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));return s.gpr.x0.qword;};
  auto clazz=find("java/lang/StringBuilder"),object=find("java/lang/Object"),abstract=find("java/lang/AbstractStringBuilder");
  auto constructor=method(clazz,"<init>","()V"),append=method(clazz,"append","(Ljava/lang/String;)Ljava/lang/StringBuilder;"),to_string=method(clazz,"toString","()Ljava/lang/String;"),virtual_string=method(object,"toString","()Ljava/lang/String;");
  check(constructor&&append&&to_string,"exact evidenced methods");
  check(!method(clazz,"<init>","(I)V")&&host.PendingException().find("NoSuchMethodError")!=std::string::npos,"unevidenced constructors remain unsupported");host.ClearException();
  addr_t previous_empty=0;
  for(addr_t mode=0;mode<3;++mode){
    auto builder=run("guest_builder_new",{host.EnvAddress(),clazz,constructor,mode});
    check(builder&&call(232,builder)==1&&call(32,builder,clazz)&&call(32,builder,abstract)&&call(32,builder,object),"real default construction and type hierarchy");
    auto empty=run("guest_builder_string",{host.EnvAddress(),builder,to_string,mode});
    check(text(empty).empty(),"default constructor starts empty");
    if(previous_empty)check(call(24,previous_empty,empty),"Android empty toString constant identity");previous_empty=empty;
    auto global=host.NewGlobalReference(builder);host.DeleteLocalReference(builder);
    auto input=host.NewString(std::u16string{u'A',0,0xe9,0xd83d,0xde00});
    auto returned=run("guest_builder_append",{host.EnvAddress(),global,append,input,mode});
    check(returned&&returned!=global&&call(232,returned)==1&&call(24,returned,global),"append returns a fresh local alias of receiver");host.DeleteLocalReference(returned);host.DeleteLocalReference(input);
    auto snapshot=run("guest_builder_string",{host.EnvAddress(),global,virtual_string,mode});
    std::u16string expected{u'A',0,0xe9,0xd83d,0xde00};
    check(text(snapshot)==expected,"UTF16 units including NUL and surrogate pairs are preserved");
    auto again=run("guest_builder_string",{host.EnvAddress(),global,to_string,mode});
    check(!call(24,snapshot,again)&&text(again)==expected,"nonempty toString creates independent copied String objects");
    returned=run("guest_builder_append",{host.EnvAddress(),global,append,0,mode});host.DeleteLocalReference(returned);expected+=u"null";
    check(text(run("guest_builder_string",{host.EnvAddress(),global,to_string,mode}))==expected&&text(snapshot)==std::u16string({u'A',0,0xe9,0xd83d,0xde00}),"append null and immutable prior snapshot");
    auto invalid=host.NewInstance("java/lang/Object");
    check(!run("guest_builder_append",{host.EnvAddress(),global,append,invalid,mode})&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"append rejects wrong argument type");host.ClearException();
    check(!run("guest_builder_append",{host.EnvAddress(),invalid,append,0,mode})&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"append rejects wrong receiver type");host.ClearException();
    check(!run("guest_builder_append",{host.EnvAddress(),0,append,0,mode})&&host.PendingException().find("NullPointerException")!=std::string::npos,"append rejects null receiver");host.ClearException();
    check(!run("guest_builder_new",{host.EnvAddress(),object,constructor,mode})&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"constructor method cannot initialize another class");host.ClearException();
    check(!run("guest_builder_new",{host.EnvAddress(),clazz,to_string,mode})&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"NewObject requires a constructor ID");host.ClearException();
    check(!run("guest_builder_new",{host.EnvAddress(),0,constructor,mode})&&host.PendingException().find("NullPointerException")!=std::string::npos,"NewObject rejects null class");host.ClearException();
    check(!run("guest_builder_new",{host.EnvAddress(),clazz,0xdead,mode})&&host.PendingException().find("NoSuchMethodError")!=std::string::npos,"NewObject rejects unknown constructor ID");host.ClearException();
    check(!run("guest_builder_string",{host.EnvAddress(),host.NewInstance("java/lang/StringBuilder"),to_string,mode})&&host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"metadata-only instance cannot bypass constructor effects");host.ClearException();
    check(text(run("guest_builder_string",{host.EnvAddress(),global,to_string,mode}))==expected,"failed calls preserve builder contents");
    call(19,8);returned=run("guest_builder_append",{host.EnvAddress(),global,append,host.NewString(u"!"),mode});returned=call(20,returned);expected+=u"!";
    check(call(24,returned,global)&&text(run("guest_builder_string",{host.EnvAddress(),returned,to_string,mode}))==expected,"builder result survives local frame promotion");
    std::u16string large(4097,0x4e2d);returned=run("guest_builder_append",{host.EnvAddress(),global,append,host.NewString(large),mode});expected+=large;
    check(call(24,returned,global)&&text(run("guest_builder_string",{host.EnvAddress(),global,to_string,mode}))==expected,"builder grows beyond initial capacity without truncation");
    host.DeleteGlobalReference(global);
    check(call(232,returned)==1&&text(run("guest_builder_string",{host.EnvAddress(),returned,to_string,mode}))==expected,"result retains builder independently of deleted global");
  }
  auto builder=run("guest_builder_new",{host.EnvAddress(),clazz,constructor,0}),global=host.NewGlobalReference(builder),local_input=host.NewString(u"foreign");
  for(size_t slot:{35,36})check(!call(slot,builder,append,0)&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"nonempty JNI V/A call requires an argument list"),host.ClearException();
  check(!call(34,builder,constructor)&&host.PendingException().find("IllegalArgumentException")!=std::string::npos,"constructor cannot be invoked as an ordinary object-returning method");host.ClearException();
  auto dead_string=host.NewString(u"released"),weak=call(226,dead_string);host.DeleteLocalReference(dead_string);
  check(run("guest_builder_append",{host.EnvAddress(),global,append,weak,1})&&text(run("guest_builder_string",{host.EnvAddress(),global,to_string,1}))==u"null","cleared weak string behaves as null");call(227,weak);
  std::exception_ptr failure;std::thread worker([&]{try{
    State s{};addr_t env=0;s.gpr.x0.qword=host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);host.InvokeVm(4,s);
    auto value=host.NewString(u" worker"),result=run("guest_builder_append",{env,global,append,value,2});
    if(!result||call(232,result)!=1||!call(24,result,global))throw std::runtime_error("worker append did not return caller-local alias");
    if(run("guest_builder_append",{env,global,append,local_input,1})||host.PendingException().find("IllegalArgumentException")==std::string::npos)throw std::runtime_error("foreign local argument accepted");host.ClearException();
    s={};s.gpr.x0.qword=host.VmAddress();host.InvokeVm(5,s);
  }catch(...){failure=std::current_exception();}});worker.join();if(failure)std::rethrow_exception(failure);++checks;
  check(text(run("guest_builder_string",{host.EnvAddress(),global,to_string,0}))==u"null worker","global builder may be used by a separately attached thread");
  check(run("guest_builder_append",{host.EnvAddress(),global,append,host.NewString(u" stack"),3})&&text(run("guest_builder_string",{host.EnvAddress(),global,to_string,0}))==u"null worker stack","actual NDK va_list stack fallback preserves the append argument");
  std::printf("StringBuilder: %u checks passed using actual NDK NewObject/CallObject direct,V,A callers\n",checks);
}

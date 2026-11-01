#include "android_context.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "sample.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <stdexcept>
#include <thread>
struct Session {
  recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};elf_image &image;alignas(16)std::array<uint8_t,65536> stack{};
  explicit Session(elf_image &i):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));}
  addr_t call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0,addr_t d=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;s.gpr.x4.qword=d;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
  addr_t find(const char *n){return call(6,reinterpret_cast<addr_t>(n));}
  addr_t method(const char *owner,const char *name,const char *sig){return call(33,find(owner),reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig));}
  addr_t run(const char *name,std::initializer_list<addr_t> args){State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5};size_t i=0;for(auto a:args)(s.gpr.*regs[i++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));if(s.gpr.sp.qword!=reinterpret_cast<addr_t>(stack.data()+stack.size())||s.gpr.pc.qword!=0xfeedffff)throw std::runtime_error("NDK context caller PC/SP changed");return s.gpr.x0.qword;}
  addr_t zero(addr_t object,addr_t method,addr_t mode){return run("guest_context_zero",{host.EnvAddress(),object,method,mode});}
  addr_t one(addr_t object,addr_t method,addr_t key,addr_t mode){return run("guest_context_one",{host.EnvAddress(),object,method,key,mode});}
  addr_t two(addr_t object,addr_t method,addr_t key,addr_t fallback,addr_t mode){return run("guest_context_two",{host.EnvAddress(),object,method,key,fallback,mode});}
  bool boolean(addr_t object,addr_t method,addr_t key,addr_t mode){return run("guest_context_boolean",{host.EnvAddress(),object,method,key,mode})!=0;}
  std::u16string text(addr_t object){auto v=host.StringValue(object);if(!v)throw std::runtime_error("expected nonnull configured string");return *v;}
};
int main(){
  using namespace bunker::windows;unsigned checks=0;auto check=[&](bool b,const char *why){if(!b)throw std::runtime_error(why);++checks;};
  elf_image image{};check(!elf_load(CONTEXT_IMAGE,0x73000000,nullptr,&image),"actual NDK context image");
  AndroidContextConfig config;config.package_name=kPackageName;config.target_sdk=kTargetSdk;config.activity_class=kLaunchActivity;
  Session h(image);addr_t kept_intent=0,weak_action=0,get_action=0,get_component=0,get_package_name=0;
  {
    AndroidContext context(h.host,config);h.call(19,128);
    auto activity=context.Activity(),get_intent=h.method("android/app/Activity","getIntent","()Landroid/content/Intent;");
    get_action=h.method("android/content/Intent","getAction","()Ljava/lang/String;");get_component=h.method("android/content/Intent","getComponent","()Landroid/content/ComponentName;");
    auto get_extras=h.method("android/content/Intent","getExtras","()Landroid/os/Bundle;"),category=h.method("android/content/Intent","hasCategory","(Ljava/lang/String;)Z");
    get_package_name=h.method("android/content/ComponentName","getPackageName","()Ljava/lang/String;");auto get_class_name=h.method("android/content/ComponentName","getClassName","()Ljava/lang/String;");
    auto get_data=h.method("android/content/Intent","getData","()Landroid/net/Uri;"),get_data_string=h.method("android/content/Intent","getDataString","()Ljava/lang/String;"),get_package=h.method("android/content/Intent","getPackage","()Ljava/lang/String;");
    auto intent=h.zero(activity,get_intent,0);kept_intent=h.host.NewGlobalReference(intent);auto action=h.zero(intent,get_action,0);weak_action=h.call(226,action);
    std::string binary=kLaunchActivity;std::replace(binary.begin(),binary.end(),'/','.');std::u16string binary16(binary.begin(),binary.end());
    for(addr_t mode=0;mode<3;++mode){
      auto returned=h.zero(activity,get_intent,mode);check(returned!=intent&&h.call(232,returned)==1&&h.call(24,returned,intent),"Activity.getIntent returns fresh local handles to its configured Intent");h.host.DeleteLocalReference(returned);
      returned=h.zero(intent,get_action,mode);check(h.text(returned)==u"android.intent.action.MAIN"&&h.call(24,action,returned),"MAIN action and stable property object");
      check(h.boolean(intent,category,h.host.NewString(u"android.intent.category.LAUNCHER"),mode)&&!h.boolean(intent,category,h.host.NewString(u"other"),mode)&&!h.boolean(intent,category,0,mode),"LAUNCHER category and absent/null category queries");
      auto component=h.zero(intent,get_component,mode);check(h.call(32,component,h.find("android/content/ComponentName"))&&h.text(h.zero(component,get_package_name,mode))==kPackageName&&h.text(h.zero(component,get_class_name,mode))==binary16,"explicit component package/class come from real APK metadata");
      check(!h.zero(intent,get_extras,mode)&&!h.zero(intent,get_data,mode)&&!h.zero(intent,get_data_string,mode)&&!h.zero(intent,get_package,mode)&&h.host.PendingException().empty(),"default extras/data/package selector are absent");
      check(!h.zero(h.host.NewInstance(config.activity_class),get_intent,mode)&&h.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unconfigured Activity cannot pretend to have a launch Intent");h.host.ClearException();
      check(!h.zero(0,get_intent,mode)&&h.host.PendingException().find("NullPointerException")!=std::string::npos,"null Activity rejected");h.host.ClearException();
      h.boolean(intent,category,activity,mode);check(h.host.PendingException().find("IllegalArgumentException")!=std::string::npos,"category argument type is checked");h.host.ClearException();
    }
    check(!h.method("android/content/Intent","unknownService","()Ljava/lang/Object;")&&h.host.PendingException().find("NoSuchMethodError")!=std::string::npos,"unknown service remains unsupported");h.host.ClearException();
    auto fake=h.host.NewHostInstance("android/content/Intent",std::make_shared<int>(7));check(!h.zero(fake,get_action,0)&&h.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"host payload type is checked");h.host.ClearException();
    h.call(20);
  }
  check(h.text(h.zero(kept_intent,get_action,1))==u"android.intent.action.MAIN"&&!h.call(24,weak_action,0),"Intent graph retains properties after Context wrapper and caller frame end");
  auto component=h.zero(kept_intent,get_component,1);check(h.text(h.zero(component,get_package_name,1))==kPackageName,"component retains package string without Context global roots");
  Session configured(image);config.launch_data=u"nier://launch?value=1";
  config.launch_extras={{u"unity",LaunchExtra::String(std::u16string{u'-',u'x',0,0xd83d,0xde00})},{u"android.intent.extra.VR_LAUNCH",LaunchExtra::Boolean(true)},{u"empty",LaunchExtra::String(u"")},{u"null",{}},{u"count",LaunchExtra::Integer(7)},{u"",LaunchExtra::String(u"empty-key")}};
  addr_t kept_bundle=0,get_string=0,get_string_default=0,contains=0,get_boolean=0;
  {
    AndroidContext context(configured.host,config);config.launch_extras.clear();config.launch_data.reset();configured.call(19,128);
    auto activity=context.Activity(),get_intent=configured.method("android/app/Activity","getIntent","()Landroid/content/Intent;"),intent=configured.zero(activity,get_intent,0);
    auto extras=configured.method("android/content/Intent","getExtras","()Landroid/os/Bundle;"),data=configured.method("android/content/Intent","getData","()Landroid/net/Uri;"),data_string=configured.method("android/content/Intent","getDataString","()Ljava/lang/String;"),uri_string=configured.method("java/lang/Object","toString","()Ljava/lang/String;");
    get_string=configured.method("android/os/Bundle","getString","(Ljava/lang/String;)Ljava/lang/String;");get_string_default=configured.method("android/os/Bundle","getString","(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;");contains=configured.method("android/os/Bundle","containsKey","(Ljava/lang/String;)Z");get_boolean=configured.method("android/os/Bundle","getBoolean","(Ljava/lang/String;)Z");
    auto bundle=configured.zero(intent,extras,0);kept_bundle=configured.host.NewGlobalReference(bundle);
    for(addr_t mode=0;mode<3;++mode){
      auto copy=configured.zero(intent,extras,mode);check(copy&&configured.call(32,copy,configured.find("android/os/BaseBundle"))&&!configured.call(24,copy,bundle),"getExtras returns an independent Bundle copy");
      auto uri=configured.zero(intent,data,mode),string=configured.zero(intent,data_string,mode);check(uri&&configured.call(32,uri,configured.find("android/net/Uri"))&&configured.text(string)==u"nier://launch?value=1"&&configured.call(24,string,configured.zero(uri,uri_string,mode)),"configured URI and data-string identity");
      auto key=configured.host.NewString(u"unity"),fallback=configured.host.NewString(u"fallback");
      check(configured.boolean(copy,contains,key,mode)&&!configured.boolean(copy,contains,configured.host.NewString(u"missing"),mode)&&!configured.boolean(copy,contains,0,mode),"Bundle presence and absent/null keys");
      auto value=configured.one(copy,get_string,key,mode),other=configured.one(bundle,get_string,key,mode);check(configured.text(value)==std::u16string({u'-',u'x',0,0xd83d,0xde00})&&configured.call(24,value,other),"Bundle snapshot preserves UTF16 string values and object identity");
      for(auto absent:{u"missing",u"count",u"null",u"android.intent.extra.VR_LAUNCH"}){
        auto query=configured.host.NewString(absent),result=configured.two(copy,get_string_default,query,fallback,mode);
        check(!configured.one(copy,get_string,query,mode)&&result!=fallback&&configured.call(232,result)==1&&configured.call(24,result,fallback),"absent/null/wrong-type string uses caller default without coercion");configured.host.DeleteLocalReference(result);check(configured.text(fallback)==u"fallback","deleting getter result preserves its default argument");
      }
      check(configured.boolean(copy,contains,configured.host.NewString(u"null"),mode)&&configured.text(configured.two(copy,get_string_default,configured.host.NewString(u"empty"),fallback,mode)).empty()&&configured.text(configured.one(copy,get_string,configured.host.NewString(u""),mode))==u"empty-key","null/present-empty values and empty keys are distinct from absence");
      check(configured.boolean(copy,get_boolean,configured.host.NewString(u"android.intent.extra.VR_LAUNCH"),mode)&&!configured.boolean(copy,get_boolean,key,mode)&&!configured.boolean(copy,get_boolean,configured.host.NewString(u"count"),mode)&&!configured.boolean(copy,get_boolean,0,mode),"Bundle booleans are typed with false for absent/null/wrong type");
      configured.one(copy,get_string,activity,mode);check(configured.host.PendingException().find("IllegalArgumentException")!=std::string::npos,"Bundle key requires a string");configured.host.ClearException();
      check(!configured.boolean(configured.host.NewInstance("android/os/Bundle"),contains,key,mode)&&configured.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unconfigured Bundle cannot invent extras");configured.host.ClearException();
    }
    auto fallback=configured.host.NewString(u"split-default");check(configured.call(24,configured.two(bundle,get_string_default,configured.host.NewString(u"missing"),fallback,3),fallback),"actual NDK two-object va_list crosses GP-save area into stack");
    configured.call(37,intent,configured.method("android/content/Intent","getAction","()Ljava/lang/String;"));check(configured.host.PendingException().find("IllegalArgumentException")!=std::string::npos,"boolean API rejects object-returning method");configured.host.ClearException();
    configured.call(20);
  }
  check(configured.text(configured.one(kept_bundle,get_string,configured.host.NewString(u"unity"),1))==std::u16string({u'-',u'x',0,0xd83d,0xde00}),"Bundle copy retains values after original Context/Intent/frame end");
  auto foreign_key=configured.host.NewString(u"unity");
  std::exception_ptr failure;std::thread worker([&]{try{State s{};addr_t env=0;s.gpr.x0.qword=configured.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);configured.host.InvokeVm(4,s);auto key=configured.host.NewString(u"android.intent.extra.VR_LAUNCH");if(!configured.boolean(kept_bundle,get_boolean,key,2))throw std::runtime_error("attached worker lost Bundle state");if(configured.one(kept_bundle,get_string,foreign_key,1)||configured.host.PendingException().find("IllegalArgumentException")==std::string::npos)throw std::runtime_error("generic method accepted a foreign local argument");configured.host.ClearException();s={};s.gpr.x0.qword=configured.host.VmAddress();configured.host.InvokeVm(5,s);}catch(...){failure=std::current_exception();}});worker.join();if(failure)std::rethrow_exception(failure);++checks;
  auto expired=configured.host.NewString(u"gone"),weak=configured.call(226,expired);configured.host.DeleteLocalReference(expired);check(!configured.call(31,weak)&&configured.host.PendingException().find("NullPointerException")!=std::string::npos,"cleared weak reference is null for a nonnull receiver");configured.host.ClearException();configured.call(227,weak);
  auto captured=h.host.CaptureValue(kept_intent);bool foreign_value=false;try{configured.host.LocalValue(captured);}catch(const std::invalid_argument &){foreign_value=true;}check(foreign_value,"opaque object graph values cannot cross hosts");
  std::printf("Configured launch Intent/Bundle: %u checks passed through actual NDK object/boolean direct,V,A callers\n",checks);
}

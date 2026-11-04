#include "android_context.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "sample.h"
#include <array>
#include <cstdio>
#include <memory>
#include <stdexcept>
using namespace bunker::windows;
namespace {
unsigned checks;
void check(bool value,const char*why){if(!value){throw std::runtime_error(why);}++checks;}
struct Session {
 recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};elf_image&image;alignas(16)std::array<uint8_t,65536> stack{};
 explicit Session(elf_image&i):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));host.DefineClass("com/unity3d/player/UnityPlayer",{{"initializeGoogleAr","()Z"},{"getLaunchURL","()Ljava/lang/String;"}});}
 addr_t env(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0,addr_t d=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;s.gpr.x4.qword=d;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
 addr_t find(const char*n){return env(6,(addr_t)n);}
 addr_t method(const char*owner,const char*name,const char*signature){auto c=find(owner);auto result=env(33,c,(addr_t)name,(addr_t)signature);host.DeleteLocalReference(c);return result;}
 addr_t run(const char*name,std::initializer_list<addr_t>args){State s{};Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};unsigned index=0;for(auto value:args){(s.gpr.*registers[index++]).qword=value;}s.gpr.sp.qword=(addr_t)(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,(addr_t)elf_symbol(&image,name));check(s.gpr.sp.qword==(addr_t)(stack.data()+stack.size())&&s.gpr.pc.qword==0xfeedffff,"actual NDK caller RET/SP");return s.gpr.x0.qword;}
 addr_t url(addr_t player,addr_t method,unsigned mode){return run("launch_url",{host.EnvAddress(),player,method,mode});}
 addr_t uri(addr_t player){return run("launch_uri_field",{host.EnvAddress(),player});}
 void set(addr_t player,addr_t value){run("launch_set_uri",{host.EnvAddress(),player,value});}
 bool same(addr_t a,addr_t b){return env(24,a,b)!=0;}
 std::u16string text(addr_t object){auto value=host.StringValue(object);check(value.has_value(),"real nonnull String value");return*value;}
};
}
int main(){elf_image image{};check(!elf_load(LAUNCH_IMAGE,0x73000000,nullptr,&image),"actual NDK launch URL fixture image");
 for(unsigned profile=0;profile<3;++profile){Session h(image);AndroidContextConfig config;config.package_name=kPackageName;config.target_sdk=kTargetSdk;config.activity_class=kLaunchActivity;
  std::optional<std::u16string> expected;if(profile==1){expected=u"";}if(profile==2){expected=std::u16string({u'n',u'i',u'e',u'r',u':',u'/',u'/',u'値',u'=',0,0xd83d,0xde80});}config.launch_data=expected;
  // New instance binding must retain the shared fail-closed declaration rules.
  h.host.DefineClass("TEST/LaunchBind",{{"available","()Ljava/lang/String;"},{"nativeMethod","()Ljava/lang/String;",false,true},{"staticMethod","()Ljava/lang/String;",true,false},{"intMethod","()I"}});
  for(const char*name:{"unknown","nativeMethod","staticMethod"}){bool rejected=false;try{h.host.BindObjectMethod("TEST/LaunchBind",name,"()Ljava/lang/String;",[](addr_t,const bunker::jni::Host::MethodArguments&){return addr_t(0);});}catch(const std::invalid_argument&){rejected=true;}check(rejected,"instance object binding rejects missing/native/static declaration");}
  bool wrong_kind=false;try{h.host.BindObjectMethod("TEST/LaunchBind","intMethod","()I",[](addr_t,const bunker::jni::Host::MethodArguments&){return addr_t(0);});}catch(const std::invalid_argument&){wrong_kind=true;}check(wrong_kind,"object binding rejects primitive result declaration");
  bool missing_handler=false;try{h.host.BindObjectMethod("TEST/LaunchBind","available","()Ljava/lang/String;",std::function<addr_t(addr_t,const bunker::jni::Host::MethodArguments&)>{});}catch(const std::invalid_argument&){missing_handler=true;}check(missing_handler,"empty object implementation rejected before binding");
  h.host.BindObjectMethod("TEST/LaunchBind","available","()Ljava/lang/String;",[](addr_t,const bunker::jni::Host::MethodArguments&){return addr_t(0);});
  bool duplicate_bind=false,duplicate_define=false;try{h.host.BindObjectMethod("TEST/LaunchBind","available","()Ljava/lang/String;",[](addr_t,const bunker::jni::Host::MethodArguments&){return addr_t(0);});}catch(const std::invalid_argument&){duplicate_bind=true;}try{h.host.DefineObjectMethod("TEST/LaunchBind","available","()Ljava/lang/String;",[](addr_t){return addr_t(0);});}catch(const std::invalid_argument&){duplicate_define=true;}check(duplicate_bind&&duplicate_define,"existing implementation cannot be rebound and Define duplicate policy stays exact");
  auto context=std::make_unique<AndroidContext>(h.host,config);config.launch_data=u"changed-after-Context-construction";
  auto player=h.host.NewInstance("com/unity3d/player/UnityPlayer");context->BindUnityPlayer(player);auto method=h.method("com/unity3d/player/UnityPlayer","getLaunchURL","()Ljava/lang/String;"),activity=context->Activity();
  auto get_intent=h.method("android/app/Activity","getIntent","()Landroid/content/Intent;"),get_data=h.method("android/content/Intent","getData","()Landroid/net/Uri;"),get_data_string=h.method("android/content/Intent","getDataString","()Ljava/lang/String;");
  auto intent=h.url(activity,get_intent,0),uri=h.uri(player),configured=h.url(intent,get_data,0);check(h.same(uri,configured),"constructor snapshots exact configured Activity Intent Uri identity");h.host.DeleteLocalReference(configured);
  auto global_uri=uri?h.host.NewGlobalReference(uri):0,weak_uri=uri?h.env(226,uri):0;h.host.DeleteLocalReference(uri);
  for(unsigned mode=0;mode<3;++mode){auto result=h.url(player,method,mode);check(h.host.PendingException().empty(),"getLaunchURL completes without invented startup metadata");if(expected){auto data=h.url(intent,get_data_string,mode);check(result&&h.text(result)==*expected&&h.same(result,data),"absent versus empty and UTF16 NUL/nonBMP survive actual NDK direct/V/A with String identity");check(h.env(232,result)==1,"returned String is real caller-local reference");h.host.DeleteLocalReference(data);}else{check(!result,"absent launch Uri returns genuine null");}h.host.DeleteLocalReference(result);}
  auto clazz=h.find("com/unity3d/player/UnityPlayer"),current=h.env(144,clazz,(addr_t)"currentActivity",(addr_t)"Landroid/app/Activity;");h.env(154,clazz,current,0);h.host.DeleteLocalReference(clazz);h.host.SetObjectFieldValue(player,"mContext","Landroid/content/Context;",0);
  h.host.DeleteLocalReference(intent);h.host.DeleteLocalReference(activity);context.reset();
  for(unsigned mode=0;mode<3;++mode){auto result=h.url(player,method,mode);check(h.host.PendingException().empty()&&(expected?result&&h.text(result)==*expected:!result),"getLaunchURL uses retained field after Context retirement and currentActivity/mContext removal, never live rereads Intent");h.host.DeleteLocalReference(result);}
  h.set(player,0);check(!h.url(player,method,0)&&h.host.PendingException().empty(),"actual JNI field replacement with null changes getter");if(global_uri){h.set(player,global_uri);auto result=h.url(player,method,1);check(h.text(result)==*expected,"actual JNI restore retains original Uri data");h.host.DeleteLocalReference(result);}
  // Explicit TEST Uri subtype exercises Java virtual toString dispatch. It is
  // not a production URI parser or a fabricated external launch event.
  h.host.DefineClass("TEST/LaunchUri",{},"android/net/Uri");auto value=h.host.NewString(u"replacement://Unicode/\u03a9");auto owned=h.host.CaptureValue(value);h.host.DeleteLocalReference(value);h.host.DefineObjectMethod("TEST/LaunchUri","toString","()Ljava/lang/String;",[&h,owned](addr_t){return h.host.LocalValue(owned);});
  auto replacement=h.host.NewInstance("TEST/LaunchUri"),weak_replacement=h.env(226,replacement);h.set(player,replacement);h.host.DeleteLocalReference(replacement);
  if(global_uri){h.host.DeleteGlobalReference(global_uri);check(h.same(weak_uri,0),"replaced original Uri expires after all its real roots are released");h.env(227,weak_uri);}
  for(unsigned mode=0;mode<3;++mode){auto result=h.url(player,method,mode);check(result&&h.text(result)==u"replacement://Unicode/\u03a9"&&!h.same(weak_replacement,0),"getter reads replacement Uri field and virtual toString with owned object lifetime");h.host.DeleteLocalReference(result);}
  h.host.DefineClass("TEST/ThrowingLaunchUri",{},"android/net/Uri");h.host.DefineObjectMethod("TEST/ThrowingLaunchUri","toString","()Ljava/lang/String;",[&h](addr_t){h.host.ThrowException("java/lang/RuntimeException",u"TEST Uri failure");return addr_t(0);});auto throwing=h.host.NewInstance("TEST/ThrowingLaunchUri");h.set(player,throwing);h.host.DeleteLocalReference(throwing);check(!h.url(player,method,1)&&h.host.PendingException()=="java/lang/RuntimeException: TEST Uri failure","real virtual toString exception propagated without native success");h.host.ClearException();check(h.same(weak_replacement,0),"field replacement releases old replacement Uri");h.env(227,weak_replacement);
  h.set(player,0);check(!h.url(0,method,2)&&h.host.PendingException().find("NullPointerException")!=std::string::npos,"NDK null UnityPlayer receiver preserves Java exception");h.host.ClearException();
  auto pending=h.host.NewString(u"pending");h.host.ThrowException("java/lang/RuntimeException",u"prior failure");check(!h.url(player,method,0)&&h.host.PendingException()=="java/lang/RuntimeException: prior failure","preexisting Java exception is preserved");h.host.ClearException();h.host.DeleteLocalReference(pending);
 }
 std::printf("UNITY-LAUNCH-URL-PASS checks=%u profiles=3 actual_NDK_direct_V_A=1 retained_Uri_snapshot=1 no_newIntent_event_claim=1\n",checks);
}

#include "package_test_session.h"
#include <atomic>
#include <memory>
int main(int argc,char **){
 using namespace bunker::windows;unsigned checks=0;auto Check=[&](bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;};
 elf_image image{};Check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual NDK Java fixture loads");
 for(int profile=0;profile<5;++profile){
  if((profile==2)!=(argc>1))continue;
  Session h(image);
  h.host.DefineClass("com/unity3d/player/UnityPlayer",{{"initializeGoogleAr","()Z"},{"getLaunchURL","()Ljava/lang/String;"},{"nativeProbe","()Z",false,true}});
  h.host.DefineClass("com/unity3d/player/GoogleARCoreApi",{{"initializeARCore","(Landroid/app/Activity;)V",false,true},{"pauseARCore","()V",false,true},{"resumeARCore","()V",false,true}});
  AndroidContextConfig config;config.package_name=kPackageName;config.target_sdk=kTargetSdk;config.activity_class=kLaunchActivity;
  if(profile==0)ApplyActualMetadata(config);
  if(profile==1)config.application_metadata[u"unity.tango-enable"]=LaunchExtra::Boolean(false);
  if(profile==2)config.application_metadata[u"unity.tango-enable"]=LaunchExtra::Boolean(true);
  if(profile==3)config.application_metadata[u"unity.tango-enable"]=LaunchExtra::String(u"true");
  auto context=std::make_unique<AndroidContext>(h.host,config);auto activity=context->Activity();
  Check(h.run("java_service_interface",{h.host.EnvAddress()})==255&&h.host.PendingException().empty(),"NDK interface catalog, NULL superclass, Object assignability, reflected type and non-instantiation");
  auto service=h.find("android/content/ServiceConnection");
  Check(!h.host.NewInstance("android/content/ServiceConnection")&&h.host.PendingException().find("InstantiationException")!=std::string::npos,"host cannot instantiate interface");h.host.ClearException();
  Check(!h.host.NewHostInstance("android/content/ServiceConnection",std::make_shared<int>(1))&&h.host.PendingException().find("InstantiationException")!=std::string::npos,"host-backed interface instantiation is rejected without dereferencing null");h.host.ClearException();
  for(size_t slot:{28,29,30}){Check(!h.call(slot,service,0)&&h.host.PendingException().find("InstantiationException")!=std::string::npos,"NewObject forms reject interface before constructing any object");h.host.ClearException();}
  bool extends_rejected=false;try{h.host.DefineClass("IllegalInterfaceSubclass",{},"android/content/ServiceConnection");}catch(const std::invalid_argument&){extends_rejected=true;}Check(extends_rejected,"no invented class extends a Java interface");
  auto resolver=h.run("java_context_resolver",{h.host.EnvAddress(),activity});Check(resolver&&!h.host.PendingException().size(),"NDK Context returns configured real resolver object");
  auto held=h.host.NewGlobalReference(resolver),weak=h.call(226,resolver);
  for(int i=0;i<16;++i){auto again=h.run("java_context_resolver",{h.host.EnvAddress(),activity});Check(again!=resolver&&h.call(24,resolver,again),"stable context-owned resolver with fresh JNI caller locals");h.host.DeleteLocalReference(again);}
  auto actual=h.call(31,resolver),base=h.call(10,actual);Check(h.call(24,actual,h.find("android/app/ContextImpl$ApplicationContentResolver"))&&h.call(24,base,h.find("android/content/ContentResolver")),"resolver concrete class and platform base hierarchy are real metadata");
  std::atomic<bool> worker_ok{false};auto global_activity=h.host.NewGlobalReference(activity);
  std::thread worker([&]{State attach{};addr_t env=0;attach.gpr.x0.qword=h.host.VmAddress();attach.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,attach);auto again=h.run("java_context_resolver",{env,global_activity});worker_ok=h.call(24,again,held)&&h.host.PendingException().empty();h.host.DeleteLocalReference(again);State detach{};detach.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,detach);});worker.join();Check(worker_ok,"attached native thread sees same context resolver identity");
  bool unsupported=false;try{h.host.BindBooleanMethod("com/unity3d/player/UnityPlayer","nativeProbe","()Z",[](addr_t,const bunker::jni::Host::MethodArguments&){return true;});}catch(const std::invalid_argument&){unsupported=true;}Check(unsupported,"binding cannot replace actual native method declarations");
  auto player=h.host.NewInstance("com/unity3d/player/UnityPlayer");context->BindUnityPlayer(player);
  auto context_field=h.host.GetObjectFieldValue(player,"mContext","Landroid/content/Context;"),current=h.call(145,h.find("com/unity3d/player/UnityPlayer"),h.field("com/unity3d/player/UnityPlayer","currentActivity","Landroid/app/Activity;",true));
  Check(h.call(24,context_field,activity)&&h.call(24,current,activity),"actual Activity/currentActivity/mContext facts are bound before AR call");
  bool repeated=false;try{context->BindUnityPlayer(player);}catch(const std::invalid_argument&){repeated=true;}Check(repeated,"binding cannot reset an existing player context or AR state");
  auto result=h.run("java_google_ar",{h.host.EnvAddress(),player});
  Check(profile!=2&&!result,"actual PM metadata controls disabled branch; enabled AR must terminate at the explicit native-side-effect boundary");
  Check(!h.host.GetObjectFieldValue(player,"m_ARCoreApi","Lcom/unity3d/player/GoogleARCoreApi;")&&h.host.PendingException().empty(),"disabled/unsupported AR creates no fake API or native success");
  unsupported=false;try{h.host.DefineBooleanMethod("com/unity3d/player/UnityPlayer","initializeGoogleAr","()Z",[](addr_t,const bunker::jni::Host::MethodArguments&){return false;});}catch(const std::invalid_argument&){unsupported=true;}Check(unsupported,"existing DefineBooleanMethod duplicate behavior is preserved");
  unsupported=false;try{h.host.BindBooleanMethod("com/unity3d/player/UnityPlayer","initializeGoogleAr","()Z",[](addr_t,const bunker::jni::Host::MethodArguments&){return false;});}catch(const std::invalid_argument&){unsupported=true;}Check(unsupported,"existing method implementation cannot be overwritten");
  // Remove every Activity edge before testing the independent resolver lease.
  h.host.SetObjectFieldValue(player,"mContext","Landroid/content/Context;",0);
  h.call(154,h.find("com/unity3d/player/UnityPlayer"),h.field("com/unity3d/player/UnityPlayer","currentActivity","Landroid/app/Activity;",true),0);
  h.host.DeleteLocalReference(context_field);h.host.DeleteLocalReference(current);
  h.host.DeleteLocalReference(activity);h.host.DeleteLocalReference(resolver);h.host.DeleteGlobalReference(global_activity);context.reset();
  Check(!h.call(24,weak,0)&&h.call(24,held,weak),"native GlobalRef alone retains resolver after context and all Activity edges are released");
  h.host.DeleteGlobalReference(held);Check(h.call(24,weak,0),"resolver expires after its last real reference is deleted; no provider root leaks it");
 }
 std::printf("Java initialization: %u checks passed; actual NDK resolver/interface/AR callers, exact APK metadata, typed non-instantiation, identity/lifetimes/threads and enabled-path failure\n",checks);
}

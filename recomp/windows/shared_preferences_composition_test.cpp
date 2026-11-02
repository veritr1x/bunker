// Regression for game11's real Context/Assets + Preferences class collision.
// Setup only: no guest native initialization and no preference backing I/O.
#include "android_context.h"
#include "android_shared_preferences.h"
#include "windows_shared_preferences.h"
#include "android_asset_pack_wrapper.h"
#include "jni_interface_proxy.h"
#include "java_native_libraries.h"
#include "apk_assets.h"
#include "unity_bootstrap_data.h"
#include <cstdio>
#include <stdexcept>
using namespace bunker::windows;
namespace {
unsigned checks=0;
void Check(bool p,const char*why){if(!p)throw std::runtime_error(why);++checks;}
addr_t Env(bunker::jni::Host&h,size_t n,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(n,s);Check(h.PendingException().empty(),"composition setup JNI healthy");return s.gpr.x0.qword;}
}
int main(){
 bunker::jni::Host host([](addr_t){return false;});DefineUnityJavaCatalog(host);
 host.DefineClass("android/os/Build$VERSION",{},"java/lang/Object",true);host.DefineField("android/os/Build$VERSION","SDK_INT","I",true);auto sdk=Env(host,6,reinterpret_cast<addr_t>("android/os/Build$VERSION"));auto field=Env(host,144,sdk,reinterpret_cast<addr_t>("SDK_INT"),reinterpret_cast<addr_t>("I"));Env(host,159,sdk,field,33);Check(Env(host,150,sdk,field)==33,"actual game SDK33 profile readback");host.DeleteLocalReference(sdk);
 auto app=Env(host,6,reinterpret_cast<addr_t>("com/unity3d/player/UnityPlayer")),clazz=Env(host,6,reinterpret_cast<addr_t>("java/lang/Class"));auto method=Env(host,33,clazz,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));auto loader=Env(host,34,app,method);
 JavaNativeLibraries libraries(host,JavaNativeLibraries::Config{loader,app,{{u"unity",u"/data/app/bunker/lib/arm64/libunity.so"},{u"il2cpp",u"/data/app/bunker/lib/arm64/libil2cpp.so"}}});for(auto x:{app,clazz,loader})host.DeleteLocalReference(x);
 AndroidContextConfig config;config.package_name=kPackageName;config.target_sdk=kTargetSdk;config.activity_class=kLaunchActivity;ApplyUnityPackageMetadata(config);config.apk_assets=std::make_shared<ApkAssets>(PREFS_APK);
 AndroidContext context(host,config);auto actual=context.Activity();
 unsigned reads=0,writes=0;auto backend=MakeWindowsSharedPreferencesBackend(config.package_name);
 backend.read=[&](const std::u16string&)->std::optional<SharedPreferencesSnapshot>{++reads;throw std::runtime_error("composition setup must not access production preferences");};
 backend.write=[&](const std::u16string&,const SharedPreferencesSnapshot&)->uint32_t{++writes;throw std::runtime_error("composition setup must not write production preferences");};
 AndroidSharedPreferences preferences(host,actual,config.package_name,std::move(backend));host.DeleteLocalReference(actual);
 JniInterfaceProxy proxies(host);
 AndroidAssetPackWrapper wrapper(host,{kApkSha256,"b2be67185a866f3489146d9864ca40d1de5c2668037f026609890afe12940689",true});
 Check(!reads&&!writes,"exact real Context+APK Assets+Prefs+Proxy+Wrapper setup performs no preference backing I/O");
 auto exception=Env(host,6,reinterpret_cast<addr_t>("java/util/NoSuchElementException"));auto superclass=Env(host,10,exception);auto runtime=Env(host,6,reinterpret_cast<addr_t>("java/lang/RuntimeException"));Check(Env(host,24,superclass,runtime),"canonical exception keeps exact RuntimeException superclass");for(auto x:{exception,superclass,runtime})host.DeleteLocalReference(x);
 bool rejected=false;try{host.DefineClass("java/util/NoSuchElementException",{},"java/lang/RuntimeException",true);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"core strict duplicate declaration guard remains intact");
 preferences.CheckPersistence();proxies.CheckNoEnabledProxies();libraries.Revoke();
 std::printf("Composed game setup: %u checks passed; actual APK Java catalog + SDK33 + native catalog + Context/ApkAssets + Prefs + Proxy + AssetPackWrapper; no guest constructors or preferences I/O\n",checks);
}

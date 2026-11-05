#include "android_asset_pack_wrapper.h"
#include <mutex>
#include <stdexcept>
#include <unordered_set>
namespace bunker::windows {
namespace {
constexpr const char *kWrapper="com/unity3d/player/AssetPackManagerWrapper";
constexpr const char *kWrapperType="Lcom/unity3d/player/AssetPackManagerWrapper;";
constexpr const char *kInit="(Landroid/content/Context;)Lcom/unity3d/player/AssetPackManagerWrapper;";
constexpr const char *kManager="Lcom/google/android/play/core/assetpacks/AssetPackManager;";
constexpr const char *kApk="9ded0797ee607b6892b531ba3a02f4c4510774f5fe098ccada78ccff881c9209";
// The verified asset-only variant sets AudioManager.m_DisableAudio. Its four
// DEX containers and every other uncompressed APK entry remain identical.
constexpr const char *kAudioDisabledApk="36e15676053734a225f55bdf89acd375adaf298872d4d1dfc06c140e5a0ed394";
// The Windows presentation variant additionally disables Android Swappy.
// Its closed application-code catalog remains byte-identical.
constexpr const char *kWindowsPresentationApk="fd0d0d357a4e8c316d0e732783d795f0e100a675d0c7a0fcf252873deb84f538";
constexpr const char *kCatalog="b2be67185a866f3489146d9864ca40d1de5c2668037f026609890afe12940689";
constexpr const char *kReinit="AssetPackManagerWrapper.init() should be called only once. Use getInstance() instead.";
struct EmptyHashSet {std::unordered_set<uint64_t> contents;};
addr_t Env(jni::Host &h,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){::State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(slot,s);return s.gpr.x0.qword;}
void Healthy(jni::Host &h){if(!h.PendingException().empty())throw std::runtime_error("asset pack wrapper JNI operation failed: "+h.PendingException());}
}
struct AndroidAssetPackWrapper::State {
  jni::Host &host;std::recursive_mutex class_monitor;
  explicit State(jni::Host &h):host(h){}
  addr_t Init(addr_t clazz,addr_t context){
    (void)context; // The missing-class resolution throws before getInstance can read Context.
    std::lock_guard monitor(class_monitor);
    auto field=Env(host,144,clazz,reinterpret_cast<addr_t>("a"),reinterpret_cast<addr_t>(kWrapperType));Healthy(host);
    auto previous=Env(host,145,clazz,field);Healthy(host);
    if(previous){host.DeleteLocalReference(previous);host.ThrowException("java/lang/RuntimeException",std::u16string(kReinit,kReinit+std::char_traits<char>::length(kReinit)));return 0;}
    auto factory=Env(host,6,reinterpret_cast<addr_t>("com/google/android/play/core/assetpacks/AssetPackManagerFactory"));
    const auto exception=host.PendingException();
    if(factory||exception.rfind("java/lang/NoClassDefFoundError",0)!=0)
      throw std::runtime_error("asset pack wrapper unsupported PlayCore availability/class-loader profile");
    host.ClearException(); // Exact constructor catch; no factory call or pack result is manufactured.
    auto object=host.NewInstance(kWrapper);Healthy(host);
    auto set=host.NewHostInstance("java/util/HashSet",std::make_shared<EmptyHashSet>());Healthy(host);
    host.SetObjectFieldValue(object,"b",kManager,0);
    host.SetObjectFieldValue(object,"c","Ljava/util/HashSet;",set);
    host.SetObjectFieldValue(object,"d","Ljava/lang/Object;",0);Healthy(host);
    host.DeleteLocalReference(set);
    Env(host,154,clazz,field,object);Healthy(host);
    // The class monitor publication is the original notifyAll point. No
    // getInstance wait/interrupt implementation is advertised by this port.
    return object;
  }
  bool Missing(addr_t receiver){auto manager=host.GetObjectFieldValue(receiver,"b",kManager);Healthy(host);const bool missing=!manager;if(manager)host.DeleteLocalReference(manager);return missing;}
};
AndroidAssetPackWrapper::AndroidAssetPackWrapper(jni::Host &host,const Profile &profile){
  if((profile.apk_sha256!=kApk&&profile.apk_sha256!=kAudioDisabledApk&&profile.apk_sha256!=kWindowsPresentationApk)||profile.code_catalog_sha256!=kCatalog||!profile.apk_only_closed_application_code)
    throw std::runtime_error("asset pack wrapper unsupported or unknown complete APK code-catalog profile");
  Healthy(host);state_=std::make_shared<State>(host);std::weak_ptr<State> weak=state_;
  auto get=[weak]{auto state=weak.lock();if(!state)throw std::runtime_error("asset pack wrapper adapter owner expired");return state;};
  host.BindStaticObjectMethod(kWrapper,"init",kInit,[get](addr_t clazz,const jni::Host::MethodArguments &args){return get()->Init(clazz,args[0]);});
  host.BindBooleanMethod(kWrapper,"playCoreApiMissing","()Z",[get](addr_t receiver,const jni::Host::MethodArguments&){return get()->Missing(receiver);});
  host.DefineField(kWrapper,"a",kWrapperType,true);host.DefineField(kWrapper,"b",kManager);
  host.DefineField(kWrapper,"c","Ljava/util/HashSet;");host.DefineField(kWrapper,"d","Ljava/lang/Object;");
  // Bounded framework metadata: exact superclass chain and existing supported
  // Cloneable/Serializable facts. Set/Collection methods/graph are not declared.
  host.DefineClass("java/util/AbstractCollection",{},"java/lang/Object",true);
  host.DefineClass("java/util/AbstractSet",{},"java/util/AbstractCollection",true);
  host.DefineClass("java/util/HashSet",{},"java/util/AbstractSet",true,{"java/lang/Cloneable","java/io/Serializable"});
  host.MarkClassInitialized(kWrapper); // DEX has no <clinit>; static a's default is null.
}
AndroidAssetPackWrapper::~AndroidAssetPackWrapper()=default; // No Java/static/native cleanup; weak bodies expire.
}

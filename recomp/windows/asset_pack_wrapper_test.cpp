#include "android_asset_pack_wrapper.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "asset_pack_proof.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <stdexcept>
#include <thread>
using namespace bunker::windows;
namespace {
constexpr const char *kWrapper="com/unity3d/player/AssetPackManagerWrapper";
constexpr const char *kReinit="java/lang/RuntimeException: AssetPackManagerWrapper.init() should be called only once. Use getInstance() instead.";
std::atomic<unsigned> checks{0};
void Check(bool p,const char *why){if(!p)throw std::runtime_error(why);++checks;}
bool Executable(addr_t p){for(auto &t:kTraces)if(t.address==p)return true;return false;}
struct Session {
 recomp::Runtime runtime;bunker::jni::Host host{Executable};elf_image &image;
 explicit Session(elf_image&i,bool native=false):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));host.DefineClass("android/content/Context",{},"java/lang/Object",true);host.DefineClass("android/app/Activity",{},"android/content/Context",true);host.DefineClass(kWrapper,{{"init","(Landroid/content/Context;)Lcom/unity3d/player/AssetPackManagerWrapper;",true,native},{"playCoreApiMissing","()Z"},{"getInstance","()Lcom/unity3d/player/AssetPackManagerWrapper;",true,false},{"getAssetPackPath","(Ljava/lang/String;)Ljava/lang/String;"}});host.DefineClass("TEST/AssetPackProbe",{{"callback","()V",true,true},{"delete","()V",true,true}});}
 addr_t env(){return host.EnvAddress();}
 addr_t call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){::State s{};s.gpr.x0.qword=env();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
 addr_t find(const char*n){return call(6,reinterpret_cast<addr_t>(n));}
 addr_t run(const char*n,std::initializer_list<addr_t> args={}){alignas(16)std::array<uint8_t,65536> stack{};::State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t at=0;for(auto a:args)(s.gpr.*r[at++]).qword=a;const auto high=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.sp.qword=high;s.gpr.x30.qword=0xfeedffff;const auto pc=reinterpret_cast<addr_t>(elf_symbol(&image,n));Check(Executable(pc),"strict NDK asset function is actually translated");runtime.Run(s,pc);Check(s.gpr.sp.qword==high&&s.gpr.pc.qword==0xfeedffff,"strict NDK asset caller preserves PC/SP");return s.gpr.x0.qword;}
};
const char *activeApkSha256=kAssetApkSha256;
AndroidAssetPackWrapper::Profile Profile(){return{activeApkSha256,kAssetCatalogSha256,true};}
}
int main(int argc,char**argv){
#ifdef ASSET_DERIVED_APK_SHA256
 if(argc>1&&std::string(argv[1])=="--derived-profile"){activeApkSha256=ASSET_DERIVED_APK_SHA256;--argc;++argv;}
#endif
 elf_image image{};Check(!elf_load(ASSET_LIBRARY,0x78000000,nullptr,&image),"actual NDK asset wrapper fixture mapped");
 if(argc>1&&std::string(argv[1])=="--retired-owner"){Session h(image);addr_t object=0;{AndroidAssetPackWrapper adapter(h.host,Profile());object=h.run("asset_init",{h.env(),0,0});}h.run("asset_missing",{h.env(),object,0});throw std::runtime_error("expired owner boundary returned");}
 if(argc>1){Session h(image);auto p=Profile();std::string mode=argv[1];if(mode=="--changed-apk")p.apk_sha256[0]^=1;if(mode=="--unknown-code")p.code_catalog_sha256.clear();if(mode=="--present-code")p.code_catalog_sha256="present Factory definition";if(mode=="--open-scope")p.apk_only_closed_application_code=false;AndroidAssetPackWrapper adapter(h.host,p);if(mode=="--visible-factory")h.host.DefineClass("com/google/android/play/core/assetpacks/AssetPackManagerFactory");auto o=h.run("asset_init",{h.env(),0,0});if(mode=="--path")h.run("asset_path",{h.env(),o});if(mode=="--get-instance")h.run("asset_get_instance",{h.env()});throw std::runtime_error("expected asset wrapper boundary returned");}
 for(unsigned mode=0;mode<3;++mode){
  Session h(image);auto adapter=std::make_unique<AndroidAssetPackWrapper>(h.host,Profile());Check(!h.run("asset_TEST_register",{h.env()})&&h.host.PendingException().empty(),"real NDK TEST native methods registered");Check(h.host.NativeEntry("TEST/AssetPackProbe","delete","()V")==reinterpret_cast<addr_t>(elf_symbol(&image,"asset_TEST_delete")),"TEST native delete entry is actual fixture, never fake original address");
  Check(!h.run("asset_static",{h.env()}),"actual class-static singleton initially null");auto context=h.host.NewInstance("android/app/Activity");auto object=h.run("asset_init",{h.env(),mode==1?0:context,mode});Check(object&&h.host.PendingException().empty(),"missing-factory branch returns nonnull typed singleton direct/V/A, including original null Context behavior");Check(h.call(32,object,h.find(kWrapper)),"original wrapper result has real class type");auto global=h.host.NewGlobalReference(object),weak=h.call(226,object);h.host.DeleteLocalReference(object);auto published=h.run("asset_static",{h.env()});Check(h.call(24,published,global),"actual JNI static field owns exact factory result identity");h.host.DeleteLocalReference(published);
  Check(!h.run("asset_field",{h.env(),global,0})&&!h.run("asset_field",{h.env(),global,2}),"actual b and d fields retain original null values");auto set=h.run("asset_field",{h.env(),global,1});Check(set&&h.call(32,set,h.find("java/util/HashSet"))&&h.call(32,set,h.find("java/util/AbstractSet"))&&h.call(32,set,h.find("java/lang/Cloneable"))&&h.call(32,set,h.find("java/io/Serializable")),"constructor creates distinct owned typed HashSet with exact supported superclass/interface facts");auto setclass=h.call(31,set);Check(h.call(24,h.call(10,setclass),h.find("java/util/AbstractSet")),"HashSet direct superclass metadata is truthful");h.host.DeleteLocalReference(setclass);h.host.DeleteLocalReference(set);
  for(unsigned form=0;form<3;++form)Check(h.run("asset_missing",{h.env(),global,form})==1&&h.host.PendingException().empty(),"real b-null boolean body called through NDK direct/V/A");
  // TEST-only typed implementation probes the field-reading body; this does
  // not define a Factory or supply a production PlayCore manager/provider.
  h.host.DefineInterface("com/google/android/play/core/assetpacks/AssetPackManager",{});h.host.DefineClass("TEST/AssetManager",{},"java/lang/Object",false,{"com/google/android/play/core/assetpacks/AssetPackManager"});auto TEST_manager=h.host.NewInstance("TEST/AssetManager");h.host.SetObjectFieldValue(global,"b","Lcom/google/android/play/core/assetpacks/AssetPackManager;",TEST_manager);for(unsigned form=0;form<3;++form)Check(!h.run("asset_missing",{h.env(),global,form}),"TEST typed b mutation proves real field read, not constant missing-API result");h.host.SetObjectFieldValue(global,"b","Lcom/google/android/play/core/assetpacks/AssetPackManager;",0);h.host.DeleteLocalReference(TEST_manager);Check(h.run("asset_missing",{h.env(),global,mode})==1,"restoring actual b=null restores original query result");
  Check(!h.run("asset_init",{h.env(),context,mode})&&h.host.PendingException()==kReinit,"second actual init throws exact Java RuntimeException and returns null because exceptional");auto exception=h.run("asset_take_exception",{h.env()});Check(exception&&h.call(32,exception,h.find("java/lang/RuntimeException")),"strict NDK obtains genuine typed reinit throwable");h.host.DeleteLocalReference(exception);published=h.run("asset_static",{h.env()});Check(h.call(24,published,global),"reinit exception does not replace or clear published singleton");h.host.DeleteLocalReference(published);
  h.host.DeleteGlobalReference(global);Check(!h.call(24,weak,0),"class-static original Java root retains singleton after local/native GlobalRef drop");Check(!h.run("asset_TEST_counts"),"factory/field/query/reference release trigger no TEST callback or delete");adapter.reset();Check(!h.call(24,weak,0),"adapter retirement does not clear or own the original static singleton");Check(!h.run("asset_TEST_counts"),"adapter retirement invokes no native callbacks or cleanup");h.call(227,weak);
 }
 {Session h(image);AndroidAssetPackWrapper adapter(h.host,Profile());auto context=h.host.NewGlobalReference(h.host.NewInstance("android/app/Activity"));std::atomic<unsigned> successes{0},failures{0};std::array<addr_t,4> winners{};std::vector<std::thread> workers;
  for(unsigned i=0;i<4;++i)workers.emplace_back([&,i]{::State state{};addr_t env=0;state.gpr.x0.qword=h.host.VmAddress();state.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,state);Check(!state.gpr.x0.qword&&env,"concurrent NDK caller really attached");auto object=h.run("asset_init",{env,context,i%3});if(object){winners[i]=h.host.NewGlobalReference(object);++successes;}else{Check(h.host.PendingException()==kReinit,"serialized losing init keeps exact original exception");h.host.ClearException();++failures;}state={};state.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,state);Check(!state.gpr.x0.qword,"actual concurrent JNI caller detaches");});
  for(auto &w:workers)w.join();Check(successes==1&&failures==3,"class-monitor serialization publishes one real singleton, all other init calls throw");auto published=h.run("asset_static",{h.env()});for(auto w:winners)if(w){Check(h.call(24,published,w),"actual winning GlobalRef equals class-static publication");h.host.DeleteGlobalReference(w);}h.host.DeleteLocalReference(published);h.host.DeleteGlobalReference(context);
 }
 {Session h(image);AndroidAssetPackWrapper adapter(h.host,Profile());bool rejected=false;try{AndroidAssetPackWrapper duplicate(h.host,Profile());}catch(const std::invalid_argument&e){rejected=std::string(e.what()).find("existing unimplemented nonnative")!=std::string::npos;}Check(rejected,"existing method duplicate binding guard preserved");}
 {Session h(image,true);bool rejected=false;try{AndroidAssetPackWrapper native(h.host,Profile());}catch(const std::invalid_argument&e){rejected=std::string(e.what()).find("existing unimplemented nonnative")!=std::string::npos;}Check(rejected,"existing native-method binding guard preserved");}
 std::printf("AssetPack wrapper: %u checks passed; exact missing-factory constructor/static lifecycle and concurrent NDK direct/V/A; no pack callbacks or delivery\n",checks.load());
}

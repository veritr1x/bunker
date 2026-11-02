#include "package_test_session.h"
#include "windows_android_id.h"
#include <atomic>
#include <memory>
#ifdef _WIN32
#include <windows.h>
#endif
using namespace bunker::windows;
namespace {
unsigned checks=0;
void Check(bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;}
AndroidContextConfig Config(){AndroidContextConfig c;c.package_name=kPackageName;c.target_sdk=kTargetSdk;c.activity_class=kLaunchActivity;return c;}
#ifdef _WIN32
void Registry(){
  std::wstring package=L"test.bunker.settings.p"+std::to_wstring(GetCurrentProcessId())+L"t"+std::to_wstring(GetTickCount64());
  const std::wstring app=L"Software\\Bunker\\Apps\\"+package,path=app+L"\\SecureSettings";
  auto reader=MakeWindowsAndroidIdReader(std::u16string(package.begin(),package.end()));
  Check(!reader(),"actual missing Windows registry key returns absence");
  struct Owned {
    std::wstring app;bool owned=false;
    ~Owned(){if(owned){HKEY root=nullptr;if(!RegOpenKeyExW(HKEY_CURRENT_USER,L"Software\\Bunker\\Apps",0,KEY_ALL_ACCESS|KEY_WOW64_64KEY,&root)){RegDeleteTreeW(root,app.c_str());RegCloseKey(root);}}}
  } cleanup{package};
  HKEY key=nullptr;DWORD disposition=0;
  Check(RegCreateKeyExW(HKEY_CURRENT_USER,app.c_str(),0,nullptr,0,KEY_READ|KEY_WRITE|KEY_WOW64_64KEY,nullptr,&key,&disposition)==ERROR_SUCCESS&&disposition==REG_CREATED_NEW_KEY,"test uniquely owns its temporary package key");cleanup.owned=true;RegCloseKey(key);
  Check(RegCreateKeyExW(HKEY_CURRENT_USER,path.c_str(),0,nullptr,0,KEY_READ|KEY_WRITE|KEY_WOW64_64KEY,nullptr,&key,&disposition)==ERROR_SUCCESS,"create only test-owned settings key");
  struct Close {HKEY &key;~Close(){if(key)RegCloseKey(key);}} close{key};
  Check(!reader(),"actual missing named registry value returns absence");
  for(const std::wstring value:{L"",L"0123456789abcdef",L"AbCdEf0011223344"}){
    Check(!RegSetValueExW(key,L"android_id",0,REG_SZ,reinterpret_cast<const BYTE*>(value.c_str()),(value.size()+1)*sizeof(wchar_t)),"test stores explicit fixture String");
    auto actual=reader();Check(actual&&*actual==std::u16string(value.begin(),value.end()),"actual stored String/empty returned unchanged");
  }
  DWORD number=7;Check(!RegSetValueExW(key,L"android_id",0,REG_DWORD,reinterpret_cast<BYTE*>(&number),sizeof(number)),"test stores unsupported type");
  bool rejected=false;try{reader();}catch(const std::runtime_error&){rejected=true;}Check(rejected,"wrong registry type fails rather than masquerading as absence");
  const wchar_t broken[]={L'1',L'2'};Check(!RegSetValueExW(key,L"android_id",0,REG_SZ,reinterpret_cast<const BYTE*>(broken),sizeof(broken)),"test stores malformed unterminated String");
  rejected=false;try{reader();}catch(const std::runtime_error&){rejected=true;}Check(rejected,"unterminated registry String fails explicitly");
  std::vector<wchar_t> oversized(32769,L'1');oversized.back()=0;Check(!RegSetValueExW(key,L"android_id",0,REG_SZ,reinterpret_cast<const BYTE*>(oversized.data()),oversized.size()*sizeof(wchar_t)),"test stores bounded oversized fixture");
  rejected=false;try{reader();}catch(const std::runtime_error&){rejected=true;}Check(rejected,"oversized registry String fails rather than truncating");
  Check(!RegDeleteValueW(key,L"android_id")&&!reader(),"actual deletion restores real missing-value result");
  RegCloseKey(key);key=nullptr;
  Check(!RegDeleteTreeW(HKEY_CURRENT_USER,path.c_str())&&!reader(),"actual key deletion restores missing-key result");
  Check(!RegDeleteTreeW(HKEY_CURRENT_USER,app.c_str()),"remove only the uniquely test-owned package subtree");cleanup.owned=false;
}
#endif
}
int main(int argc,char **argv){
  elf_image image{};Check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual strict NDK fixture loads");
  if(argc>1){
    Session h(image);auto c=Config();std::string mode=argv[1];
    if(mode!="--unset")c.read_android_id=[]()->std::optional<std::u16string>{return u"fixture-only-value";};
    if(mode=="--backend-error")c.read_android_id=[]()->std::optional<std::u16string>{throw std::runtime_error("explicit settings backing read error");};
    AndroidContext context(h.host,c);auto r=h.run("secure_resolver",{h.host.EnvAddress(),context.Activity()});auto key=h.run("secure_android_id_constant",{h.host.EnvAddress()});
    if(mode=="--unknown-key")key=h.host.NewString(u"unimplemented_setting");
    if(mode=="--null-key")key=0;
    if(mode=="--null-resolver")r=0;
    if(mode=="--unrecognized-resolver")r=h.host.NewInstance("android/content/ContentResolver");
    h.run("secure_get",{h.host.EnvAddress(),r,key,1});throw std::runtime_error("negative settings boundary returned success");
  }
  for(const auto &value:std::vector<std::optional<std::u16string>>{{},u"",u"fixture-only-0123456789abcdef"}){
    Session h(image);auto c=Config();auto calls=std::make_shared<std::atomic<unsigned>>(0);auto life=std::make_shared<int>(1);std::weak_ptr<int> weak_life=life;
    c.read_android_id=[value,calls,life](){++*calls;return value;};life.reset();
    auto context=std::make_unique<AndroidContext>(h.host,c);c.read_android_id={};auto activity=context->Activity();
    auto resolver=h.run("secure_resolver",{h.host.EnvAddress(),activity});auto constant=h.run("secure_android_id_constant",{h.host.EnvAddress()});
    Check(h.text(constant)==u"android_id","actual NDK static ANDROID_ID field is SDK key, not an ID value");
    Check(h.call(24,h.call(10,h.find("android/provider/Settings$Secure")),h.find("android/provider/Settings$NameValueTable")),"framework static class hierarchy metadata matches");
    auto held=h.host.NewGlobalReference(resolver),weak=h.call(226,resolver);
    for(unsigned mode=0;mode<3;++mode){
      auto out=h.run("secure_get",{h.host.EnvAddress(),resolver,constant,mode});
      Check(value?out&&h.text(out)==*value:!out,"actual direct/V/A caller preserves absent/empty/nonempty backing result");
      Check(h.host.PendingException().empty(),"normal registry absence produces no Java error");
      if(out){auto weak_result=h.call(226,out);h.host.DeleteLocalReference(out);Check(h.call(24,weak_result,0),"fresh result caller-local has no fabricated provider root");h.call(227,weak_result);}
    }
    Check(*calls==3,"each call invokes the actual configured reader without manufactured result caching");
    std::atomic<bool> worker_ok{false};auto global_key=h.host.NewGlobalReference(constant);
    std::thread worker([&]{State s{};addr_t env=0;s.gpr.x0.qword=h.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,s);auto out=h.run("secure_get",{env,held,global_key,2});worker_ok=value?out&&h.text(out)==*value:!out;if(out)h.host.DeleteLocalReference(out);s={};s.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,s);});worker.join();Check(worker_ok,"attached worker calls real resolver backing with owned reference arguments");
    h.host.DeleteLocalReference(activity);h.host.DeleteLocalReference(resolver);context.reset();
    Check(!weak_life.expired()&&!h.call(24,weak,0),"resolver GlobalRef alone retains actual backing after wrapper/Activity release");
    auto after=h.run("secure_get",{h.host.EnvAddress(),held,global_key,0});Check(value?after&&h.text(after)==*value:!after,"retained resolver backing remains callable after wrapper destruction");if(after)h.host.DeleteLocalReference(after);
    h.host.DeleteGlobalReference(held);Check(weak_life.expired()&&h.call(24,weak,0),"backing lifetime ends with last real resolver reference");h.call(227,weak);h.host.DeleteGlobalReference(global_key);h.host.DeleteLocalReference(constant);
  }
  for(const auto &bad:std::vector<std::u16string>{u"",u"../escape",u"test\\other",u"a..b",u".a"}){bool rejected=false;try{MakeWindowsAndroidIdReader(bad);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"registry namespace cannot escape exact application key");}
#ifdef _WIN32
  Registry();
#endif
  std::printf("Settings Secure: %u checks passed; actual NDK static field/direct/V/A, real absent/value semantics and resolver ownership\n",checks);
}

// Reuse the established callback/ABI observers and unchanged legacy component.
#include "../fastaes/elfload.h"
static int LifetimeLegacyLoad(const char*,uintptr_t,elf_resolver,struct elf_image*);
#define elf_load LifetimeLegacyLoad
#define main FirebaseLegacyMain
#define ObserveGetProcAddress LegacyObserveGetProcAddress
#include "firebase_app_test.cpp"
#undef ObserveGetProcAddress
#undef main
#undef elf_load
static elf_resolver lifetime_legacy_resolver=nullptr;
static void *LifetimeLegacyResolve(const char*n){
 static const char*names[]={"Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath","Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0","Firebase_App_CSharp_FirebaseApp_NameInternal_get","Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal"};
 for(unsigned i=0;i<4;i++)if(!strcmp(n,names[i]))return reinterpret_cast<void*>(0x7fef00000000ULL+8*(18+i));
 return lifetime_legacy_resolver(n);
}
static int LifetimeLegacyLoad(const char*p,uintptr_t b,elf_resolver resolve,struct elf_image*i){lifetime_legacy_resolver=resolve;return elf_load(p,b,&LifetimeLegacyResolve,i);}
namespace {
using ConfigFn=void(*)(const char*);using CreateFn=void*(*)();using NameFn=const char*(*)(void*);using ReleaseFn=void(*)(void*);
ConfigFn real_config=nullptr;CreateFn real_create=nullptr;NameFn real_name=nullptr;ReleaseFn real_release=nullptr;
unsigned config_calls=0,create_calls=0,name_calls=0,release_calls=0;
std::string observed_config;void *observed_create=nullptr,*observed_name_app=nullptr,*observed_release_app=nullptr;
void ObserveConfig(const char*p){++config_calls;observed_config=p?p:"";real_config(p);}
void *ObserveCreate(){++create_calls;observed_create=real_create();return observed_create;}
const char *ObserveName(void*p){++name_calls;observed_name_app=p;return real_name(p);}
void ObserveRelease(void*p){++release_calls;observed_release_app=p;real_release(p);}
FARPROC WINAPI LifetimeGetProcAddress(HMODULE h,LPCSTR n){auto p=LegacyObserveGetProcAddress(h,n);if(p&&reinterpret_cast<uintptr_t>(n)>65535){
#define NEW_OBS(NAME,REAL,OBSERVER) if(!strcmp(n,NAME)){memcpy(&REAL,&p,sizeof(REAL));auto q=&OBSERVER;memcpy(&p,&q,sizeof(q));}
NEW_OBS("Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath",real_config,ObserveConfig)
NEW_OBS("Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0",real_create,ObserveCreate)
NEW_OBS("Firebase_App_CSharp_FirebaseApp_NameInternal_get",real_name,ObserveName)
NEW_OBS("Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal",real_release,ObserveRelease)
#undef NEW_OBS
}return p;}
void NativeException(const char*){}void NativeArgument(const char*,const char*){}
}
int main(int argc,char**argv){
 if(argc==2&&!strcmp(argv[1],"legacy"))return FirebaseLegacyMain(1,argv);
 if(argc==2&&!strcmp(argv[1],"foreign"))return FirebaseLegacyMain(argc,argv);
 try{
  const bool missing=argc==2&&!strcmp(argv[1],"missing");
  Check(sizeof(State)==1200&&sizeof(addr_t)==8,"State1200/Memory64 preserved");
  __wrap___imp_GetProcAddress=&LifetimeGetProcAddress;
  const std::wstring dll=FIREBASE_DLL;Check(Sha(dll)==FirebaseAppService::kDllSha256,"official SDK bytes pinned before raw reference load");
  HMODULE native=LoadLibraryExW(dll.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);Check(native!=nullptr,"real pinned DLL reference load");
  auto re=Fn<RE>(native,"SWIGRegisterExceptionCallbacks_AppUtil");re(NativeException,NativeException,NativeException,NativeException,NativeException,NativeException,NativeException,NativeException,NativeException,NativeException,NativeException);
  Fn<RB>(native,"SWIGRegisterExceptionArgumentCallbacks_AppUtil")(NativeArgument,NativeArgument,NativeArgument);
  auto rs=Fn<void(*)(S)>(native,"SWIGRegisterStringCallback_AppUtil");rs(&NativeCopy);
  Fn<void(*)(L)>(native,"Firebase_App_CSharp_SetLogFunction")(nullptr);Fn<void(*)(int32_t)>(native,"Firebase_App_CSharp_SetLogLevel")(4);
  const std::string path=missing?FIREBASE_EMPTY_CONFIG:FIREBASE_CONFIG;
  Fn<ConfigFn>(native,"Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath")(path.c_str());
  auto raw_create=Fn<CreateFn>(native,"Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0");
  auto raw_release=Fn<ReleaseFn>(native,"Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal");
  auto raw_name=Fn<NameFn>(native,"Firebase_App_CSharp_FirebaseApp_NameInternal_get");
  void *raw=raw_create();const bool native_positive=raw!=nullptr;std::string expected_name;
  if(raw){const char *name=raw_name(raw);Check(name!=nullptr,"genuine reference App name exists");expected_name=name;std::free(const_cast<char*>(name));raw_release(raw);}
  if(!missing)Check(native_positive,"byte-exact original APK desktop configuration creates a genuine native App");
  rs(nullptr);re(nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr);Fn<RB>(native,"SWIGRegisterExceptionArgumentCallbacks_AppUtil")(nullptr,nullptr,nullptr);
  config_calls=create_calls=name_calls=release_calls=0;
  recomp::Runtime runtime;elf_image image{};
  std::map<std::string,addr_t> imports;addr_t next=0x7fee00000100ULL;
  auto resolve=[&](const char*n)->void*{if(!strcmp(n,"TEST_replay"))return reinterpret_cast<void*>(replay_marker);if(!strcmp(n,"malloc"))return reinterpret_cast<void*>(malloc_marker);if(!strcmp(n,"free"))return reinterpret_cast<void*>(free_marker);auto [it,added]=imports.emplace(n,next);if(added)next+=8;return reinterpret_cast<void*>(it->second);};
  // elf_load requires a plain resolver; its binding below is this single owner.
  static std::function<void*(const char*)> resolver;resolver=resolve;
  Check(!elf_load(FIREBASE_GUEST,0x62000000,[](const char*n){return resolver(n);},&image),"actual direct/pointer NDK App caller ELF mapped");runtime.AddTraces(kTraces,std::size(kTraces));
  std::map<void*,size_t> owned;
  runtime.AddImport(malloc_marker,recomp::MakeBridge<addr_t(addr_t)>([&](addr_t n){void*p=std::malloc(n);Check(p&&owned.emplace(p,n).second,"callback C allocation owned");recomp::InvalidateGuestMemory(A(p),n);++allocations;return A(p);}));
  runtime.AddImport(free_marker,recomp::MakeBridge<void(addr_t)>([&](addr_t p){auto it=owned.find(reinterpret_cast<void*>(p));Check(it!=owned.end(),"original-style caller frees actual returned C allocation");recomp::InvalidateGuestMemory(p,it->second);std::free(it->first);owned.erase(it);++frees;}));
  auto execute=[&](addr_t entry,const std::vector<addr_t>&args){++calls;alignas(16)std::array<unsigned char,65536>stack{};State s{};const auto top=A(stack.data()+stack.size()-128);Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};for(size_t i=0;i<args.size();i++)if(i<8)(s.gpr.*r[i]).qword=args[i];else memcpy(reinterpret_cast<void*>(top+8*(i-8)),&args[i],8);s.gpr.sp.qword=top;s.gpr.x30.qword=0xfeed7830;s.gpr.x19.qword=0xfedcba9876543210ULL;s.gpr.x29.qword=0xabcdef0123456789ULL;std::array<uint64_t,8> memory{};const auto copy=memory;auto*token=reinterpret_cast<Memory*>(memory.data());Check(runtime.Run(s,entry,token)==token&&memory==copy,"NDK opaque Memory64 and bytes unchanged");Check(s.gpr.pc.qword==0xfeed7830&&s.gpr.sp.qword==top&&s.gpr.x19.qword==0xfedcba9876543210ULL&&s.gpr.x29.qword==0xabcdef0123456789ULL,"NDK return/SP/callee-save high64 unchanged");return s.gpr.x0.qword;};
  auto sym=[&](const char*n){auto p=A(elf_symbol(&image,n));Check(p&&runtime.HasGuestTrace(p),"actual translated NDK entry exists");return p;};
  const std::string virtual_path="jar:file:///data/app/bunker/base.apk!/assets";unsigned mappings=0;
  FirebaseAppService service({dll,[&](const std::wstring&p,const std::string&sha){Check(sha==FirebaseAppService::kDllSha256&&Sha(p)==sha,"requested/loaded native DLL bytes exact");++verified;},[&](addr_t e,const std::vector<addr_t>&a){++callback_runs;return execute(e,a);},[]{return recomp::CurrentExecutionState()!=nullptr;},[&](addr_t p){return runtime.HasGuestTrace(p);},[&](const std::string&p){if(p==virtual_path){++mappings;return path;}return p;}});
  for(const auto&n:service.Commands()){sdk_markers.insert(service.Marker(n));}
  service.Install(runtime);
  for(auto [name,marker]:imports){Check(marker==imports.at(name),"NDK import identity stable");runtime.AddImport(marker,[&,name](State&s){Preserve([&]{service.Invoke(name,s);return uint64_t(0);});});}
  auto run=[&](const char*n,std::initializer_list<addr_t>a){return execute(sym(n),std::vector<addr_t>(a));};
  std::array<uint64_t,48> record{};
  run("register_all",{service.Marker("SWIGRegisterExceptionCallbacks_AppUtil"),service.Marker("SWIGRegisterExceptionArgumentCallbacks_AppUtil"),service.Marker("SWIGRegisterStringCallback_AppUtil"),service.Marker("Firebase_App_CSharp_SetLogFunction"),A(record.data())});
  bool reentry_checked=false;
  runtime.AddImport(replay_marker,recomp::MakeBridge<void()>([&]{if(reentry_checked)return;reentry_checked=true;for(auto name:{"Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath","Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0","Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal"}){bool rejected=false;try{State s{};s.gpr.x0.qword=A(path.c_str());service.Invoke(name,s);}catch(const std::exception&){rejected=true;}Check(rejected,"App operations reject reentrant string-callback mutation before native call");}}));
  run("default_name",{service.Marker("Firebase_App_CSharp_FirebaseApp_DefaultName_get")});Check(reentry_checked,"real SDK callback exercised reentrant App rejection");
  std::vector<addr_t> apps;
  for(int form=0;form<2;form++){
   run("app_config",{A(form?virtual_path.c_str():path.c_str()),addr_t(form)});Check(observed_config==path,"native config path uses unchanged real path or exact qualified virtual-folder mapping");
   const auto app=run("app_create",{addr_t(form)});Check(app==A(observed_create)&&bool(app)==native_positive,"actual NDK default-create result equals genuine native result");
   if(app){apps.push_back(app);Check(run("app_name",{app,addr_t(form)})==Hash(expected_name.c_str())&&A(observed_name_app)==app,"App name flows through genuine SDK and allocating/freeing translated callback");}
  }
  const auto before_release=release_calls,before_name=name_calls;
  for(auto name:{"Firebase_App_CSharp_FirebaseApp_NameInternal_get","Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal"}){bool rejected=false;try{State s{};s.gpr.x0.qword=0x12345678;service.Invoke(name,s);}catch(const std::exception&){rejected=true;}Check(rejected,"unowned forged App rejected before native use");}
  Check(release_calls==before_release&&name_calls==before_name,"invalid handles never reach the native DLL");
  if(!apps.empty()){
   bool rejected=false;try{service.Revoke();}catch(const std::exception&){rejected=true;}Check(rejected&&saved_s,"live App references block revoke without clearing callbacks");
   run("app_release",{apps[0],0});Check(A(observed_release_app)==apps[0],"direct release forwards exact native App handle");
   Check(run("app_name",{apps[1],1})==Hash(expected_name.c_str()),"remaining genuine create reference keeps App alive after first release");
   run("app_release",{apps[1],1});Check(A(observed_release_app)==apps[1],"pointer release forwards exact native App handle");
   for(auto name:{"Firebase_App_CSharp_FirebaseApp_NameInternal_get","Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal"}){bool stale=false;try{State s{};s.gpr.x0.qword=apps[1];service.Invoke(name,s);}catch(const std::exception&){stale=true;}Check(stale,"last released App handle is rejected");}
  }
  Check(mappings==1,"only the exact virtual streamingAssets folder is mapped");Check(owned.empty()&&allocations==frees,"every returned SDK name allocation freed by actual NDK caller");service.CheckHealthy();service.Revoke();
  std::printf("FIREBASE-APP-LIFETIME-PASS checks=%u NDK_calls=%u callbacks=%u positive=%u creates=%u names=%u releases=%u config_calls=%u allocations=%u frees=%u commands=%zu State=%zu Memory64=%zu mode=%s\n",checks,calls,callback_runs,unsigned(native_positive),create_calls,name_calls,release_calls,config_calls,allocations,frees,service.Commands().size(),sizeof(State),sizeof(addr_t),missing?"missing":"original-config");
  return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"FIREBASE-APP-LIFETIME-FAIL %s\n",e.what());return 1;}
}

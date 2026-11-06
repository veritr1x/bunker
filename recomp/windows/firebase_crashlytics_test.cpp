// Transparent native SDK observers plus actual translated NDK callers.
#define main FirebaseLegacyMain
#include "firebase_app_test.cpp"
#undef main
#include "tracked_memory_test.h"
namespace {
RE crash_real_e=nullptr;RB crash_real_b=nullptr;void(*crash_real_s)(S)=nullptr;
std::array<E,11> crash_e{};std::array<B,3> crash_b{};S crash_s=nullptr;
void CrashE(E a,E b,E c,E d,E e,E f,E g,E h,E i,E j,E k){crash_e={a,b,c,d,e,f,g,h,i,j,k};crash_real_e(a,b,c,d,e,f,g,h,i,j,k);}
void CrashB(B a,B b,B c){crash_b={a,b,c};crash_real_b(a,b,c);}
void CrashS(S s){crash_s=s;crash_real_s(s);}
using InstanceFn=void*(*)(void*,int32_t*);InstanceFn native_instance=nullptr;
unsigned instance_calls=0;void *last_instance=nullptr;int32_t *last_out=nullptr;int32_t last_status=0;
void *Instance(void*a,int32_t*r){++instance_calls;last_out=r;last_instance=native_instance(a,r);last_status=*r;return last_instance;}
uint32_t(*native_size)(void*)=nullptr;using Getter=const char*(*)(void*);
std::array<Getter,4> getters{};void *probe_frame=nullptr;unsigned probe_field=0;const char *probe_string=nullptr;
uint32_t Size(void*v){auto n=native_size(v);if(probe_frame){probe_string=getters[probe_field](probe_frame);probe_frame=nullptr;}return n;}
FARPROC WINAPI CrashGetProcAddress(HMODULE h,LPCSTR n){auto p=ObserveGetProcAddress(h,n);if(p&&reinterpret_cast<uintptr_t>(n)>65535){
#define OBS_CRASH(NAME,REAL,OBSERVER) if(!strcmp(n,NAME)){memcpy(&REAL,&p,sizeof(REAL));auto q=&OBSERVER;memcpy(&p,&q,sizeof(q));}
 OBS_CRASH("SWIGRegisterExceptionCallbacks_CrashlyticsInternal",crash_real_e,CrashE)
 OBS_CRASH("SWIGRegisterExceptionArgumentCallbacks_CrashlyticsInternal",crash_real_b,CrashB)
 OBS_CRASH("SWIGRegisterStringCallback_CrashlyticsInternal",crash_real_s,CrashS)
 OBS_CRASH("Firebase_Crashlytics_CSharp_FirebaseCrashlyticsInternal_GetInstance__SWIG_0",native_instance,Instance)
 OBS_CRASH("Firebase_Crashlytics_CSharp_StackFrames_size",native_size,Size)
#undef OBS_CRASH
 }return p;}
void NativeE(const char*){}void NativeB(const char*,const char*){}
constexpr addr_t crash_replay_marker=0x7fee00000028ULL,take_string_marker=0x7fee00000030ULL;
}
int main(int argc,char**argv){try{
 const bool foreign=argc==2&&!strcmp(argv[1],"foreign");
 __wrap___imp_GetProcAddress=CrashGetProcAddress;
 const std::wstring dll=FIREBASE_DLL;Check(Sha(dll)==FirebaseAppService::kDllSha256,"pinned genuine desktop SDK");
 HMODULE native=LoadLibraryExW(dll.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);Check(native!=nullptr,"actual SDK load");
 auto app_e=Fn<RE>(native,"SWIGRegisterExceptionCallbacks_AppUtil");app_e(NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE);
 Fn<RB>(native,"SWIGRegisterExceptionArgumentCallbacks_AppUtil")(NativeB,NativeB,NativeB);Fn<void(*)(S)>(native,"SWIGRegisterStringCallback_AppUtil")(&NativeCopy);
 auto cre=Fn<RE>(native,"SWIGRegisterExceptionCallbacks_CrashlyticsInternal");cre(NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE,NativeE);
 Fn<RB>(native,"SWIGRegisterExceptionArgumentCallbacks_CrashlyticsInternal")(NativeB,NativeB,NativeB);Fn<void(*)(S)>(native,"SWIGRegisterStringCallback_CrashlyticsInternal")(&NativeCopy);
 Fn<void(*)(L)>(native,"Firebase_App_CSharp_SetLogFunction")(nullptr);Fn<void(*)(int32_t)>(native,"Firebase_App_CSharp_SetLogLevel")(4);
 const std::string config=FIREBASE_CONFIG;Fn<void(*)(const char*)>(native,"Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath")(config.c_str());
 auto raw_create=Fn<void*(*)()>(native,"Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0");auto raw_release=Fn<void(*)(void*)>(native,"Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal");
 void *raw=raw_create();Check(raw!=nullptr,"authentic APK desktop configuration creates actual App");int32_t expected_status=0x12345678;
 Check(Fn<InstanceFn>(native,"Firebase_Crashlytics_CSharp_FirebaseCrashlyticsInternal_GetInstance__SWIG_0")(raw,&expected_status)!=nullptr,"genuine raw desktop GetInstance nonnull");raw_release(raw);
 for(unsigned i=0;i<4;i++){const char *fields[]={"library","symbol","fileName","lineNumber"};auto n=std::string("Firebase_Crashlytics_CSharp_FirebaseCrashlyticsFrame_")+fields[i]+"_get";auto p=RealGetProcAddress(native,n.c_str());Check(p!=nullptr,"genuine extra getter for transparent string callback fixture only");memcpy(&getters[i],&p,sizeof(Getter));}
 instance_calls=0;
 recomp::Runtime runtime;elf_image image{};std::map<std::string,addr_t> imports;addr_t next=0x7fee00000100ULL;
 static std::function<void*(const char*)> resolver;resolver=[&](const char*n)->void*{if(!strcmp(n,"TEST_replay"))return reinterpret_cast<void*>(replay_marker);if(!strcmp(n,"TEST_crash_replay"))return reinterpret_cast<void*>(crash_replay_marker);if(!strcmp(n,"TEST_take_string"))return reinterpret_cast<void*>(take_string_marker);if(!strcmp(n,"malloc"))return reinterpret_cast<void*>(malloc_marker);if(!strcmp(n,"free"))return reinterpret_cast<void*>(free_marker);auto[it,added]=imports.emplace(n,next);if(added)next+=8;return reinterpret_cast<void*>(it->second);};
 Check(!elf_load(FIREBASE_GUEST,0x62000000,[](const char*n){return resolver(n);},&image),"real direct/pointer NDK caller ELF");runtime.AddTraces(kTraces,std::size(kTraces));
 std::map<void*,size_t>owned;
 runtime.AddImport(malloc_marker,recomp::MakeBridge<addr_t(addr_t)>([&](addr_t n){auto*p=std::malloc(n);Check(p&&owned.emplace(p,n).second,"translated callback allocation");recomp::InvalidateGuestMemory(A(p),n);++allocations;return A(p);}));
 runtime.AddImport(free_marker,recomp::MakeBridge<void(addr_t)>([&](addr_t p){auto it=owned.find(reinterpret_cast<void*>(p));Check(it!=owned.end(),"exact returned allocating callback pointer freed by NDK");recomp::InvalidateGuestMemory(p,it->second);std::free(it->first);owned.erase(it);++frees;}));
 runtime.AddImport(replay_marker,recomp::MakeBridge<void()>([]{}));
 runtime.AddImport(take_string_marker,recomp::MakeBridge<addr_t()>([]{Check(probe_string!=nullptr,"actual extra getter returned allocated string");auto p=A(probe_string);probe_string=nullptr;return p;}));
 auto execute=[&](addr_t entry,const std::vector<addr_t>&args){++calls;alignas(16)std::array<unsigned char,65536>stack{};State s{};const auto top=A(stack.data()+stack.size()-128);Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};for(size_t i=0;i<args.size();i++)if(i<8)(s.gpr.*r[i]).qword=args[i];else memcpy(reinterpret_cast<void*>(top+8*(i-8)),&args[i],8);s.gpr.sp.qword=top;s.gpr.x30.qword=0xfeed7830;s.gpr.x19.qword=0xfedcba9876543210ULL;s.gpr.x29.qword=0xabcdef0123456789ULL;reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;std::array<uint64_t,8>memory;memory.fill(0xa7a7a7a7a7a7a7a7ULL);auto copy=memory;auto*token=reinterpret_cast<Memory*>(memory.data());Check(runtime.Run(s,entry,token)==token&&memory==copy,"Memory64 token and bytes preserved");Check(s.gpr.pc.qword==0xfeed7830&&s.gpr.sp.qword==top&&s.gpr.x19.qword==0xfedcba9876543210ULL&&s.gpr.x29.qword==0xabcdef0123456789ULL&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"State1200 return/SP/high64/terminal guard");return s.gpr.x0.qword;};
 auto sym=[&](const char*n){auto p=A(elf_symbol(&image,n));Check(p&&runtime.HasGuestTrace(p),"actual translated NDK entry");return p;};
 const std::string virtual_path="jar:file:///data/app/bunker/base.apk!/assets";unsigned mappings=0;
 FirebaseAppService service({dll,[&](const std::wstring&p,const std::string&sha){Check(sha==FirebaseAppService::kDllSha256&&Sha(p)==sha,"requested/loaded SDK bytes exact");++verified;},[&](addr_t e,const std::vector<addr_t>&a){++callback_runs;return execute(e,a);},[]{return recomp::CurrentExecutionState()!=nullptr;},[&](addr_t p){return runtime.HasGuestTrace(p);},[&](const std::string&p){if(p==virtual_path){++mappings;return config;}return p;}});
 for(const auto&n:service.Commands())sdk_markers.insert(service.Marker(n));
 service.Install(runtime);
 for(auto[name,marker]:imports)runtime.AddImport(marker,[&,name](State&s){Preserve([&]{service.Invoke(name,s);return uint64_t(0);});});
 auto run=[&](const char*n,std::initializer_list<addr_t>a){return execute(sym(n),std::vector<addr_t>(a));};
 auto reject=[&](const char*n,std::initializer_list<addr_t>a){bool rejected=false;try{run(n,a);}catch(const std::exception&){rejected=true;}Check(rejected,"invalid/lifetime operation rejected before native use");};
 std::array<uint64_t,48>app_record{},cr{};
 run("register_all",{service.Marker("SWIGRegisterExceptionCallbacks_AppUtil"),service.Marker("SWIGRegisterExceptionArgumentCallbacks_AppUtil"),service.Marker("SWIGRegisterStringCallback_AppUtil"),service.Marker("Firebase_App_CSharp_SetLogFunction"),A(app_record.data())});
 const auto old_e=saved_e;const auto old_b=saved_b;const auto old_s=saved_s;
 for(int form=0;form<2;form++)run("crash_register",{A(cr.data()),addr_t(form)});
 Check(saved_e==old_e&&saved_b==old_b&&saved_s==old_s,"Crash registration leaves all App callback slots unchanged");
 for(unsigned i=0;i<11;i++)Check(crash_e[i]&&crash_e[i]!=saved_e[i],"separate exception-family C thunks");
 for(unsigned i=0;i<3;i++)Check(crash_b[i]&&crash_b[i]!=saved_b[i],"separate argument-family C thunks");
 Check(crash_s&&crash_s!=saved_s,"separate string-family C thunk");
 if(foreign){crash_e[0]("foreign");bool caught=false;try{service.CheckHealthy();}catch(const std::exception&){caught=true;}Check(caught&&cr[0]==0,"foreign Crash callback never executes guest or unwinds across DLL");service.Revoke();std::printf("FIREBASE-CRASH-FOREIGN-PASS checks=%u\n",checks);return 0;}
 bool replayed=false;runtime.AddImport(crash_replay_marker,recomp::MakeBridge<void()>([&]{if(replayed)return;replayed=true;for(auto cb:crash_e)cb("crash-route");for(auto cb:crash_b)cb("crash-argument","crash-parameter");for(auto cb:saved_e)cb("app-route");for(auto cb:saved_b)cb("app-argument","app-parameter");}));
 run("app_config",{A(virtual_path.c_str()),1});Check(mappings==1,"qualified config callback resolves exact original file directory");
 std::array<addr_t,2>apps{},instances{};alignas(16)std::array<int32_t,4>status{0x13572468,0x12345678,0x24681357,0x76543210};
 for(int form=0;form<2;form++){apps[form]=run("app_create",{addr_t(form)});Check(apps[form]!=0,"real App reference");auto reserved=bunker::test::ReserveAcrossOperation(A(&status[1]),4,[&]{instances[form]=run("crash_instance",{apps[form],A(&status[1]),addr_t(form)});});Check(reserved.status!=0,"GetInstance tracked guest status publication invalidates exclusive reservation");Check(instances[form]==A(last_instance)&&instances[form]&&status[1]==last_status&&status[1]==expected_status,"real SDK instance/status forwarded without platform rewrite");Check(last_out!=&status[1]&&status[0]==0x13572468&&status[2]==0x24681357&&status[3]==0x76543210,"native output targets local int32 and preserves guest neighbors");}
 Check(apps[0]==apps[1],"genuine default App creates hold two native references to same pointer");const auto before=instance_calls;
 reject("crash_instance",{0x1234,A(&status[1]),0});reject("crash_instance",{apps[0],0,1});Check(instance_calls==before,"bad App/status never reaches SDK");
 std::array<addr_t,2>frames{},vectors{};const char*fields[]={"lib-fixture","symbol-fixture","source-fixture","123:45"};
 for(int form=0;form<2;form++){frames[form]=run("crash_new",{0,addr_t(form)});vectors[form]=run("crash_new",{1,addr_t(form)});Check(frames[form]&&vectors[form],"genuine owned Frame/vector native allocations");for(int field=0;field<4;field++){std::string transient=fields[field];run("crash_set",{frames[form],A(transient.c_str()),addr_t(field),addr_t(form)});}for(int field=0;field<4;field++){std::string churn(4096,'x');probe_frame=reinterpret_cast<void*>(frames[form]);probe_field=field;Check(run("crash_probe",{vectors[form],addr_t(form)})==Hash(fields[field]),"SDK owns copied UTF8 field including string lineNumber; actual Crash allocating callback/free");}run("crash_add",{vectors[form],frames[form],addr_t(form)});Check(run("crash_size",{vectors[form],addr_t(form)})==1,"native vector size uint32 exact");auto borrowed=run("crash_item",{vectors[form],0,addr_t(form)});Check(borrowed!=0,"genuine borrowed item pointer");reject("crash_delete",{borrowed,0,addr_t(form)});run("crash_add",{vectors[form],frames[form],addr_t(form)});reject("crash_set",{borrowed,A("must reject"),0,addr_t(form)});Check(run("crash_size",{vectors[form],addr_t(form)})==2,"native vector Add direct/pointer");for(int event=0;event<4;event++)run("crash_event",{instances[form],A("local-fixture"),A("local-value"),vectors[form],addr_t(event),addr_t(form)});}
 for(unsigned i=0;i<11;i++)Check(cr[i]==1&&app_record[i]==1&&cr[20+i]==Hash("crash-route")&&app_record[20+i]==Hash("app-route"),"all11 family slots including AArch64 stack routes isolated");
 for(unsigned i=0;i<3;i++)Check(cr[11+i]==1&&app_record[11+i]==1&&cr[31+i]==Hash("crash-argument")&&app_record[31+i]==Hash("app-argument"),"all3 family argument routes isolated");
 auto empty=run("crash_new",{1,0});auto before_errors=cr;auto before_app=app_record;Check(run("crash_item",{empty,7,1})==0,"actual out-of-range SDK returns null");unsigned errors=0,error_slot=99;for(unsigned i=0;i<14;i++){auto count=unsigned(cr[i]-before_errors[i]);errors+=count;if(count)error_slot=i;}Check(errors==1&&app_record==before_app,"genuine SDK argument failure reaches Crash family only");std::printf("GENUINE-CRASH-ERROR slot=%u message_hash=%llu\n",error_slot,static_cast<unsigned long long>(cr[20+error_slot]));run("crash_delete",{empty,1,0});
 bool live_reject=false;try{service.Revoke();}catch(const std::exception&){live_reject=true;}Check(live_reject&&crash_s,"live native owned objects prevent premature revoke");
 run("app_release",{apps[0],0});run("crash_event",{instances[0],A("still-live"),0,0,0,0});
 run("app_release",{apps[1],1});for(auto i:instances)reject("crash_event",{i,A("released"),0,0,0,0});
 bool frame_revoke=false;try{service.Revoke();}catch(const std::exception&){frame_revoke=true;}Check(frame_revoke&&crash_s,"owned Frame/vector objects block revoke after all App references released");
 for(int form=0;form<2;form++){auto borrowed=run("crash_item",{vectors[form],0,addr_t(form)});run("crash_delete",{vectors[form],1,addr_t(form)});reject("crash_set",{borrowed,A("deleted-vector"),0,0});run("crash_delete",{frames[form],0,addr_t(form)});reject("crash_delete",{frames[form],0,addr_t(form)});}
 Check(owned.empty()&&allocations==frees&&allocations==8,"all eight actual Crash string callback allocations freed by real NDK callers");service.CheckHealthy();service.Revoke();Check(!crash_s&&!saved_s&&std::all_of(crash_e.begin(),crash_e.end(),[](E e){return !e;}),"quiescent revoke clears both native callback families");
 std::printf("FIREBASE-CRASH-PASS checks=%u NDK_calls=%u callbacks=%u allocations=%u frees=%u instance_calls=%u native_status=%d commands=%zu State=%zu Memory64=%zu\n",checks,calls,callback_runs,allocations,frees,instance_calls,expected_status,service.Commands().size(),sizeof(State),sizeof(addr_t));return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"FIREBASE-CRASH-FAIL %s\n",e.what());return 1;}}

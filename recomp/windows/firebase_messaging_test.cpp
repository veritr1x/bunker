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
constexpr addr_t crash_replay_marker=0x7fee00000028ULL,take_string_marker=0x7fee00000030ULL;
}
namespace {
using MC=int32_t(*)(void*);using TC=void(*)(const char*);
RE msg_real_e=nullptr;RB msg_real_b=nullptr;void(*msg_real_s)(S)=nullptr;
std::array<E,11>msg_e{};std::array<B,3>msg_b{};S msg_s=nullptr;MC msg_callback=nullptr;TC token_callback=nullptr;
void MsgE(E a,E b,E c,E d,E e,E f,E g,E h,E i,E j,E k){msg_e={a,b,c,d,e,f,g,h,i,j,k};msg_real_e(a,b,c,d,e,f,g,h,i,j,k);}
void MsgB(B a,B b,B c){msg_b={a,b,c};msg_real_b(a,b,c);}void MsgS(S s){msg_s=s;msg_real_s(s);}
void(*real_listener)(MC,TC)=nullptr;void(*real_enabled)(uint32_t,uint32_t)=nullptr;void(*real_send)()=nullptr;void(*real_delete)(void*)=nullptr;
void*(*raw_new)()=nullptr;const char*(*raw_get)(void*)=nullptr;void(*raw_set)(void*,const char*)=nullptr;
unsigned listener_calls=0,poll_calls=0,service_deletes=0,SDK_contract_deletes=0;uint32_t enabled_message=0,enabled_token=0;
int probe=0;void *observed_message=nullptr;const char *observed_token=nullptr;int32_t observed_result=0;
void MsgListener(MC m,TC t){++listener_calls;msg_callback=m;token_callback=t;real_listener(m,t);}
void MsgEnabled(uint32_t m,uint32_t t){enabled_message=m;enabled_token=t;real_enabled(m,t);}
void MsgDelete(void*p){++service_deletes;real_delete(p);}
// The observer calls the real selected SDK API first. Extra callback invocations
// are explicit local ABI/ownership fixtures; no message is queued or sent.
void MsgSend(){++poll_calls;real_send();const int action=probe;probe=0;
 if(action==1){observed_message=raw_new();Check(observed_message&&msg_callback,"real local Message and registered thunk");observed_result=msg_callback(observed_message);if(!observed_result){++SDK_contract_deletes;real_delete(observed_message);}}
 if(action==2){auto p=raw_new();Check(p&&token_callback,"real local string field fixture");raw_set(p,"local ABI text; not a registration token");observed_token=raw_get(p);Check(observed_token!=nullptr,"genuine SDK getter allocated through registered Messaging string callback");token_callback(observed_token);real_delete(p);}
}
FARPROC WINAPI MessagingGetProcAddress(HMODULE h,LPCSTR n){auto p=CrashGetProcAddress(h,n);if(p&&reinterpret_cast<uintptr_t>(n)>65535){
#define MSG_OBS(NAME,REAL,OBSERVER) if(!strcmp(n,NAME)){memcpy(&REAL,&p,sizeof(REAL));auto q=&OBSERVER;memcpy(&p,&q,sizeof(q));}
 MSG_OBS("SWIGRegisterExceptionCallbacks_FirebaseMessaging",msg_real_e,MsgE)
 MSG_OBS("SWIGRegisterExceptionArgumentCallbacks_FirebaseMessaging",msg_real_b,MsgB)
 MSG_OBS("SWIGRegisterStringCallback_FirebaseMessaging",msg_real_s,MsgS)
 MSG_OBS("Firebase_Messaging_CSharp_SetListenerCallbacks",real_listener,MsgListener)
 MSG_OBS("Firebase_Messaging_CSharp_SetListenerCallbacksEnabled",real_enabled,MsgEnabled)
 MSG_OBS("Firebase_Messaging_CSharp_SendPendingEvents",real_send,MsgSend)
 MSG_OBS("Firebase_Messaging_CSharp_delete_FirebaseMessage",real_delete,MsgDelete)
#undef MSG_OBS
 }return p;}
constexpr addr_t msg_replay_marker=0x7fee00000038ULL;
}
int main(int argc,char**argv){try{
 const bool foreign=argc==2&&!strcmp(argv[1],"foreign");__wrap___imp_GetProcAddress=MessagingGetProcAddress;
 const std::wstring dll=FIREBASE_DLL;Check(Sha(dll)==FirebaseAppService::kDllSha256,"pinned genuine SDK");const std::string config=FIREBASE_CONFIG;
 recomp::Runtime runtime;elf_image image{};std::map<std::string,addr_t>imports;addr_t next=0x7fee00000100ULL;
 static std::function<void*(const char*)>resolver;resolver=[&](const char*n)->void*{if(!strcmp(n,"TEST_replay"))return reinterpret_cast<void*>(replay_marker);if(!strcmp(n,"TEST_crash_replay"))return reinterpret_cast<void*>(crash_replay_marker);if(!strcmp(n,"TEST_take_string"))return reinterpret_cast<void*>(take_string_marker);if(!strcmp(n,"TEST_messaging_replay"))return reinterpret_cast<void*>(msg_replay_marker);if(!strcmp(n,"malloc"))return reinterpret_cast<void*>(malloc_marker);if(!strcmp(n,"free"))return reinterpret_cast<void*>(free_marker);auto[it,added]=imports.emplace(n,next);if(added)next+=8;return reinterpret_cast<void*>(it->second);};
 Check(!elf_load(FIREBASE_GUEST,0x62000000,[](const char*n){return resolver(n);},&image),"actual translated NDK Messaging caller ELF");runtime.AddTraces(kTraces,std::size(kTraces));
 std::map<void*,size_t>owned;
 runtime.AddImport(malloc_marker,recomp::MakeBridge<addr_t(addr_t)>([&](addr_t n){auto*p=std::malloc(n);Check(p&&owned.emplace(p,n).second,"actual translated string allocation");recomp::InvalidateGuestMemory(A(p),n);++allocations;return A(p);}));
 runtime.AddImport(free_marker,recomp::MakeBridge<void(addr_t)>([&](addr_t p){auto it=owned.find(reinterpret_cast<void*>(p));Check(it!=owned.end(),"exact SDK string allocation freed by translated receiver");recomp::InvalidateGuestMemory(p,it->second);std::free(it->first);owned.erase(it);++frees;}));
 runtime.AddImport(replay_marker,recomp::MakeBridge<void()>([]{}));runtime.AddImport(crash_replay_marker,recomp::MakeBridge<void()>([]{}));runtime.AddImport(take_string_marker,recomp::MakeBridge<addr_t()>([]{return addr_t(0);}));
 auto execute=[&](addr_t entry,const std::vector<addr_t>&args){++calls;alignas(16)std::array<unsigned char,65536>stack{};State s{};const auto top=A(stack.data()+stack.size()-128);Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};for(size_t i=0;i<args.size();i++)if(i<8)(s.gpr.*r[i]).qword=args[i];else memcpy(reinterpret_cast<void*>(top+8*(i-8)),&args[i],8);s.gpr.sp.qword=top;s.gpr.x30.qword=0xfeed7830;s.gpr.x19.qword=0xfedcba9876543210ULL;s.gpr.x29.qword=0xabcdef0123456789ULL;reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;std::array<uint64_t,8>memory;memory.fill(0xa7a7a7a7a7a7a7a7ULL);auto copy=memory;auto*token=reinterpret_cast<Memory*>(memory.data());Check(runtime.Run(s,entry,token)==token&&memory==copy,"NDK Memory64 token and bytes preserved");Check(s.gpr.pc.qword==0xfeed7830&&s.gpr.sp.qword==top&&s.gpr.x19.qword==0xfedcba9876543210ULL&&s.gpr.x29.qword==0xabcdef0123456789ULL&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"State1200/SP/PC/high64 and terminal byte preserved");return s.gpr.x0.qword;};
 auto sym=[&](const char*n){auto p=A(elf_symbol(&image,n));Check(p&&runtime.HasGuestTrace(p),"actual NDK translated symbol");return p;};
 FirebaseAppService service({dll,[&](const std::wstring&p,const std::string&h){Check(h==FirebaseAppService::kDllSha256&&Sha(p)==h,"actual requested and loaded DLL bytes");++verified;},[&](addr_t e,const std::vector<addr_t>&a){++callback_runs;return execute(e,a);},[]{return recomp::CurrentExecutionState()!=nullptr;},[&](addr_t p){return runtime.HasGuestTrace(p);}});
 for(const auto&n:service.Commands())sdk_markers.insert(service.Marker(n));
 service.Install(runtime);for(auto[name,marker]:imports)runtime.AddImport(marker,[&,name](State&s){Preserve([&]{service.Invoke(name,s);return uint64_t(0);});});
 HMODULE native=GetModuleHandleW(dll.c_str());Check(native!=nullptr,"genuine SDK module");
 auto native_listener_slots=reinterpret_cast<const uintptr_t*>(reinterpret_cast<uintptr_t>(native)+0x9cae00);
 auto direct=[&](const char*n,auto&f){auto p=RealGetProcAddress(native,n);Check(p!=nullptr,"genuine test-only local Message export");memcpy(&f,&p,sizeof(f));};
 direct("Firebase_Messaging_CSharp_new_FirebaseMessage",raw_new);direct("Firebase_Messaging_CSharp_FirebaseMessage_To_get",raw_get);direct("Firebase_Messaging_CSharp_FirebaseMessage_To_set",raw_set);
 auto run=[&](const char*n,std::initializer_list<addr_t>a){return execute(sym(n),std::vector<addr_t>(a));};
 auto reject=[&](const char*n,std::initializer_list<addr_t>a){bool caught=false;try{run(n,a);}catch(const std::exception&){caught=true;}Check(caught,"unowned/detached/lifetime operation rejected before native call");};
 std::array<uint64_t,48>app{},cr{},msg{};
 run("register_all",{service.Marker("SWIGRegisterExceptionCallbacks_AppUtil"),service.Marker("SWIGRegisterExceptionArgumentCallbacks_AppUtil"),service.Marker("SWIGRegisterStringCallback_AppUtil"),service.Marker("Firebase_App_CSharp_SetLogFunction"),A(app.data())});run("crash_register",{A(cr.data()),0});
 const auto app_e=saved_e;const auto app_b=saved_b;const auto app_s=saved_s;const auto old_crash_e=crash_e;const auto old_crash_b=crash_b;const auto old_crash_s=crash_s;
 for(int form=0;form<2;form++)run("messaging_register",{A(msg.data()),addr_t(form)});
 Check(saved_e==app_e&&saved_b==app_b&&saved_s==app_s&&crash_e==old_crash_e&&crash_b==old_crash_b&&crash_s==old_crash_s,"Messaging registration preserves both original callback families");
 for(unsigned i=0;i<11;i++)Check(msg_e[i]&&msg_e[i]!=saved_e[i]&&msg_e[i]!=crash_e[i],"third independent exception-family thunk");
 for(unsigned i=0;i<3;i++)Check(msg_b[i]&&msg_b[i]!=saved_b[i]&&msg_b[i]!=crash_b[i],"third independent argument-family thunk");
 Check(msg_s&&msg_s!=saved_s&&msg_s!=crash_s,"third independent string-family thunk");
 if(foreign){msg_e[0]("foreign routing fixture");bool caught=false;try{service.CheckHealthy();}catch(const std::exception&){caught=true;}Check(caught&&msg[0]==0,"foreign Messaging callback fails without guest execution or DLL unwind");service.Revoke();std::printf("FIREBASE-MESSAGING-FOREIGN-PASS checks=%u\n",checks);return 0;}
 bool replayed=false;runtime.AddImport(msg_replay_marker,recomp::MakeBridge<void()>([&]{if(replayed)return;replayed=true;for(auto e:msg_e)e("messaging-route");for(auto b:msg_b)b("messaging-argument","parameter");for(auto e:saved_e)e("app-route");for(auto b:saved_b)b("app-argument","parameter");for(auto e:crash_e)e("crash-route");for(auto b:crash_b)b("crash-argument","parameter");}));
 reject("messaging_listener",{3,0});run("app_config",{A(config.c_str()),0});std::array<addr_t,2>apps{};for(int form=0;form<2;form++){apps[form]=run("app_create",{addr_t(form)});Check(apps[form]!=0,"real default App native reference");}
 Check(apps[0]==apps[1],"actual two default App references share SDK pointer");
 for(int form=0;form<2;form++){
  run("messaging_listener",{3,addr_t(form)});Check(msg_callback&&token_callback,"actual genuine listener callback registration");
  for(auto bits:{0u,1u,0x80000000u}){run("messaging_enabled",{bits,bits,addr_t(form)});Check(enabled_message==unsigned(bits!=0)&&enabled_token==unsigned(bits!=0),"actual native SWIG bool32 normalization");}
  auto before_message=msg[16],before_token=msg[17];run("messaging_poll",{addr_t(form)});Check(msg[16]==before_message&&msg[17]==before_token,"genuine desktop empty poll creates no invented message/token");
  probe=2;run("messaging_poll",{addr_t(form)});Check(msg[19]==A(observed_token)&&msg[41]==Hash("local ABI text; not a registration token"),"actual SDK getter allocating callback pointer reaches translated receiver unchanged and is freed exactly once");
  for(unsigned mode=0;mode<4;mode++){
   msg[42]=mode;msg[43]=0x81234567;auto sd=service_deletes,nd=SDK_contract_deletes;probe=1;run("messaging_poll",{addr_t(form)});auto pointer=A(observed_message);Check(msg[18]==pointer,"actual local native Message pointer passed unchanged to original-style callback");Check(observed_result==(mode==0||mode==3?0:static_cast<int32_t>(0x81234567)),"signed32 native ownership result preserved exactly");
   if(mode==1){Check(service_deletes==sd&&SDK_contract_deletes==nd,"accepted message remains owned until actual guest disposal");run("messaging_delete",{pointer,addr_t(form)});Check(service_deletes==sd+1,"retained native message genuine delete");}
   else if(mode==2)Check(service_deletes==sd+1&&SDK_contract_deletes==nd,"synchronous guest Dispose accepted: one genuine deferred native delete");
   else Check(service_deletes==sd&&SDK_contract_deletes==nd+1,"declined message, including pending Dispose, retains SDK exactly-one-delete contract");
   reject("messaging_delete",{pointer,addr_t(form)});
  }
  run("messaging_listener",{0,addr_t(form)});Check(!msg_callback&&!token_callback,"both-null clear reaches genuine SDK");
 }
 for(unsigned i=0;i<11;i++)Check(app[i]==1&&cr[i]==1&&msg[i]==1&&app[20+i]==Hash("app-route")&&cr[20+i]==Hash("crash-route")&&msg[20+i]==Hash("messaging-route"),"all11 callback slots and AArch64 stack args remain family-isolated");
 for(unsigned i=0;i<3;i++)Check(app[11+i]==1&&cr[11+i]==1&&msg[11+i]==1,"all3 argument slots remain family-isolated");
 reject("messaging_delete",{0x12345678,0});auto frame=run("crash_new",{0,0});reject("messaging_delete",{frame,1});run("crash_delete",{frame,0,0});
 run("messaging_listener",{3,0});msg[42]=1;msg[43]=1;probe=1;run("messaging_poll",{0});auto retained=A(observed_message);
 run("app_release",{apps[0],0});reject("app_release",{apps[1],1});Check(msg_callback&&token_callback,"last-release guard leaves real listener attached");
 for(int form=0;form<2;form++){
  run("messaging_listener",{1,addr_t(form)});Check(msg_callback&&!token_callback&&native_listener_slots[0]==0&&native_listener_slots[1]==reinterpret_cast<uintptr_t>(msg_callback)&&native_listener_slots[2]==0,"actual SDK stores message-only callback and has no Listener allocation");
  reject("app_release",{apps[1],addr_t(form)});auto old_messages=msg[16],old_tokens=msg[17];msg[42]=2;msg[43]=0x12345678;probe=1;run("messaging_poll",{addr_t(form)});Check(msg[16]==old_messages+1&&msg[17]==old_tokens&&observed_result==0x12345678,"partial message slot retains real App and admits pending-delivery callback ABI");
  run("messaging_listener",{2,addr_t(form)});Check(!msg_callback&&token_callback&&native_listener_slots[0]==0&&native_listener_slots[1]==0&&native_listener_slots[2]==reinterpret_cast<uintptr_t>(token_callback),"actual SDK stores token-only callback and has no Listener allocation");
  reject("app_release",{apps[1],addr_t(form)});old_messages=msg[16];old_tokens=msg[17];probe=2;run("messaging_poll",{addr_t(form)});Check(msg[16]==old_messages&&msg[17]==old_tokens+1&&msg[19]==A(observed_token),"partial token slot retains real App and exact allocating-callback pointer");
 }
 run("messaging_listener",{0,1});Check(native_listener_slots[0]==0&&native_listener_slots[1]==0&&native_listener_slots[2]==0,"both-null registration clears actual native listener and both callback slots");run("app_release",{apps[1],1});
 bool message_revoke=false;try{service.Revoke();}catch(const std::exception&){message_revoke=true;}Check(message_revoke&&msg_s,"retained native Message alone blocks revoke after listener detach and App release");run("messaging_delete",{retained,1});
 Check(allocations==frees&&allocations==4&&owned.empty(),"all genuine Messaging string returns freed by translated receivers");service.CheckHealthy();service.Revoke();Check(!msg_s&&!saved_s&&!crash_s&&!msg_callback&&!token_callback,"quiescent revoke clears listener and every family");
 std::printf("FIREBASE-MESSAGING-PASS checks=%u NDK_calls=%u callbacks=%u allocations=%u frees=%u listener_calls=%u polls=%u service_deletes=%u SDK_contract_deletes=%u commands=%zu State=%zu Memory64=%zu\n",checks,calls,callback_runs,allocations,frees,listener_calls,poll_calls,service_deletes,SDK_contract_deletes,service.Commands().size(),sizeof(State),sizeof(addr_t));return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"FIREBASE-MESSAGING-FAIL %s\n",e.what());return 1;}}

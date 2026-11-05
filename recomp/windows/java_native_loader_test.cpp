#include "java_native_loader.h"
#include "java_native_libraries.h"
#include "../fastaes/elfload.h"
#include "native_loader_traces.h"
#include <array>
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <exception>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>
using namespace bunker::windows;
namespace {
std::atomic<unsigned>checks{0},calls{0};
void Check(bool b,const char*why){++checks;if(!b)throw std::runtime_error(why);}
template<class F>void Reject(F f,const char*why){bool fail=false;try{f();}catch(const std::invalid_argument&){fail=true;}Check(fail,why);}
addr_t Env(bunker::jni::Host&h,size_t n,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(n,s);return s.gpr.x0.qword;}
addr_t Find(bunker::jni::Host&h,const char*n){return Env(h,6,reinterpret_cast<addr_t>(n));}
void Attach(bunker::jni::Host&h){State s{};addr_t env=0;s.gpr.x0.qword=h.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.InvokeVm(4,s);Check(s.gpr.x0.dword==0&&env,"actualJNIthreadattach");}
void Detach(bunker::jni::Host&h){State s{};s.gpr.x0.qword=h.VmAddress();h.InvokeVm(5,s);Check(s.gpr.x0.dword==0,"actualJNIthreaddetach");}
struct Fixture {
 recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};elf_image original{},noentry{};
 ModuleRegistry modules{[this](addr_t e){Run(e,{});}};std::unique_ptr<JavaNativeLibraries>catalog;std::unique_ptr<JavaNativeLoader>manager;
 addr_t loader=0,player=0,method=0;std::mutex mutex;std::condition_variable changed;bool parallel_entered=false,parallel_release=false;std::vector<JavaNativeLoader::Event>events;std::vector<std::u16string>diagnostics;
 Fixture(){
  host.Install(runtime);runtime.AddTraces(kLoaderTraces,std::size(kLoaderTraces));
  Check(!elf_load(NATIVE_LOADER_IMAGE,0x77000000,nullptr,&original),"actualNDKOnLoadELF");Check(!elf_load(NATIVE_LOADER_NOENTRY_IMAGE,0x78000000,nullptr,&noentry),"actualNDKELFwithoutOnLoad");
  host.DefineClass("com/unity3d/player/UnityPlayer",{{"loadLibrary","(Ljava/lang/String;)Z",false,false}});host.MarkClassInitialized("com/unity3d/player/UnityPlayer");
  host.DefineClass("test/LoaderHook");host.DefineStaticIntMethod("test/LoaderHook","onLoad","(I)I",[this](addr_t,const bunker::jni::Host::MethodArguments&a){
   if(a[0]==1)return manager->LoadForLoader(loader,u"recursive")?1:0;
   std::unique_lock lock(mutex);parallel_entered=true;changed.notify_all();changed.wait(lock,[&]{return parallel_release;});return 1;
  });host.MarkClassInitialized("test/LoaderHook");
  auto app=Find(host,"com/unity3d/player/UnityPlayer"),cl=Find(host,"java/lang/Class");auto get=Env(host,33,cl,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));auto local=Env(host,34,app,get);loader=host.NewGlobalReference(local);host.DeleteLocalReference(local);
  player=host.NewGlobalReference(host.NewInstance("com/unity3d/player/UnityPlayer"));method=Env(host,33,app,reinterpret_cast<addr_t>("loadLibrary"),reinterpret_cast<addr_t>("(Ljava/lang/String;)Z"));
  std::vector<JavaNativeLibraries::Library>paths;std::vector<JavaNativeLoader::Library>libs;
  for(auto name:{u"one",u"adopt",u"wrong",u"absent",u"freshabsent",u"bad",u"recursive",u"parallel",u"pending",u"pendinglower",u"error",u"legacy",u"unregistered"}){std::u16string u(name);std::string ascii(u.begin(),u.end());auto path="/test/lib"+ascii+".so";paths.push_back({u,std::u16string(path.begin(),path.end())});libs.push_back({u,path,(u==u"adopt"||u==u"wrong")?Entry("JNI_OnLoad"):0});}
  catalog=std::make_unique<JavaNativeLibraries>(host,JavaNativeLibraries::Config{loader,app,paths});
  for(const auto&lib:libs){if(lib.name==u"unregistered")continue;bool absent=lib.name==u"absent"||lib.name==u"freshabsent";auto&image=absent?noentry:original;
   Module m;m.name=lib.guest_path.substr(lib.guest_path.find_last_of('/')+1);m.aliases={lib.guest_path};m.initializers={reinterpret_cast<addr_t>(elf_symbol(&image,"loader_ctor"))};m.finalizers={reinterpret_cast<addr_t>(elf_symbol(&image,"loader_dtor"))};
   if(!absent){const char*n=lib.name==u"bad"?"loader_bad_onload":lib.name==u"recursive"?"loader_recursive_onload":lib.name==u"parallel"?"loader_parallel_onload":(lib.name==u"pending"||lib.name==u"pendinglower")?"loader_pending_onload":lib.name==u"error"?"loader_error_onload":lib.name==u"legacy"?"loader_legacy_onload":"JNI_OnLoad";m.exports.emplace("JNI_OnLoad",Entry(n));}modules.Add(std::move(m));
  }
  JavaNativeLoader::Config c;c.application_class=app;c.application_loader=loader;c.libraries=libs;c.runner=[this](addr_t e,const std::vector<addr_t>&a){return Run(e,a);};
  c.observer=[this](const JavaNativeLoader::Event&e){if(e.handle)Check(modules.IsOpenHandleFor(e.path,e.handle),"observerrunsoutsideprovidermanagerlocks");std::lock_guard lock(mutex);events.push_back(e);};
  c.diagnostic=[this](int level,const std::u16string&s){Check(level==6&&!s.empty(),"actualloadfailureseverity6");std::lock_guard lock(mutex);diagnostics.push_back(s);};
  manager=std::make_unique<JavaNativeLoader>(host,modules,c);
 }
 addr_t Entry(const char*n){auto e=reinterpret_cast<addr_t>(elf_symbol(&original,n));Check(e!=0,"originalNDKentryexists");return e;}
 uint64_t Run(addr_t e,const std::vector<addr_t>&a){alignas(16)std::array<unsigned char,65536>stack{};State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5};size_t i=0;for(auto v:a){(s.gpr.*regs[i++]).qword=v;}
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x123456789abcdef0;std::memset(&s.simd.v[31],0xa7,16);reinterpret_cast<unsigned char*>(&s)[1199]=0xd1;auto token=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);
  Check(runtime.Run(s,e,token)==token,"opaqueMemory64exact");Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x19.qword==0x123456789abcdef0,"NDKreturnPCSPcalleeSaved");
  Check(reinterpret_cast<unsigned char*>(&s.simd.v[31])[15]==0xa7&&reinterpret_cast<unsigned char*>(&s)[1199]==0xd1,"fullState1200SIMDhighcell");return s.gpr.x0.qword;
 }
 unsigned Count(unsigned n,bool absent=false){auto&image=absent?noentry:original;return unsigned(Run(reinterpret_cast<addr_t>(elf_symbol(&image,"loader_count")),{n}));}
 bool Call(const std::u16string&name,unsigned mode=0,addr_t receiver=0){auto s=host.NewString(name);auto result=Run(Entry("loader_call"),{host.EnvAddress(),receiver?receiver:player,method,s,mode});host.DeleteLocalReference(s);++calls;return result!=0;}
};
}
int main(){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16);Fixture f;
 auto h=f.modules.Open("/test/libadopt.so",2),wrong=f.modules.Open("/test/libwrong.so",2);Check(h&&wrong&&h!=wrong,"twomoduleswithsameOnLoadentry");Check(f.Run(f.Entry("JNI_OnLoad"),{f.host.VmAddress(),0})==bunker::jni::kVersion16,"independentlycompletedactualOnLoad");
 auto refs=f.modules.ReferenceCount("libadopt.so");Check(f.modules.IsOpenHandleFor("/test/libadopt.so",h)&&f.modules.IsOpenHandleFor("libadopt.so",h)&&!f.modules.IsOpenHandleFor("/test/libadopt.so",wrong),"exactaliasandleownerquery");
 f.modules.Open("/test/unavailable.so",2);Check(f.modules.IsOpenHandleFor("/test/libadopt.so",h)&&f.modules.ReferenceCount("libadopt.so")==refs,"querydoesnotopenorchangeRefs");Check(f.modules.Error()!=0,"querydoesnotclearpreviousdlerror");
 Reject([&]{f.manager->Adopt(u"adopt",wrong,bunker::jni::kVersion16);},"wronghandlewithsameOnLoadaddressrejected");Reject([&]{f.manager->Adopt(u"adopt",h,0x10001);},"Android13rejectscompletedJNI11adoption");Check(f.modules.ReferenceCount("libadopt.so")==refs,"JNI11adoptiondoesnotacquireref");f.manager->Adopt(u"adopt",h,bunker::jni::kVersion16);f.manager->BindUnityPlayer();
 auto before=f.Count(1);for(unsigned mode=0;mode<3;++mode)Check(f.Call(u"adopt",mode),"actualNDKdirectVAadoptedload");Check(f.Count(1)==before&&f.modules.ReferenceCount("libadopt.so")==refs,"adoptionnoOpennoOnLoadreplay");Reject([&]{f.manager->BindUnityPlayer();},"duplicatebindingrejected");
 auto ctor=f.Count(0),onload=f.Count(1);Check(f.Call(u"one")&&f.Call(u"one",2),"freshexactregisteredloadandcache");Check(f.Count(0)==ctor+1&&f.Count(1)==onload+1&&f.modules.ReferenceCount("libone.so")==1,"ctorandOnLoadonceonly");
 Check(!f.Call(u"unknown")&&!f.Call(u"../one")&&!f.Call(u"libone.so")&&!f.Call(u"unregistered"),"unknownnamesandunregisteredmodulefail");Check(f.host.PendingException().empty(),"wrapperfailurehasnocaughtJavaexceptionleak");
 Check(!f.Call(u"bad")&&!f.Call(u"bad",1)&&f.Count(2)==1&&f.modules.ReferenceCount("libbad.so")==1,"badversioncachedandmodulekeptalive");
 Check(!f.Call(u"legacy")&&!f.Call(u"legacy",2)&&f.Count(8)==1&&f.modules.ReferenceCount("liblegacy.so")==1&&f.host.PendingException().empty(),"actualJNI11OnLoadrejectedcachedandcaughtwithoutfinalization");
 Check(!elf_symbol(&f.noentry,"JNI_OnLoad"),"actualabsentELFhasnoOnLoadexport");auto absent=f.modules.Open("/test/libabsent.so",2);f.manager->Adopt(u"absent",absent,0);Check(f.Call(u"absent")&&f.Call(u"freshabsent")&&f.Call(u"freshabsent",1)&&f.Count(0,true)==2,"optionalOnLoadabsentfreshandadopted");
 Check(f.Call(u"recursive")&&f.Count(3)==1&&f.modules.ReferenceCount("librecursive.so")==1,"actualNDKOnLoadrecursionreusesinflightowner");
 std::exception_ptr first_error,second_error;bool first=false,second=false;std::thread a([&]{try{Attach(f.host);first=f.Call(u"parallel");Detach(f.host);}catch(...){first_error=std::current_exception();}});
 {std::unique_lock lock(f.mutex);f.changed.wait(lock,[&]{return f.parallel_entered;});}
 std::thread b([&]{try{Attach(f.host);second=f.Call(u"parallel",2);Detach(f.host);}catch(...){second_error=std::current_exception();}});
 {std::lock_guard lock(f.mutex);f.parallel_release=true;f.changed.notify_all();}a.join();b.join();if(first_error)std::rethrow_exception(first_error);if(second_error)std::rethrow_exception(second_error);
 Check(first&&second&&f.Count(4)==1&&f.modules.ReferenceCount("libparallel.so")==1,"concurrentJNIcallsoneactualOnLoad");
 auto foreign=f.host.NewInstance("java/lang/ClassLoader");Check(!f.manager->LoadForLoader(foreign,u"one"),"differentJavaloadercannotclaimlibrary");
 f.host.DefineClass("test/BootstrapPlayer",{},"com/unity3d/player/UnityPlayer",true);auto boot=f.host.NewInstance("test/BootstrapPlayer");Check(!f.Call(u"one",0,boot),"actualreceiverloaderchecked");
 auto oldref=f.modules.ReferenceCount("libone.so");f.host.ThrowException("java/lang/IllegalStateException",u"preserve incoming");auto pending=f.host.PendingException();auto exception=Env(f.host,15);Check(!f.manager->LoadForLoader(f.loader,u"one")&&f.host.PendingException()==pending&&f.modules.ReferenceCount("libone.so")==oldref,"incomingpendingpreservedandnoOpen");Check(Env(f.host,24,exception,Env(f.host,15))==1,"exactincomingThrowableidentity");f.host.ClearException();
 Check(!f.manager->LoadForLoader(f.loader,u"pendinglower")&&f.Count(5)==1&&f.host.PendingException().find("IllegalStateException")!=std::string::npos,"lowernativeoperationpreservesfreshThrowable");f.host.ClearException();
 Check(!f.Call(u"pending")&&f.Count(5)==2&&f.host.PendingException().empty(),"originalExceptioncaughtbyUnitywrapper");Check(!f.Call(u"pending")&&f.Count(5)==2,"caughtOnLoadfailurecached");
 Check(!f.Call(u"error")&&f.Count(6)==1&&f.host.PendingException().find("OutOfMemoryError")!=std::string::npos,"otherErrorpropagatesfromoriginalOnLoad");f.host.ClearException();
 Check(!f.diagnostics.empty(),"realfailedattemptdiagnosticsobserved");auto null_result=f.Run(f.Entry("loader_call"),{f.host.EnvAddress(),f.player,f.method,0,2});++calls;Check(!null_result&&f.host.PendingException().empty(),"originalnullStringcaughtaswrapperfalse");
 f.manager->Revoke();Check(!f.Call(u"one")&&f.modules.ReferenceCount("libone.so")==1&&f.Count(7)==0,"revocationnevershutdownsregisterednatives");
 unsigned adopted=0,recursive=0,cached=0;for(const auto&e:f.events){adopted+=e.adopted;recursive+=e.recursive;cached+=e.cached;}Check(adopted>=4&&recursive==1&&cached>=8,"observerexposesactualnameandcacheownership");
 std::printf("JAVA-NATIVE-LOADER-PASS checks=%u NDK_calls=%u constructors_and_OnLoad=actual State=1200 Memory64=1\n",checks.load(),calls.load());return 0;
}catch(const std::exception&e){std::fprintf(stderr,"Java native loader: %s\n",e.what());return 1;}}

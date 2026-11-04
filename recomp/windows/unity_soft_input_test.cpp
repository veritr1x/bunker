#include "unity_soft_input.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <future>
#include <queue>

using bunker::jni::Host;
using bunker::windows::UnitySoftInputSession;
namespace {
constexpr const char* Player="com/unity3d/player/UnityPlayer";
constexpr const char* Dialog="Lcom/unity3d/player/l;";
constexpr addr_t Area=0x7fe100001000,Visible=0x7fe100002000;
std::atomic<unsigned> checks{0},guest_calls{0},native_reports{0};
void Check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);++checks;}
template<class F> void Reject(F f,const char* why){bool caught=false;try{f();}catch(const std::exception&){caught=true;}Check(caught,why);}
struct Harness {
  recomp::Runtime runtime;Host host{[](addr_t p){return p==Area||p==Visible;}};elf_image& image;
  addr_t player=0,global=0,weak=0,hide=0;std::vector<int> reports;std::vector<addr_t> report_locals;
  std::thread::id report_owner;addr_t report_env=0;bool report_throw=false;
  explicit Harness(elf_image& i):image(i){
    host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
    host.DefineClass(Player,{{"hideSoftInput","()V"},{"nativeSetInputArea","(IIII)V",false,true},{"nativeSetKeyboardIsVisible","(Z)V",false,true}},"java/lang/Object",true);
    host.DefineClass("com/unity3d/player/l",{},"java/lang/Object",true);
    player=host.NewInstance(Player);global=host.NewGlobalReference(player);weak=Call(226,player);
    hide=Method(Player,"hideSoftInput","()V");
    bunker::jni::NativeMethod n[]={{reinterpret_cast<addr_t>("nativeSetInputArea"),reinterpret_cast<addr_t>("(IIII)V"),Area},{reinterpret_cast<addr_t>("nativeSetKeyboardIsVisible"),reinterpret_cast<addr_t>("(Z)V"),Visible}};
    Check(Call(215,Find(Player),reinterpret_cast<addr_t>(n),2)==0,"real RegisterNatives accepts two TEST native report probes");
    Check(host.NativeCount(Player)==2,"only two null-dialog native reports registered");
  }
  addr_t Call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
  addr_t Find(const char* name){return Call(6,reinterpret_cast<addr_t>(name));}
  addr_t Method(const char* owner,const char* name,const char* sig){return Call(33,Find(owner),reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig));}
  addr_t Run(const char* name,std::initializer_list<addr_t> args){
    alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t n=0;
    for(auto v:args){(s.gpr.*r[n++]).qword=v;}
    s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
    runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));++guest_calls;
    Check(s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.pc.qword==0xfeedffff,"NDK caller restores PC/SP");return s.gpr.x0.qword;
  }
  void Hide(addr_t receiver,addr_t mode){Check(Run("soft_hide",{host.EnvAddress(),receiver,hide,mode})==0x123456789abcdef0ULL,"NDK void direct/V/A returns with sentinel");}
  auto Runner(){return [this](addr_t entry,const std::vector<addr_t>& a)->uint64_t{
    Check(std::this_thread::get_id()==report_owner,"native reports execute on explicit UnityMain owner");
    Check(a.size()==(entry==Area?6:3)&&a[0]==host.EnvAddress()&&a[0]==report_env,"fresh attached-thread Env and exact native arity");
    Check(Call(232,a[1])==1&&Call(24,a[1],weak),"fresh native player local retains original instance");
    for(size_t j=2;j<a.size();++j)Check(a[j]==0,"new Rect area and visibility are exact zero scalars");
    Check(entry==Area||entry==Visible,"no configuration callback on null-dialog path");
    reports.push_back(entry==Area?0:1);report_locals.push_back(a[1]);++native_reports;
    if(report_throw){host.ThrowException("java/lang/IllegalStateException",u"TEST native report exception");}
    return 0;
  };}
  void ExpiredReports(){for(auto p:report_locals)Check(Call(232,p)==0,"native report local expires after Runner");Check(host.PendingException().empty(),"local expiry checks leave no Java exception");}
};
// TEST scheduler only. The actual native thread attaches to the supplied VM;
// production code still owns its queue policy and all report admission gates.
struct Worker {
  Harness& h;std::mutex mutex;std::condition_variable cv;std::queue<std::packaged_task<void()>> jobs;bool stop=false;std::thread thread;
  explicit Worker(Harness& value):h(value),thread([this]{
    addr_t env=0;State s{};s.gpr.x0.qword=h.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,s);
    for(;;){std::packaged_task<void()> job;{std::unique_lock lock(mutex);cv.wait(lock,[&]{return stop||!jobs.empty();});if(stop&&jobs.empty())break;job=std::move(jobs.front());jobs.pop();}job();}
    s={};s.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,s);
  }){}
  ~Worker(){{std::lock_guard lock(mutex);stop=true;}cv.notify_one();thread.join();}
  template<class F>void Do(F f){std::packaged_task<void()> job(std::move(f));auto done=job.get_future();{std::lock_guard lock(mutex);jobs.push(std::move(job));}cv.notify_one();done.get();}
  void Bind(UnitySoftInputSession& session){Do([&]{session.SetUnityMainCurrent();h.report_owner=std::this_thread::get_id();h.report_env=h.host.EnvAddress();});}
};
void Binder(elf_image& image){
  Harness h(image);h.host.DefineClass("VoidProbe",{{"probe","(Ljava/lang/Object;I)V"},{"staticVoid","()V",true,false},{"nativeVoid","()V",false,true},{"notVoid","()I"}},"java/lang/Object",true);
  auto body=[](addr_t,const Host::MethodArguments&){};
  Reject([&]{h.host.BindVoidMethod("Absent","probe","()V",body);},"binder rejects missing owner");
  Reject([&]{h.host.BindVoidMethod("VoidProbe","missing","()V",body);},"binder rejects missing declaration");
  Reject([&]{h.host.BindVoidMethod("VoidProbe","probe","()V",body);},"binder rejects different signature");
  Reject([&]{h.host.BindVoidMethod("VoidProbe","staticVoid","()V",body);},"binder rejects static declaration");
  Reject([&]{h.host.BindVoidMethod("VoidProbe","nativeVoid","()V",body);},"binder rejects native declaration");
  Reject([&]{h.host.BindVoidMethod("VoidProbe","notVoid","()I",body);},"binder rejects nonvoid result");
  Reject([&]{h.host.BindVoidMethod("VoidProbe","probe","(Ljava/lang/Object;I)V",{});},"binder rejects empty implementation");
  auto receiver=h.host.NewInstance("VoidProbe"),argument=h.host.NewString(u"caller");auto receiver_global=h.host.NewGlobalReference(receiver),argument_global=h.host.NewGlobalReference(argument);
  std::vector<addr_t> weak;unsigned called=0;int behavior=0;
  h.host.BindVoidMethod("VoidProbe","probe","(Ljava/lang/Object;I)V",[&](addr_t object,const Host::MethodArguments& a){
    ++called;Check(object!=receiver&&h.Call(232,object)==1&&h.Call(24,object,receiver_global),"void receiver is borrowed callee local");
    Check(a[0]!=argument&&h.Call(232,a[0])==1&&h.Call(24,a[0],argument_global),"void reference argument is borrowed callee local");
    Check(static_cast<uint32_t>(a[1])==0x87654321U,"jint argument preserves low32 bits");
    weak.push_back(h.Call(226,h.host.NewString(u"temporary")));h.Call(19,8);weak.push_back(h.Call(226,h.host.NewString(u"unbalanced user frame")));
    if(behavior==1)h.host.ThrowException("java/lang/IllegalStateException",u"TEST bound void error");
    if(behavior==2)throw std::runtime_error("TEST bound void C++ error");
  });
  Reject([&]{h.host.BindVoidMethod("VoidProbe","probe","(Ljava/lang/Object;I)V",body);},"binder rejects duplicate without overwrite");
  auto method=h.Method("VoidProbe","probe","(Ljava/lang/Object;I)V");
  auto invoke=[&](addr_t mode){return h.Run("soft_probe",{h.host.EnvAddress(),receiver,method,argument,0x87654321U,mode});};
  auto expired=[&]{for(auto w:weak)Check(h.Call(24,w,0),"void callback and user-frame temporary locals expire");Check(h.Call(232,receiver)==1&&h.Call(232,argument)==1,"caller references survive bound void frame");};
  for(addr_t mode=0;mode<3;++mode){Check(invoke(mode)==0xfedcba9876543210ULL,"NDK direct/V/A jvalue array canaries intact");expired();}
  Check(called==3,"all three actual JNI void forms call bound implementation");
  h.host.ThrowException("java/lang/IllegalStateException",u"original pending");auto pending=h.host.CaptureValue(h.Call(15));invoke(0);Check(called==3,"pending exception suppresses bound void body");auto p=h.host.LocalValue(pending);Check(h.Call(24,h.Call(15),p),"original pending exception identity preserved");h.host.ClearException();
  behavior=1;invoke(1);Check(h.host.PendingException().find("TEST bound void error")!=std::string::npos,"bound void Java exception preserved");h.host.ClearException();expired();
  behavior=2;std::array<addr_t,2> native_args={argument,0x87654321U};Reject([&]{h.Call(63,receiver,method,reinterpret_cast<addr_t>(native_args.data()));},"direct Host A boundary propagates bound void C++ exception");expired();
  Check(h.host.PendingException().empty(),"binder tests leave no pending exception");
}
void Queues(elf_image& image){
  {Harness h(image);UnitySoftInputSession session(h.host,h.player,h.Runner());Worker worker(h);worker.Bind(session);session.SetNativeLoaded(true);
    const auto ui_env=h.host.EnvAddress();Check(ui_env!=h.report_env,"UI and attached UnityMain have different real Env tables");
    worker.Do([&]{for(addr_t mode=0;mode<3;++mode)h.Hide(h.global,mode);session.DrainGlThreadJobs();});
    Check(h.reports.empty(),"hide never reports before deferred UI job");Reject([&]{session.CheckIdle();},"queued UI work is observable");
    worker.Do([&]{Reject([&]{session.DrainUiJobs();},"foreign UI pump rejects");});
    Reject([&]{session.DrainGlThreadJobs();},"foreign main pump rejects");Reject([&]{session.SetUnityMainCurrent();},"main owner cannot silently change");
    h.host.DeleteLocalReference(h.player);h.host.DeleteGlobalReference(h.global);session.DrainUiJobs();Check(h.reports.empty(),"UI posts FIFO reports rather than executing on foreign thread");
    Reject([&]{session.CheckIdle();},"queued GL work remains observable");worker.Do([&]{session.DrainGlThreadJobs();});
    Check(h.reports==std::vector<int>({0,1,0,1,0,1}),"all area/visible reports preserve original FIFO order after handle retirement");session.CheckIdle();h.ExpiredReports();
  }
  {Harness h(image);UnitySoftInputSession session(h.host,h.player,h.Runner());Worker worker(h);worker.Bind(session);
    h.Hide(h.player,0);session.DrainUiJobs();worker.Do([&]{session.DrainGlThreadJobs();});Check(h.reports.empty(),"native unloaded admission drops both reports");session.CheckIdle();
    session.SetNativeLoaded(true);h.Hide(h.player,1);session.DrainUiJobs();session.SetNativeLoaded(false);worker.Do([&]{session.DrainGlThreadJobs();});Check(h.reports==std::vector<int>({0,1}),"already queued jobs do not recheck native-loaded gate");session.CheckIdle();h.ExpiredReports();
  }
  {Harness h(image);UnitySoftInputSession session(h.host,h.player,h.Runner());Worker worker(h);worker.Bind(session);session.SetNativeLoaded(true);
    h.Hide(h.player,2);session.DrainUiJobs();session.SetFinishing(true);session.SetFinishing(false);worker.Do([&]{session.DrainGlThreadJobs();});Check(h.reports.empty(),"execution finishing gate drops queued jobs and remains sticky");
    h.Hide(h.player,0);session.DrainUiJobs();worker.Do([&]{session.DrainGlThreadJobs();});Check(h.reports.empty(),"finishing admission drops later reports");session.CheckIdle();
  }
  {Harness h(image);UnitySoftInputSession session(h.host,h.player,h.Runner());session.SetUnityMainCurrent();h.report_owner=std::this_thread::get_id();h.report_env=h.host.EnvAddress();session.SetNativeLoaded(true);
    h.Hide(h.player,0);Check(h.reports.empty(),"same-owner TEST case still defers hide UI closure");session.DrainUiJobs();Check(h.reports==std::vector<int>({0,1}),"report jobs inline only after UI closure reaches same main owner");session.CheckIdle();h.ExpiredReports();
  }
  {Harness h(image);UnitySoftInputSession session(h.host,h.player,h.Runner());Worker worker(h);worker.Bind(session);session.SetNativeLoaded(true);auto dialog=h.host.NewInstance("com/unity3d/player/l");h.host.SetObjectFieldValue(h.player,"mSoftInputDialog",Dialog,dialog);
    h.Hide(h.player,1);Reject([&]{session.DrainUiJobs();},"nonnull dialog explicitly rejects unsupported dismissal after report scheduling");
    Check(h.Call(24,h.host.GetObjectFieldValue(h.player,"mSoftInputDialog",Dialog),dialog),"unsupported dialog remains intact");worker.Do([&]{session.DrainGlThreadJobs();});Check(h.reports==std::vector<int>({0,1}),"nonnull branch schedules both reports before unsupported dismissal");session.CheckIdle();
  }
  {Harness h(image);UnitySoftInputSession session(h.host,h.player,h.Runner());Worker worker(h);worker.Bind(session);session.SetNativeLoaded(true);h.report_throw=true;h.Hide(h.player,2);session.DrainUiJobs();
    worker.Do([&]{Reject([&]{session.DrainGlThreadJobs();},"native pending exception rejects report continuation");Check(h.host.PendingException().find("TEST native report exception")!=std::string::npos,"native report pending exception preserved");h.host.ClearException();session.SetFinishing(true);session.DrainGlThreadJobs();});Check(h.reports==std::vector<int>({0}),"failed area does not silently execute visible report");session.CheckIdle();h.ExpiredReports();
  }
}
void InvalidSessions(elf_image& image){
  Harness h(image);auto runner=h.Runner();
  Reject([&]{UnitySoftInputSession s(h.host,0,runner);},"session rejects null player");
  Reject([&]{UnitySoftInputSession s(h.host,h.player,{});},"session rejects missing native runner");
  auto stale=h.host.NewInstance(Player);h.host.DeleteLocalReference(stale);Reject([&]{UnitySoftInputSession s(h.host,stale,runner);},"session rejects stale player");h.host.ClearException();
  auto wrong=h.host.NewString(u"wrong");Reject([&]{UnitySoftInputSession s(h.host,wrong,runner);},"session rejects wrong instance class");h.host.ClearException();
  auto klass=h.Find(Player);Reject([&]{UnitySoftInputSession s(h.host,klass,runner);},"session rejects class metadata as player");h.host.ClearException();
  h.host.ThrowException("java/lang/IllegalStateException",u"construct pending");Reject([&]{UnitySoftInputSession s(h.host,h.player,runner);},"session rejects pending Java exception");Check(h.host.PendingException().find("construct pending")!=std::string::npos,"construction does not clear pending Java exception");h.host.ClearException();
  UnitySoftInputSession session(h.host,h.player,runner);session.SetUnityMainCurrent();h.report_owner=std::this_thread::get_id();h.report_env=h.host.EnvAddress();session.SetNativeLoaded(true);
  Reject([&]{UnitySoftInputSession duplicate(h.host,h.player,runner);},"duplicate session does not overwrite existing field or binding");
  auto other=h.host.NewInstance(Player);Reject([&]{h.Call(63,other,h.hide,0);},"direct Host A boundary rejects same-class unrelated receiver");Check(h.host.PendingException().empty(),"receiver identity rejection does not invent Java exception");session.CheckIdle();
  h.Hide(0,2);Check(!h.host.PendingException().empty(),"null receiver rejects through JNI");h.host.ClearException();session.CheckIdle();
  h.Hide(h.player,1);session.DrainUiJobs();Check(h.reports==std::vector<int>({0,1}),"strict negatives preserve valid session implementation");session.CheckIdle();
}
}
int main(){try{elf_image image{};Check(!elf_load(SOFT_IMAGE,0x73000000,nullptr,&image),"load genuine NDK JNI callers");Binder(image);Queues(image);InvalidSessions(image);std::printf("UNITY-SOFT-INPUT-PASS checks=%u guest_calls=%u native_reports=%u",checks.load(),guest_calls.load(),native_reports.load());std::putchar(10);return 0;}catch(const std::exception& e){std::fprintf(stderr,"UNITY-SOFT-INPUT-FAILURE %s",e.what());std::fputc(10,stderr);return 1;}}

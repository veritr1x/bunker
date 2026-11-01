#include "package_test_session.h"
#include <atomic>
#include <chrono>
#include <functional>
#include <future>
#include <mutex>

namespace {
struct Payload {
  std::function<void()> retire;
  explicit Payload(std::function<void()> action):retire(std::move(action)){}
  ~Payload(){retire();}
};
}
int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(30));std::fputs("constructor frame watchdog\n",stderr);std::_Exit(95);}).detach();
  std::atomic<unsigned> checks{0};
  auto check=[&](bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;};
  elf_image image{};check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual NDK constructor callers");Session h(image);
  h.host.DefineClass("Factory");h.host.DefineClass("FactoryChild",{},"Factory");h.host.DefineClass("Other");h.host.DefineClass("Payload");
  const auto owner=h.find("Factory"),caller=h.host.NewInstance("Factory"),global=h.host.NewGlobalReference(caller);
  const auto argument=h.host.NewString(u"caller argument"),global_argument=h.host.NewGlobalReference(argument);
  std::vector<addr_t> weak;std::mutex weak_mutex;
  auto track=[&](addr_t object){auto ref=h.call(226,object);std::lock_guard lock(weak_mutex);weak.push_back(ref);return ref;};
  auto temporary=[&]{track(h.host.NewString(u"factory temporary"));};
  auto dead_since=[&](size_t at){for(size_t i=at;i<weak.size();++i)check(h.call(24,weak[i],0),"factory temporary expires before caller frame pop");};
  int behavior=0;addr_t raw_result=0,result_weak=0;const int32_t integer=static_cast<int32_t>(0x87654321u);
  h.host.DefineConstructor("Factory","(Ljava/lang/Object;ILjava/lang/Object;)V",[&](const bunker::jni::Host::MethodArguments &args){
    check(args[0]!=argument&&args[0]!=global_argument&&h.call(232,args[0])==1&&h.call(24,args[0],global_argument),"factory reference argument is a borrowed callee local");
    check(static_cast<int32_t>(args[1])==integer&&args[2]!=global&&h.call(232,args[2])==1&&h.call(24,args[2],global),"mixed jint slot and second reference preserved");
    temporary();temporary();
    if(behavior==1)return caller;
    if(behavior==2)return global;
    if(behavior==3){h.host.DeleteLocalReference(args[0]);h.host.DeleteLocalReference(args[2]);}
    h.call(19,8);temporary();raw_result=h.host.NewInstance("Factory");result_weak=h.call(226,raw_result);return raw_result;
  });
  const auto mixed=h.method("Factory","<init>","(Ljava/lang/Object;ILjava/lang/Object;)V");
  auto construct_three=[&](addr_t mode){return h.run("package_construct_three",{h.host.EnvAddress(),owner,mixed,argument,static_cast<uint32_t>(integer),global,mode});};
  for(addr_t mode=0;mode<4;++mode)for(behavior=0;behavior<4;++behavior){
    const auto at=weak.size();const auto result=construct_three(mode);dead_since(at);
    check(result&&result!=caller&&result!=global&&h.call(232,result)==1,"factory produces one independent caller-local result");
    if(behavior==1||behavior==2)check(h.call(24,result,global),"existing factory result retains object identity");
    else check(!h.call(232,raw_result)&&h.call(24,result,result_weak),"raw factory local retired after result promotion");
    h.host.DeleteLocalReference(result);
    if(behavior==0||behavior==3)check(h.call(24,result_weak,0),"factory result has no hidden local root after caller deletion");
    check(h.call(232,caller)==1&&h.call(232,global)==2&&h.call(232,argument)==1&&h.call(232,global_argument)==2,"callee cleanup preserves caller and global inputs");
  }
  h.host.DefineConstructor("Factory","(Ljava/lang/String;)V",[&](const bunker::jni::Host::MethodArguments &args){check(!args[0],"null reference argument remains null");temporary();return h.host.NewInstance("Factory");});
  auto nullable=h.method("Factory","<init>","(Ljava/lang/String;)V");
  for(addr_t mode=0;mode<3;++mode){auto at=weak.size();auto result=h.construct(owner,nullable,0,mode);dead_since(at);check(result&&h.host.PendingException().empty(),"null argument accepted on each NDK constructor variant");h.host.DeleteLocalReference(result);}

  // Invalid results must never be promoted, and all temporary roots still retire.
  h.host.DefineConstructor("Factory","()V",[&](const bunker::jni::Host::MethodArguments&){
    temporary();
    if(behavior==0)return addr_t(0);
    if(behavior==1)return h.host.NewInstance("Other");
    if(behavior==2)return h.host.NewInstance("FactoryChild");
    auto result=h.host.NewInstance("Factory");track(result);h.host.DeleteLocalReference(result);return result;
  });
  const auto zero=h.method("Factory","<init>","()V");
  for(addr_t mode=0;mode<3;++mode)for(behavior=0;behavior<4;++behavior){auto at=weak.size();check(!h.construct(owner,zero,0,mode),"invalid constructor result rejected");check(h.host.PendingException().find(behavior?"IllegalArgumentException":"IllegalStateException")!=std::string::npos,"invalid constructor result reports exact failure category");h.host.ClearException();dead_since(at);}
  h.host.DefineConstructor("java/lang/String","()V",[&](const bunker::jni::Host::MethodArguments&){temporary();auto result=h.host.NewString(u"wrong kind");track(result);return result;});
  auto string_owner=h.find("java/lang/String"),string_constructor=h.method("java/lang/String","<init>","()V");
  auto at=weak.size();check(!h.construct(string_owner,string_constructor,0,1)&&h.host.PendingException().find("wrong class")!=std::string::npos,"exact class name is insufficient without kInstance state");h.host.ClearException();dead_since(at);

  std::promise<addr_t> foreign_ready;std::promise<void> foreign_release;auto release=foreign_release.get_future();
  std::thread foreign_thread([&]{addr_t env=0;State s{};s.gpr.x0.qword=h.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,s);foreign_ready.set_value(h.host.NewInstance("Factory"));release.wait();s={};s.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,s);});
  auto foreign=foreign_ready.get_future().get();h.host.DefineConstructor("Factory","(Ljava/lang/Object;)V",[&](const bunker::jni::Host::MethodArguments&){temporary();return foreign;});
  auto foreign_constructor=h.method("Factory","<init>","(Ljava/lang/Object;)V");
  for(addr_t mode=0;mode<3;++mode){at=weak.size();check(!h.construct(owner,foreign_constructor,0,mode)&&h.host.PendingException().find("IllegalArgumentException")!=std::string::npos,"foreign-thread constructor result rejected");h.host.ClearException();dead_since(at);}
  foreign_release.set_value();foreign_thread.join();

  // Nested construction and destruction keep the boundary active to quiescence.
  h.host.DefineClass("NestedFactory");const auto nested_owner=h.host.NewGlobalReference(h.find("NestedFactory"));
  h.host.DefineConstructor("NestedFactory","()V",[&](const bunker::jni::Host::MethodArguments&){temporary();h.call(19,8);auto result=h.host.NewInstance("NestedFactory");return result;});
  const auto nested_constructor=h.method("NestedFactory","<init>","()V");
  int retirements=0,error_mode=0;bool retirement_failed=false;bunker::jni::Host::ObjectValue original_exception;
  auto make_payload=[&]{auto payload=std::make_shared<Payload>([&]{try{
    ++retirements;if(error_mode)h.host.ClearException();h.call(19,8);temporary();
    auto nested=h.construct(nested_owner,nested_constructor,0,2);check(nested&&h.call(232,nested)==1,"destructor can execute nested NDK NewObject");h.host.DeleteLocalReference(nested);h.call(19,8);temporary();
    check(!h.call(20,0)&&h.host.PendingException().empty(),"destructor may pop its own user frame");
    State vm{};vm.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,vm);check(static_cast<int32_t>(vm.gpr.x0.qword)==bunker::jni::kError,"factory detach prohibited during payload retirement");
    std::exception_ptr failure;std::thread worker([&]{try{addr_t env=0;State s{};s.gpr.x0.qword=h.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,s);if(!env)throw std::runtime_error("factory destructor worker attach");s={};s.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,s);}catch(...){failure=std::current_exception();}});worker.join();if(failure)std::rethrow_exception(failure);
    if(error_mode){h.host.ClearException();h.host.ThrowException("java/lang/IllegalArgumentException",u"factory cleanup error");}
  }catch(...){retirement_failed=true;}});track(h.host.NewHostInstance("Payload",std::move(payload)));};
  h.host.DefineClass("RetireFactory");auto retire_owner=h.find("RetireFactory");
  h.host.DefineConstructor("RetireFactory","()V",[&](const bunker::jni::Host::MethodArguments&){
    check(!h.call(20)&&h.host.PendingException().find("IllegalStateException")!=std::string::npos,"constructor owned boundary cannot be popped");h.host.ClearException();
    State vm{};vm.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,vm);check(static_cast<int32_t>(vm.gpr.x0.qword)==bunker::jni::kError,"active factory detach rejected");make_payload();temporary();
    if(error_mode==1){h.host.ThrowException("java/lang/IllegalStateException",u"original factory error");original_exception=h.host.CaptureValue(h.call(15));return addr_t(0);}
    return h.host.NewInstance("RetireFactory");
  });
  auto retire_constructor=h.method("RetireFactory","<init>","()V");
  for(error_mode=0;error_mode<3;++error_mode){at=weak.size();auto result=h.construct(retire_owner,retire_constructor,0,error_mode);dead_since(at);check(!retirement_failed&&retirements==error_mode+1,"factory payload cleanup completes outside provider lock");if(!error_mode){check(result&&h.host.PendingException().empty(),"successful factory survives destructor reentry");h.host.DeleteLocalReference(result);}else if(error_mode==1){auto exception=h.call(15),original=h.host.LocalValue(original_exception);check(!result&&h.call(24,exception,original)&&h.host.PendingException().find("original factory error")!=std::string::npos,"factory Java exception identity survives destructor clearing");h.host.ClearException();}else{check(!result&&h.host.PendingException().find("factory cleanup error")!=std::string::npos,"cleanup exception prevents constructor result promotion");h.host.ClearException();}}
  h.host.DefineConstructor("RetireFactory","(Ljava/lang/Object;)V",[&](const bunker::jni::Host::MethodArguments&)->addr_t{temporary();h.call(19,8);make_payload();throw std::runtime_error("original C++ factory error");});
  // Runtime import exceptions are intentionally fatal; inspect C++ propagation
  // at the provider boundary rather than through a translated caller.
  error_mode=0;at=weak.size();bool caught=false;try{h.call(28,retire_owner,h.method("RetireFactory","<init>","(Ljava/lang/Object;)V"),0);}catch(const std::runtime_error &error){caught=std::string(error.what())=="original C++ factory error";}dead_since(at);check(caught&&!retirement_failed&&h.host.PendingException().empty(),"C++ factory throw cleans owned scope before propagation");

  h.host.DefineClass("ArgumentFactory");auto argument_owner=h.find("ArgumentFactory");auto ephemeral_global=h.host.NewGlobalReference(h.host.NewString(u"retained argument"));
  h.host.DefineConstructor("ArgumentFactory","(Ljava/lang/Object;)V",[&](const bunker::jni::Host::MethodArguments &args){std::thread worker([&]{h.host.DeleteGlobalReference(ephemeral_global);});worker.join();check(h.text(args[0])==u"retained argument","callee clone survives original global deletion");h.host.DeleteLocalReference(args[0]);return h.host.NewInstance("ArgumentFactory");});
  auto argument_result=h.construct(argument_owner,h.method("ArgumentFactory","<init>","(Ljava/lang/Object;)V"),ephemeral_global,2);check(argument_result&&!h.call(232,ephemeral_global),"argument factory succeeds after caller global retired");h.host.DeleteLocalReference(argument_result);

  // Simultaneous factories get independent local-frame ownership on each thread.
  h.host.DefineClass("ParallelFactory");auto parallel_owner=h.host.NewGlobalReference(h.find("ParallelFactory"));
  h.host.DefineConstructor("ParallelFactory","(Ljava/lang/Object;)V",[&](const bunker::jni::Host::MethodArguments &args){check(h.call(232,args[0])==1&&h.call(24,args[0],global_argument),"parallel factory owns argument local on invoking thread");temporary();return h.host.NewInstance("ParallelFactory");});
  auto parallel_constructor=h.method("ParallelFactory","<init>","(Ljava/lang/Object;)V");
  std::exception_ptr parallel_error;std::mutex error_mutex;std::vector<std::thread> workers;at=weak.size();
  for(int n=0;n<8;++n)workers.emplace_back([&]{try{addr_t env=0;State s{};s.gpr.x0.qword=h.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,s);for(int repeat=0;repeat<4;++repeat){auto result=h.construct(parallel_owner,parallel_constructor,global_argument,repeat%3);auto ref=h.call(226,result);check(result&&h.call(232,result)==1,"parallel factory result belongs to caller thread");h.host.DeleteLocalReference(result);check(h.call(24,ref,0),"parallel factory result expires without hidden roots");}s={};s.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,s);}catch(...){std::lock_guard lock(error_mutex);if(!parallel_error)parallel_error=std::current_exception();}});
  for(auto &worker:workers)worker.join();
  if(parallel_error)std::rethrow_exception(parallel_error);
  dead_since(at);
  check(h.call(232,caller)==1&&h.call(232,global)==2&&h.call(232,argument)==1&&h.host.PendingException().empty(),"constructor tests preserve caller frame and original references");
  std::printf("JNI constructor frames: %u checks; actual NDK NewObject direct,V,A,stackV; exact-owner promotion, weak liveness and reentrant retirement\n",checks.load());
}

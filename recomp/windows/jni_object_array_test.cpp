#include "jni_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <atomic>
#include <array>
#include <cstdio>
#include <functional>
#include <stdexcept>
#include <thread>
namespace {
struct Payload {std::function<void()> retire;~Payload(){retire();}};
}
int main(){try{
  std::atomic<unsigned> checks{0};auto check=[&](bool v,const char *why){if(!v)throw std::runtime_error(why);++checks;};
  elf_image image{};check(!elf_load(ARRAY_IMAGE,0x74000000,nullptr,&image),"NDK object-array fixture mapping");
  recomp::Runtime runtime;bunker::jni::Host host([](addr_t){return false;});host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
  auto env=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;};
  auto run=[&](const char *name,std::initializer_list<addr_t> args){alignas(16)std::array<uint8_t,65536> stack{};State s{};
    Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4};size_t i=0;for(auto a:args)(s.gpr.*regs[i++]).qword=a;
    s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
    auto target=reinterpret_cast<addr_t>(elf_symbol(&image,name));check(target!=0,"original fixture export");runtime.Run(s,target);
    check(s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.pc.qword==0xfeedffff,"NDK caller stack/return");return s.gpr.x0.qword;};
  auto find=[&](const char *name){return run("array_find",{host.EnvAddress(),reinterpret_cast<addr_t>(name)});};
  auto make=[&](int32_t n,addr_t component,addr_t initial=0){return run("array_new",{host.EnvAddress(),static_cast<uint32_t>(n),component,initial});};
  auto get=[&](addr_t a,int32_t i){return run("array_get",{host.EnvAddress(),a,static_cast<uint32_t>(i)});};
  auto set=[&](addr_t a,int32_t i,addr_t v){run("array_set",{host.EnvAddress(),a,static_cast<uint32_t>(i),v});};
  auto error=[&](const char *type){check(host.PendingException().find(type)!=std::string::npos,"exact Java exception category");host.ClearException();};
  auto same=[&](addr_t a,addr_t b){return env(24,a,b)!=0;};
  auto object=find("java/lang/Object"),string=find("java/lang/String"),classes=find("java/lang/Class");
  const auto excessive=std::string(256,'[')+"Ljava/lang/String;";check(!find(excessive.c_str()),"invalid 256-dimension descriptor rejected before recursion");error("NoClassDefFoundError");
  auto text=host.NewString(u"array element"),weak=env(226,text);
  auto array=make(257,string,text);check(array&&host.PendingException().empty(),"real String array allocated");
  check(run("array_length",{host.EnvAddress(),array})==257,"jsize length");
  for(int i=0;i<257;++i){auto value=get(array,i);check(value&&value!=text&&same(value,text)&&env(232,value)==1,"each element returns fresh caller-local identity");host.DeleteLocalReference(value);}
  host.DeleteLocalReference(text);check(!same(weak,0),"array strongly owns every initialized element");
  auto array_class=find("[Ljava/lang/String;"),object_array_class=find("[Ljava/lang/Object;");
  auto serializable=find("java/io/Serializable"),serializable_array_class=find("[Ljava/io/Serializable;");
  check(env(11,array_class,serializable_array_class),"String[] covariance follows actual Serializable implementation");
  check(run("array_shape",{host.EnvAddress(),array,reinterpret_cast<addr_t>("[Ljava/lang/String;")})==15,"actual array class/superclass/marker interfaces");
  check(env(11,array_class,object_array_class)&&!env(11,object_array_class,array_class),"reference array covariance");
  auto wrong=host.NewInstance("java/lang/Object");set(array,0,wrong);error("ArrayStoreException");auto previous=get(array,0);check(same(previous,weak),"failed store preserves old element");host.DeleteLocalReference(previous);
  auto serializable_array=make(4,serializable);auto throwable=host.NewInstance("java/lang/IllegalArgumentException"),builder=host.NewInstance("java/lang/StringBuilder");
  auto serializable_text=get(array,0);for(auto value:{serializable_text,string,throwable,builder}){set(serializable_array,0,value);check(host.PendingException().empty(),"builtin Serializable values accepted");}host.DeleteLocalReference(serializable_text);
  set(serializable_array,0,wrong);error("ArrayStoreException");host.DeleteLocalReference(serializable_array);
  host.DefineClass("java/io/File");host.DefineClass("android/content/Intent");host.DefineClass("android/content/ComponentName");host.DefineClass("android/os/Bundle");
  auto file_value=host.NewInstance("java/io/File"),file_array=make(1,serializable,file_value);check(file_array&&host.PendingException().empty(),"known File Serializable metadata");host.DeleteLocalReference(file_array);host.DeleteLocalReference(file_value);
  auto cloneable=find("java/lang/Cloneable");for(auto name:{"android/content/Intent","android/content/ComponentName","android/os/Bundle"}){auto value=host.NewInstance(name),values=make(1,cloneable,value);check(values&&host.PendingException().empty(),"known Android framework Cloneable metadata");host.DeleteLocalReference(values);host.DeleteLocalReference(value);}
  for(int32_t i:{-1,257,INT32_MAX,INT32_MIN}){check(!get(array,i),"out-of-range get returns null");error("ArrayIndexOutOfBoundsException");set(array,i,0);error("ArrayIndexOutOfBoundsException");}
  for(int i=0;i<257;++i)set(array,i,0);check(same(weak,0),"last array edge retires element");
  auto weak_initial=make(1,string,weak);check(weak_initial&&!get(weak_initial,0)&&host.PendingException().empty(),"cleared weak initializer is a null value");set(array,0,weak);check(!get(array,0)&&host.PendingException().empty(),"cleared weak store is null");host.DeleteLocalReference(weak_initial);
  check(!make(-1,string),"negative allocation rejected");error("NegativeArraySizeException");
  check(!make(1,string,wrong),"incompatible initializer rejected");error("ArrayStoreException");
  auto empty=make(0,object);check(run("array_length",{host.EnvAddress(),empty})==0,"zero-length array");
  auto class_array=make(1,classes,string);auto element=get(class_array,0);check(same(element,string),"jclass values have java.lang.Class runtime type");host.DeleteLocalReference(element);
  auto nested=make(2,array_class,array);check(run("array_shape",{host.EnvAddress(),nested,reinterpret_cast<addr_t>("[[Ljava/lang/String;")})==15,"nested reference-array class");
  auto nested_class=find("[[Ljava/lang/String;"),object_nested_class=find("[[Ljava/lang/Object;");check(env(11,nested_class,object_nested_class)&&env(11,nested_class,object_array_class),"nested covariance to Object[][] and Object[]");
  auto objects=make(1,object,nested);element=get(objects,0);check(same(element,nested),"array object stored as Object");host.DeleteLocalReference(element);
  check(!env(27,array_class),"array cannot be AllocObject-created");error("InstantiationException");
  auto seed=host.NewString(u"frame-owned"),seed_weak=env(226,seed);auto framed=run("array_frame",{host.EnvAddress(),string,seed});host.DeleteLocalReference(seed);check(framed&&!same(seed_weak,0)&&env(232,framed)==1,"PopLocalFrame promotes array with retained edges");host.DeleteLocalReference(framed);check(same(seed_weak,0),"frame array does not leak hidden element roots");
  auto global=host.NewGlobalReference(array);std::exception_ptr failure;
  std::thread worker([&]{try{addr_t current_env=0;State vm{};vm.gpr.x0.qword=host.VmAddress();vm.gpr.x1.qword=reinterpret_cast<addr_t>(&current_env);host.InvokeVm(4,vm);check(current_env!=0,"worker JNI attach");auto local=get(global,0);check(!local&&host.PendingException().empty(),"attached worker shares array identity");vm={};vm.gpr.x0.qword=host.VmAddress();host.InvokeVm(5,vm);check(vm.gpr.x0.dword==0,"worker JNI detach");}catch(...){failure=std::current_exception();}});worker.join();if(failure)std::rethrow_exception(failure);host.DeleteGlobalReference(global);
  host.DefineClass("Payload");auto payload_class=find("Payload");int retirements=0;bool reentrant=false;
  auto payload=std::make_shared<Payload>();payload->retire=[&]{++retirements;std::thread other([&]{auto temporary=host.NewString(u"unlocked payload retirement");host.DeleteLocalReference(temporary);reentrant=true;});other.join();};
  auto payload_ref=host.NewHostInstance("Payload",std::move(payload)),payload_array=make(1,payload_class,payload_ref);host.DeleteLocalReference(payload_ref);set(payload_array,0,0);check(retirements==1&&reentrant,"element retirement runs outside provider mutex");
  auto class_type=find("java/lang/Class"),loader_method=env(33,class_type,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
  auto payload_array_class=env(31,payload_array),component_loader=env(34,payload_class,loader_method),array_loader=env(34,payload_array_class,loader_method);check(same(component_loader,array_loader),"reference array inherits its component class loader");
  auto array_weak=env(226,array);for(auto local:{objects,nested,class_array,empty,array,wrong})host.DeleteLocalReference(local);check(same(array_weak,0),"array retires after last nested/native edge");
  check(host.PendingException().empty(),"no hidden Java exceptions");
  std::printf("JNI object arrays: %u checks; actual NDK creation/length/get/store, covariance, references, bounds, threads and unlocked retirement\n",checks.load());return 0;
}catch(const std::exception &e){std::fprintf(stderr,"object arrays: %s\n",e.what());return 1;}}

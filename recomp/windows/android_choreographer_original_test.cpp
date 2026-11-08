// Separate original-638 integration TU. Generic fixture helpers are retained
// unchanged; its main is not executed by this component.
#include "libc.h"
static std::function<uint64_t(addr_t,const std::vector<addr_t>&)> original_runner;
namespace bunker::windows {
class ComponentLibC:public LibC {
 public:ComponentLibC():LibC([](addr_t pc,const std::vector<addr_t>&args){return original_runner(pc,args);}){}
};
}
#define LibC ComponentLibC
#define main unused_generic_choreographer_main
#include "android_choreographer_test.cpp"
#undef main
#undef LibC
#include "android_process.h"
#include "thread_priority.h"
#include "filesystem.h"
#include "logging.h"
#include "original_profile.h"

namespace {
Session* original_session=nullptr;
FileSystem* original_files=nullptr;
Logging* original_logging=nullptr;
ThreadPriorities* original_priorities=nullptr;
std::map<std::string,addr_t> original_imports;
template<class P> addr_t Try(P& p,const char* name){try{return p.Marker(name);}catch(const std::invalid_argument&){return 0;}}
void* OriginalResolve(const char* name){
  auto& s=*original_session;auto found=original_imports.find(name);if(found!=original_imports.end())return reinterpret_cast<void*>(found->second);
  addr_t address=0;
  for(auto candidate:{Try(s.libc,name),Try(s.threads,name),Try(*original_files,name),Try(*original_logging,name),Try(*original_priorities,name)})
    if(candidate){Check(!address||address==candidate,"one actual import provider owns original symbol");address=candidate;}
  if(!address){
    Check(strcmp(name,"__sF"),"strong original stdio data uses genuine FileSystem storage");
    address=0x7ffcf0000000ULL+original_imports.size()*8;
    s.runtime.AddImport(address,[symbol=std::string(name)](State& state){fprintf(stderr,"ORIGINAL638 unsupported import=%s LR=%#llx\n",symbol.c_str(),(unsigned long long)state.gpr.x30.qword);fflush(stderr);std::abort();});
  }
  original_imports.emplace(name,address);return reinterpret_cast<void*>(address);
}
template<class T>T ReadOriginal(addr_t address){T value{};recomp::ReadGuestMemory(&value,address,sizeof(value));return value;}
struct NativeStorage{alignas(16)std::array<uint8_t,16>before;std::array<uint8_t,0xc8>object{};std::array<uint8_t,24>after;};
}
int main(){try{
  setvbuf(stderr,nullptr,_IONBF,0);Session s;active=&s;original_session=&s;
  original_runner=[&](addr_t pc,const std::vector<addr_t>&args){return s.threads.Run(pc,args);};
  FileSystem files;original_files=&files;files.Install(s.runtime);
  Logging logging;original_logging=&logging;logging.SetStream([&](addr_t stream,std::string_view text){return files.FWrite(text.data(),1,text.size(),stream);});logging.Install(s.runtime);
  ThreadPriorities priorities(s.threads,ThreadPriorities::Profile::UnityNormalClass);original_priorities=&priorities;priorities.Install(s.runtime);
  AndroidProcess process(s.host,priorities);
  Check(!elf_load(CHOREOGRAPHER_LIBRARY,0x7e000000,Resolve,&s.image),"real NDK control callers mapped");
  elf_image unity{};Check(!elf_load(ORIGINAL_UNITY_LIBRARY,0x70000000,OriginalResolve,&unity),"actual original Unity ELF mapped/relocated");
  Check(unity.span==20316160,"original Unity data span");
  AndroidContext context(s.host,Context());WindowsDisplayService displays(s.host);auto inventory=displays.Displays();auto display=std::find_if(inventory.begin(),inventory.end(),[](const auto& value){return value.id==0;});
  Check(display!=inventory.end()&&display->refresh_numerator&&display->refresh_denominator,"actual observed Windows refresh");
  auto config=s.Config(*display);
  config.prepare_worker=[&](const std::u16string&)->std::shared_ptr<void>{auto lease=std::make_shared<Lease>();lease->parent=s.threads.Self();Check(!s.signals.Mask(lease->parent,0,nullptr,&lease->mask),"capture actual original creator mask");return lease;};
  AndroidChoreographer service(s.host,std::move(config));std::atomic<unsigned>native_invocations{0};
  JniInterfaceProxy proxy(s.host,{[&](addr_t entry,const std::vector<addr_t>&args){Check(entry==0x70ab6e48&&entry==s.host.NativeEntry("bitter/jnibridge/JNIBridge","invoke","(JLjava/lang/Class;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;"),"genuine original registered native invocation");++native_invocations;return s.threads.Run(entry,args);}});
  const auto vm=s.host.VmAddress();recomp::WriteGuestMemory(0x7130da50,&vm,sizeof(vm));
  for(auto pc:kOriginalInitializers){fprintf(stderr,"ORIGINAL638 initializer=%#llx\n",(unsigned long long)pc);s.threads.Run(pc,{});}
  Check(s.threads.Run(0x70ab6eb4,{})==1,"actual original native registration returns success");
  Check(s.host.NativeEntry("bitter/jnibridge/JNIBridge","invoke","(JLjava/lang/Class;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;")==0x70ab6e48&&s.host.NativeEntry("bitter/jnibridge/JNIBridge","delete","(J)V")==0x70ab6e9c,"actual two original registered bodies");
  NativeStorage storage;storage.before.fill(0x5a);storage.after.fill(0xc3);const auto object=reinterpret_cast<addr_t>(storage.object.data());
  std::mutex task_mutex;std::condition_variable task_done;unsigned completed=0;std::exception_ptr task_failure;
  s.host.DefineClass("TEST/OriginalCtorDriver",{},"java/lang/Object",true,{"android/os/Handler$Callback"});
  s.host.DefineBooleanMethod("TEST/OriginalCtorDriver","handleMessage","(Landroid/os/Message;)Z",[&](addr_t,const auto&args){
    try{const auto what=static_cast<int32_t>(s.Guest("choreo_get_what",{args[0]}));fprintf(stderr,"ORIGINAL638 driver what=%d native_tid=%lu\n",what,GetCurrentThreadId());
      if(what==100)s.threads.Run(0x70437158,{object});
      else if(what==101)s.threads.Run(0x704373c0,{object});
      else if(what==102){auto cls=s.Find("android/os/Looper"),current=s.Object(cls,s.Method(cls,"myLooper","()Landroid/os/Looper;",true),0,0,0,true);s.Void(current,s.Method(cls,"quit","()V"));}
      else throw std::runtime_error("unknown TEST driver task");
      {std::lock_guard lock(task_mutex);++completed;}task_done.notify_all();return true;
    }catch(...){std::lock_guard lock(task_mutex);task_failure=std::current_exception();task_done.notify_all();throw;}
  });
  auto ht=s.Find("android/os/HandlerThread"),thread=s.Find("java/lang/Thread"),handler_class=s.Find("android/os/Handler"),message_class=s.Find("android/os/Message");
  auto worker=s.New(ht,s.Method(ht,"<init>","(Ljava/lang/String;)V"),0,s.host.NewString(u"TEST-OriginalCtorOwner"),0,1);s.Void(worker,s.Method(thread,"start","()V"));
  auto looper=s.Object(worker,s.Method(ht,"getLooper","()Landroid/os/Looper;"),0),driver=s.host.NewInstance("TEST/OriginalCtorDriver");
  auto driver_handler=s.New(handler_class,s.Method(handler_class,"<init>","(Landroid/os/Looper;Landroid/os/Handler$Callback;)V"),0,looper,driver,2);
  const auto obtain=s.Method(handler_class,"obtainMessage","(I)Landroid/os/Message;"),send=s.Method(message_class,"sendToTarget","()V");
  auto queue=[&](addr_t handler,int what){auto message=s.Object(handler,obtain,0,static_cast<uint32_t>(what),2);s.Void(message,send);s.host.DeleteLocalReference(message);};
  auto await=[&](unsigned n){std::unique_lock lock(task_mutex);Check(task_done.wait_for(lock,std::chrono::seconds(15),[&]{return completed>=n||task_failure;}),"bounded original task completion");if(task_failure)std::rethrow_exception(task_failure);};
  queue(driver_handler,100);await(1);service.CheckHealthy();s.Healthy();
  const auto record=ReadOriginal<addr_t>(object+0x58),predicate=ReadOriginal<addr_t>(record);
  Check(record&&predicate,"real original message0 published nonnull payload before constructor returned");
  const auto handler_record=ReadOriginal<addr_t>(object+0xb8),native_handler=ReadOriginal<addr_t>(handler_record);
  Check(native_handler!=0,"real original child Handler retained");
  const auto before=ReadOriginal<uint32_t>(0x712c30c4);queue(native_handler,1);
  const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(10);
  while(ReadOriginal<uint32_t>(0x712c30c4)-before<2&&std::chrono::steady_clock::now()<deadline){service.CheckHealthy();std::this_thread::sleep_for(std::chrono::milliseconds(5));}
  const auto frames=ReadOriginal<uint32_t>(0x712c30c4)-before;
  const auto stamp=ReadOriginal<uint64_t>(0x712c30c8);
  Check(frames>=2&&stamp!=0,"actual original frame body increments counter and records genuine clock timestamp");
  queue(native_handler,2);queue(driver_handler,101);await(2);service.CheckHealthy();s.Healthy();
  Check(std::all_of(storage.before.begin(),storage.before.end(),[](auto x){return x==0x5a;})&&std::all_of(storage.after.begin(),storage.after.end(),[](auto x){return x==0xc3;}),"original nondeleting constructor/destructor preserve owned c8 extent canaries");
  proxy.CheckNoEnabledProxies();queue(driver_handler,102);await(3);s.Void(worker,s.Method(thread,"join","()V"));service.Stop();
  Check(s.entered==2&&s.exited==2,"original child and TEST prepared driver both genuinely quiesce");
  Check(!s.threads.Shutdown()&&!s.signals.DropThread(s.parent)&&!s.threads.ReleaseCurrent(),"actual component parent cleanup");
  FILE* result=fopen(ORIGINAL_RESULT_FILE,"wb");Check(result!=nullptr,"dedicated original component result file");
  fprintf(result,"ORIGINAL638-PASS checks=%u initializers=24 original_native_calls=%u frames=%u frame_stamp=%llu ctor=70437158 dtor=704373c0 workers=%u/%u VM_seed_only=1 first_frame_claim=0\n",checks.load(),native_invocations.load(),frames,(unsigned long long)stamp,s.entered.load(),s.exited.load());fclose(result);return 0;
}catch(const std::exception&error){fprintf(stderr,"Original638 fixture failed:%s\n",error.what());return 1;}}

#include "pthread_host.h"
#include "tracked_memory_test.h"
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <set>
#include <stdexcept>
#include <thread>
#include <vector>
#include <windows.h>
#include "../fastaes/elfload.h"
#include "pthread_traces.h"

static bunker::windows::Pthreads *guest_host;
static constexpr addr_t kMemset=0x7ffb00000000;
static void *Resolve(const char *name){
  if(!std::strcmp(name,"memset"))return reinterpret_cast<void*>(kMemset);
  try{return reinterpret_cast<void*>(guest_host->Marker(name));}
  catch(const std::exception &e){std::fprintf(stderr,"unimplemented fixture import %s: %s\n",name,e.what());return nullptr;}
}
int main(){
  using namespace bunker::windows;
  unsigned checks=0;
  auto require=[&](bool condition,const char *reason){if(!condition)throw std::runtime_error(reason);++checks;};
  recomp::Runtime runtime;
  Pthreads host(runtime,[](addr_t entry){for(auto &t:kTraces)if(t.address==entry)return true;return false;});
  int guest_errno=123;host.SetErrorSink([&](int e){guest_errno=e;});host.Install();
  runtime.AddTraces(kTraces,std::size(kTraces));
  runtime.AddImport(kMemset,[](State &s){s.gpr.x0.qword=reinterpret_cast<addr_t>(std::memset(reinterpret_cast<void*>(s.gpr.x0.qword),s.gpr.x1.dword,s.gpr.x2.qword));});
  guest_host=&host;elf_image image;
  require(elf_load(PTHREAD_GUEST_IMAGE,0x70000000,Resolve,&image)==0,"NDK pthread caller image");
  auto invoke=[&](const char *name){auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));require(entry!=0,"fixture export");return host.Run(entry);};
  uint64_t self=host.Self();require(self==host.Self(),"stable calling-thread token");
  alignas(64) AndroidThreadAttr tracked_attr{};
  host.AttrInit(&tracked_attr);
  auto reserved=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked_attr),8,[&]{if(host.AttrSetDetach(&tracked_attr,1)||host.AttrSetDetach(&tracked_attr,0))throw std::runtime_error("attr ABA failed");});
  require(reserved.status==1&&tracked_attr.flags==0,"cross-thread attribute ABA invalidates reservations");
  alignas(64) int64_t tracked_condattr=0;
  reserved=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked_condattr),8,[&]{if(host.CondAttrSetClock(&tracked_condattr,1)||host.CondAttrSetClock(&tracked_condattr,0))throw std::runtime_error("condattr ABA failed");});
  require(reserved.status==1&&tracked_condattr==0,"cross-thread clockattr ABA invalidates reservations");
  alignas(64) int32_t tracked_key=0;
  reserved=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked_key),4,[&]{if(host.KeyCreate(&tracked_key,0)||tracked_key!=0||host.KeyDelete(tracked_key))throw std::runtime_error("key output failed");});
  require(reserved.status==1&&tracked_key==0,"same-value pthread_key_create output is tracked");
  alignas(64) uint8_t tracked_mutex[64]{};
  reserved=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(tracked_mutex),4,[&]{if(host.MutexInit(tracked_mutex,nullptr)||host.MutexDestroy(tracked_mutex)||host.MutexInit(tracked_mutex,nullptr))throw std::runtime_error("mutex ABA failed");});
  require(reserved.status==1&&*reinterpret_cast<uint32_t*>(tracked_mutex)==0&&host.MutexDestroy(tracked_mutex)==0,"opaque mutex lifetime ABA is tracked");
  // Join publishes the actual translated callback result, even if its bits were
  // already present in the caller's result slot.
  uint64_t joined_thread=0;alignas(64) uint64_t tracked_result=0x6013;
  auto nested_entry=reinterpret_cast<addr_t>(elf_symbol(&image,"guest_nested_stack"));
  require(host.Create(&joined_thread,nullptr,nested_entry,0)==0,"create translated result-publishing worker");
  reserved=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked_result),8,[&]{if(host.Join(joined_thread,&tracked_result))throw std::runtime_error("tracked join failed");});
  require(reserved.status==1&&tracked_result==0x6013,"same-value joined translated result is tracked");
  AndroidThreadAttr attr;uint64_t base,size;
  require(host.GetAttr(self,&attr)==95,"external thread stack initially unknown");
  require(host.AttrInit(&attr)==0&&attr.stack_size==1048576&&host.AttrSetStackSize(&attr,100)==22&&host.AttrSetDetach(&attr,2)==22,"Android attrs and minimum stack");
  require(host.AttrSetStackSize(&attr,65536)==0&&host.AttrGetStack(&attr,&base,&size)==0&&base==0&&size==65536,"Android 64-bit stack fields");
  require(host.AttrDestroy(&attr)==0&&host.AttrSetDetach(&attr,1)==22,"attribute lifetime");
  alignas(8) uint8_t m[40]{},recursive[40]{},errorcheck[40]{};
  uint32_t word=0x4000;std::memcpy(recursive,&word,4);word=0x8000;std::memcpy(errorcheck,&word,4);
  require(host.MutexLock(recursive)==0&&host.MutexLock(recursive)==0&&host.MutexLock(recursive,true)==0,"NDK lazy recursive mutex initializer");
  require(host.MutexDestroy(recursive)==16&&host.MutexUnlock(recursive)==0&&host.MutexUnlock(recursive)==0&&host.MutexUnlock(recursive)==0&&host.MutexDestroy(recursive)==0,"recursive depth and destroy busy");
  require(host.MutexLock(recursive)==22&&host.MutexInit(recursive,nullptr)==0&&host.MutexDestroy(recursive)==0,"destroyed mutex rejects lazy resurrection, explicit reinit");
  require(host.MutexLock(errorcheck)==0&&host.MutexLock(errorcheck)==35&&host.MutexLock(errorcheck,true)==16,"NDK lazy errorcheck initializer");
  std::atomic<int> nonowner{0};std::thread foreign([&]{nonowner=host.MutexUnlock(errorcheck);});foreign.join();
  require(nonowner==1&&host.MutexUnlock(errorcheck)==0&&host.MutexDestroy(errorcheck)==0,"errorcheck ownership");
  std::atomic<bool> start{false};std::atomic<unsigned> faults{0};uint64_t counter=0;
  std::vector<std::thread> workers;
  for(unsigned i=0;i<4;++i)workers.emplace_back([&]{while(!start.load())std::this_thread::yield();for(unsigned n=0;n<3000;++n){if(host.MutexLock(m))++faults;++counter;if(host.MutexUnlock(m))++faults;}});
  start=true;for(auto &w:workers)w.join();
  require(counter==12000&&faults==0&&host.MutexDestroy(m)==0,"native contention and lazy normal initializer");
  alignas(8) uint8_t cm[40]{},cond[48]{};int64_t ca;
  require(host.CondAttrInit(&ca)==0&&host.CondAttrSetClock(&ca,1)==0&&ca==2&&host.CondInit(cond,&ca)==0,"Bionic condattr bit encoding");
  require(host.MutexLock(cm)==0,"condition mutex");
  AndroidTimespec deadline;Pthreads::ClockGetTime(1,&deadline);deadline.nanoseconds+=10000000;if(deadline.nanoseconds>=1000000000){deadline.nanoseconds-=1000000000;++deadline.seconds;}
  auto began=std::chrono::steady_clock::now();
  require(host.CondWait(cond,cm,&deadline)==110&&std::chrono::steady_clock::now()-began>=std::chrono::milliseconds(5)&&host.MutexLock(cm,true)==16,"absolute monotonic timeout reacquires mutex");
  deadline.nanoseconds=-1;require(host.CondWait(cond,cm,&deadline)==22,"invalid timespec");
  require(host.MutexUnlock(cm)==0&&host.CondWait(cond,cm,&deadline)==22&&host.CondDestroy(cond)==0&&host.CondAttrDestroy(&ca)==0,"condition lifetime");
  require(host.CondWake(cond,true)==22,"destroyed condition rejected");
  unsigned ready=0;bool release=false;std::atomic<unsigned> awoken{0};workers.clear();
  require(host.CondInit(cond,nullptr)==0,"reinitialize realtime condition");
  for(unsigned i=0;i<3;++i)workers.emplace_back([&]{host.MutexLock(cm);++ready;host.CondWake(cond,true);while(!release)if(host.CondWait(cond,cm))++faults;host.MutexUnlock(cm);++awoken;});
  host.MutexLock(cm);while(ready!=3)host.CondWait(cond,cm);release=true;host.CondWake(cond,true);host.MutexUnlock(cm);
  for(auto &w:workers)w.join();require(awoken==3&&faults==0,"broadcast with atomic release/wait");
  require(host.CondDestroy(cond)==0&&host.MutexDestroy(cm)==0,"condition and mutex clean shutdown");
  int32_t key;require(host.KeyCreate(&key,0)==0&&host.SetSpecific(key,0x1234)==0&&host.GetSpecific(key)==0x1234,"TLS value");
  uint64_t child_id=0,previous_id=0;
  for(unsigned i=0;i<6;++i){std::thread t([&]{child_id=host.Self();if(host.GetSpecific(key)!=0)++faults;host.SetSpecific(key,55);});t.join();require(child_id!=previous_id&&child_id!=self,"lifetime-unique external thread IDs");previous_id=child_id;}
  require(host.Kill(child_id,0)==3&&host.GetAttr(child_id,&attr)==3,"external thread lifetime uses retained native handles");
  require(faults==0&&host.GetSpecific(key)==0x1234,"TLS isolation across reused OS thread IDs");
  int32_t old_key=key;require(host.KeyDelete(key)==0&&host.KeyCreate(&key,0)==0&&key==old_key&&host.GetSpecific(key)==0,"recycled key generation does not resurrect values");host.KeyDelete(key);
  std::array<int32_t,128> keys;
  for(auto &k:keys)if(host.KeyCreate(&k,0))++faults;
  require(!faults&&host.KeyCreate(&key,0)==11,"NDK 128 key limit");for(auto k:keys)host.KeyDelete(k);
  require(host.SetSpecific(-1,1)==22&&host.KeyDelete(128)==22&&host.KeyCreate(&key,0x123)==22,"TLS error paths and callback validation");
  uint64_t unused;require(host.Create(&unused,nullptr,0x123,0)==22&&host.Join(self,nullptr)==35&&host.Detach(0x123)==3,"thread argument and lifetime errors");
  alignas(8) uint8_t rw[56]{};
  require(host.RwLock(rw,false)==0&&host.RwLock(rw,false)==0&&host.RwLock(rw,true)==35&&host.RwDestroy(rw)==16,"recursive readers and upgrade error");
  std::atomic<bool> writing{false};std::thread writer([&]{if(host.RwLock(rw,true))++faults;writing=true;if(host.RwUnlock(rw))++faults;});
  require(!writing&&host.RwUnlock(rw)==0&&host.RwUnlock(rw)==0,"rwlock writer excludes readers");writer.join();
  require(writing&&faults==0&&host.RwDestroy(rw)==0&&host.RwUnlock(rw)==22,"rwlock writer handoff and lifetime");
  require(host.Kill(self,0)==0&&host.Kill(self,10)==38&&host.SetName(self,"01234567890123456")==34,"signals explicit unsupported, Android thread-name limit");
  State state{};state.gpr.x0.qword=99;AndroidTimespec time;state.gpr.x1.qword=reinterpret_cast<addr_t>(&time);state.gpr.x30.qword=0xfeedffff;
  runtime.Run(state,host.Marker("clock_gettime"));require(static_cast<int32_t>(state.gpr.x0.dword)==-1&&guest_errno==22,"clock errno adapter");
  struct GuardedTime {uint64_t before[2];AndroidTimespec time;uint64_t after[2];} boot_time;
  std::memset(&boot_time,0xa5,sizeof(boot_time));
  auto ticks_before=GetTickCount64();
  require(Pthreads::ClockGetTime(7,&boot_time.time)==0&&boot_time.time.seconds>=0&&boot_time.time.nanoseconds>=0&&boot_time.time.nanoseconds<1000000000,"CLOCK_BOOTTIME returns Android64 timespec");
  auto ticks_after=GetTickCount64();auto boot_ms=static_cast<uint64_t>(boot_time.time.seconds)*1000+boot_time.time.nanoseconds/1000000;
  require(boot_ms+32>=ticks_before&&boot_ms<=ticks_after+32&&boot_time.time.nanoseconds%100==0&&boot_time.before[0]==0xa5a5a5a5a5a5a5a5ULL&&boot_time.before[1]==0xa5a5a5a5a5a5a5a5ULL&&boot_time.after[0]==0xa5a5a5a5a5a5a5a5ULL&&boot_time.after[1]==0xa5a5a5a5a5a5a5a5ULL,"boot epoch matches Windows uptime, exact16-byte output bounds");
  auto first_boot=boot_time.time;std::this_thread::sleep_for(std::chrono::milliseconds(20));
  auto boot_entry=reinterpret_cast<addr_t>(elf_symbol(&image,"guest_boot_clock"));
  require(host.Run(boot_entry,{reinterpret_cast<addr_t>(&boot_time.time)})==0x6014,"actual translated NDK CLOCK_BOOTTIME caller");
  auto later_boot=boot_time.time;
  require((later_boot.seconds>first_boot.seconds||(later_boot.seconds==first_boot.seconds&&later_boot.nanoseconds>first_boot.nanoseconds))&&boot_time.before[1]==0xa5a5a5a5a5a5a5a5ULL&&boot_time.after[0]==0xa5a5a5a5a5a5a5a5ULL,"translated boot-relative clock progresses monotonically with correct wire bounds");
  auto unchanged=boot_time.time;
  state={};state.gpr.x0.qword=6;state.gpr.x1.qword=reinterpret_cast<addr_t>(&boot_time.time);state.gpr.x30.qword=0xfeedffff;runtime.Run(state,host.Marker("clock_gettime"));
  require(static_cast<int32_t>(state.gpr.x0.dword)==-1&&guest_errno==22&&!std::memcmp(&unchanged,&boot_time.time,sizeof(unchanged)),"unsupported clock IDs fail without fabricated time");
  require(invoke("guest_primitives")==0x600f,"translated NDK recursive/errorcheck/condclock/rwlock/signal callers");
  require(invoke("guest_threads")==0x600d,"translated contention, cond wake, once, separate stacks/TLS, TLS destructor rounds, thread results");
  require(invoke("guest_exit_lifetimes")==0x600e,"translated pthread_exit TLS cleanup and lifetime-unique worker tokens");
  require(invoke("guest_detach")==0x6010,"translated detached attrs and explicit detach");
  require(invoke("guest_once_exit")==0x6011,"translated pthread_exit resets incomplete once and allows retry");
  require(invoke("guest_destructor_limit")==0x6012,"translated TLS destructor limit is exactly four rounds");
  require(invoke("guest_nested_stack")==0x6013&&invoke("guest_nested_stack")==0x6013,"nested translated callbacks preserve caller stack and once allocation reuse");
  require(guest_errno==22,"pthread errors do not overwrite guest errno");
  require(host.GetAttr(self,&attr)==0&&attr.stack_size==1048576,"getattr reports actual guest stack after Run");
  MEMORY_BASIC_INFORMATION guard_info,stack_info;
  require(attr.guard_size==4096&&VirtualQuery(reinterpret_cast<void*>(attr.stack_base-1),&guard_info,sizeof(guard_info))&&guard_info.State==MEM_RESERVE&&VirtualQuery(reinterpret_cast<void*>(attr.stack_base),&stack_info,sizeof(stack_info))&&stack_info.State==MEM_COMMIT&&stack_info.Protect==PAGE_READWRITE,"guest stack has actual inaccessible guard pages");
  require(host.ReleaseCurrent()==0&&host.Kill(self,0)==3&&host.Self()!=self,"explicit external guest-thread teardown and new lifetime");
  require(host.Shutdown()==0&&host.Create(&unused,nullptr,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_nested_stack")),0)==11,"explicit worker shutdown refuses creation and preserves callback runner");
  std::printf("Windows Android pthread ABI: %u checks passed; translated NDK workers/once/TLS callbacks, 6000 guest mutex increments, cond broadcast, explicit exit/detach.\n",checks);
}

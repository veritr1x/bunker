#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <process.h>
#include <pthread.h>
#include "pthread_host.h"
#include "egl_host.h"
#include "libc.h"
#include "nonlocal_jmp.h"
#include "../whole/bridge.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
namespace {
std::atomic<unsigned>checks{0},completed{0};
void Require(bool yes,const char*why){if(!yes){std::fprintf(stderr,"passive thread storage: %s\n",why);std::abort();}++checks;}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
bool Translated(addr_t pc){for(auto&t:kTraces)if(t.address==pc)return true;return false;}
#include "game_bootstrap_detail.h"
bunker::windows::Pthreads *threads;
bunker::windows::EglHost *egl;
void*Resolve(const char*n){if(!std::strncmp(n,"egl",3))return reinterpret_cast<void*>(egl->Marker(n));return reinterpret_cast<void*>(threads->Marker(n));}
struct Observed {uint64_t token=0,destructors=0;int32_t initial=-1,error=-1,cleared=-1,key_result=-1;};
struct Job {std::function<void()> body;};
unsigned __stdcall Raw(void*p){std::unique_ptr<Job>job(static_cast<Job*>(p));try{job->body();}catch(const std::exception&e){std::fprintf(stderr,"raw test thread: %s\n",e.what());std::abort();}return 0;}
}
int main(){
 using namespace bunker::windows;
 recomp::Entry unchanged_helper=GameOriginalSaveHelper;(void)unchanged_helper;
 bunker::jni::Host java([](addr_t){return false;});recomp::Runtime runtime;runtime.AddTraces(kTraces,std::size(kTraces));
 Pthreads pthreads(runtime,Translated);threads=&pthreads;pthreads.Install();NativeWindows windows(java);EglHost graphics(windows,PASSIVE_ANGLE);egl=&graphics;graphics.Install(runtime);
 elf_image image{};Require(!elf_load(PASSIVE_IMAGE,0x5c000000,Resolve,&image),"strict NDK passive-storage fixture loads");
 auto tick=reinterpret_cast<addr_t>(elf_symbol(&image,"storage_guest_tick"));auto probe=reinterpret_cast<addr_t>(elf_symbol(&image,"storage_guest_probe"));auto dtor=reinterpret_cast<addr_t>(elf_symbol(&image,"storage_guest_destructor"));
 int32_t key=-1;Require(!pthreads.KeyCreate(&key,dtor),"actual NDK destructor registered for explicit guest TLS cleanup");
 auto Tick=[&]{alignas(16)std::array<uint8_t,65536>stack{};State s{};s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,tick);Require(s.gpr.x0.qword==0x123456789abcdef0ULL&&s.gpr.pc.qword==0xfeedffff,"actual Runtime first-touch tick returns without providers");};
 auto Error=[&]{State s{};graphics.Invoke("eglGetError",s);return s.gpr.x0.dword;};
 std::mutex token_mutex;std::set<uint64_t>tokens;std::array<Observed,16>outputs{};
 for(unsigned kind=0;kind<2;++kind){
  for(unsigned order=0;order<2;++order){
   for(unsigned repeat=0;repeat<4;++repeat){
    const unsigned index=kind*8+order*4+repeat;
    auto Body=[&,index,order]{
     if(order)Tick();
     auto &frames=GameAutomaticEnvironments::Frames();Require(frames.empty(),"new native thread has an empty independent frame vector");
     const uint64_t token=pthreads.Self();Require(token!=0&&Error()==0x3000,"real Pthreads binding and EGL error begin clean");
     {std::lock_guard lock(token_mutex);Require(tokens.insert(token).second,"native thread/token reuse cannot alias another owner");}
     GameAutomaticEnvironments owner;alignas(16)std::array<uint8_t,4096>stack{};const auto high=reinterpret_cast<addr_t>(stack.data()+stack.size());
     frames.push_back({token,1,high,0xfeedffff,0});State saved{};saved.gpr.x30.qword=0x825b0580;saved.gpr.sp.qword=high-0x140;saved.gpr.x0.qword=saved.gpr.sp.qword+8;
     owner.BeforeSetjmp(saved,token);auto region=owner.Find(saved.gpr.x0.qword,256,token);
     Require(region&&region->generation==1&&region->low==saved.gpr.x0.qword,"actual Frame metadata binds scalar environment/generation to current token");
     Require(!owner.Find(saved.gpr.x0.qword,264,token)&&!owner.Find(saved.gpr.x0.qword,256,token+1),"Frame lookup rejects wrong size/owner");
     frames.push_back({token,2,high-0x200,0xfeedffff,0x12340000});Require(owner.Find(0x12340000,256,token)->generation==2,"nested frame retains independent generation");frames.pop_back();Require(!owner.Find(0x12340000,256,token)&&owner.Find(saved.gpr.x0.qword,256,token),"normal pop revokes only nested frame metadata");
     if(!order)Tick();
     auto &out=outputs[index];Require(pthreads.Run(probe,{reinterpret_cast<addr_t>(&out),uint64_t(key)})==token,"actual NDK uses its existing real binding");
     Require(out.token==token&&!out.key_result&&out.initial==0x3000&&out.error==0x300d&&out.cleared==0x3000,"actual NDK thread TLS/error record and EGL clear-on-read remain truthful");
     Require(!pthreads.ReleaseCurrent()&&out.destructors==1,"explicit ReleaseCurrent runs actual NDK guest destructor exactly once");graphics.ReleaseCurrentThread();
     frames.pop_back();Require(!owner.Find(saved.gpr.x0.qword,256,token),"final normal pop revokes frame");
     // Deliberately leave scalar-only metadata: the native storage destructor
     // must not call Forget/jumps/guest cleanup or dereference environment.
     frames.push_back({token,3,0x1234,0x5678,0xabcdef01});++completed;
    };
    if(!kind){std::thread worker(Body);worker.join();}
    else{auto job=std::make_unique<Job>();job->body=Body;auto handle=reinterpret_cast<HANDLE>(_beginthreadex(nullptr,0,Raw,job.get(),0,nullptr));Require(handle!=nullptr,"actual raw _beginthreadex created");job.release();Require(WaitForSingleObject(handle,INFINITE)==WAIT_OBJECT_0,"actual raw native thread terminated");CloseHandle(handle);}
    Require(outputs[index].destructors==1,"passive native container teardown never reruns guest destructors");AndroidThreadAttr attr{};Require(pthreads.GetAttr(outputs[index].token,&attr)==3,"real external thread registry tombstone survives passive map deletion until provider ownership retires it");
   }
  }
 }
 Require(completed==16&&tokens.size()==16,"both native exits and both first-touch orders completed");Require(GameAutomaticEnvironments::Frames().empty(),"workers never alter main frame metadata");Require(Error()==0x3000,"worker EGL errors never alter main thread");Require(!pthreads.KeyDelete(key),"explicit guest key retirement unchanged");Require(!pthreads.Shutdown(),"actual Pthreads registry shutdown remains explicit");
 std::printf("Passive native thread storage: %u checks passed;16 std::thread/raw _beginthreadex exits, both first-touch orders, actual NDK TLS/error callbacks, real Frame metadata and passive cleanup\n",checks.load());
}

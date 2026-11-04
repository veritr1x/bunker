#include "runtime.h"
#include "sensor_service_fixture.h"
#include "sensor_service.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cerrno>
#include <stdexcept>
using bunker::windows::SensorService;
extern "C" Memory*sub_704119f8(State&,addr_t,Memory*);
extern "C" Memory*sub_704124d8(State&,addr_t,Memory*);
static recomp::Runtime*active_runtime;
static addr_t manager_marker;
static unsigned long polls;
extern "C" uint32_t __real___bunker_guest_poll_requested();
extern "C" uint32_t __wrap___bunker_guest_poll_requested(){++polls;auto r=__real___bunker_guest_poll_requested();if(r){die("unexpected poll request");}return r;}
extern "C" void __wrap___bunker_guest_poll_slow(State*,uint64_t,uint64_t,uint64_t){die("unexpected slow poll");}
extern "C" Memory*sub_700b8660(State&s,addr_t,Memory*m){++sensor_calls;return active_runtime->Run(s,manager_marker,m);}
extern "C" Memory*sub_700b8440(State&s,addr_t,Memory*m){if(s.gpr.x0.qword!=GLOBAL_BASE+0xe048||s.gpr.x1.dword||s.gpr.x2.qword!=0x240){die("original memset arguments");}++memset_calls;memset((void*)s.gpr.x0.qword,0,0x240);s.gpr.pc.qword=s.gpr.x30.qword;return m;}
#define FENCE(head) extern "C" Memory*sub_##head(State&,addr_t,Memory*){die("excluded nonnull-manager path " #head);return nullptr;}
#include "sensor_fences.h"
static void*resolve(const char*name){if(strcmp(name,"ASensorManager_getInstance")){die("unscoped NDK import");}return(void*)manager_marker;}
static void check(bool value,const char*why){if(!value){die(why);}}
static void seed(State&s,addr_t head){memset(&s,0,sizeof(s));for(unsigned i=0;i<31;++i){memcpy((uint8_t*)&s.gpr.x0+i*16,&port_seeds[i],8);}s.gpr.sp.qword=entry_sp;s.gpr.pc.qword=head;memcpy(&s.simd,port_qseeds,512);s.fpcr.flat=port_controls[0];s.fpsr.flat=port_controls[1];}
static uint64_t run_ndk(elf_image&image,const char*name,addr_t argument){State s{};seed(s,0);s.gpr.x0.qword=argument;s.gpr.x30.qword=FIXTURE_RETURN;auto pc=(addr_t)elf_symbol(&image,name);check(pc!=0,"actual NDK export");active_runtime->Run(s,pc);check(s.gpr.pc.qword==FIXTURE_RETURN&&s.gpr.sp.qword==entry_sp,"NDK genuine RET/SP");return s.gpr.x0.qword;}
int main(int argc,char**argv){if(argc!=3){die("host arguments");}int polled=atoi(argv[1]);setup((unsigned)strtoul(argv[2],0,10));
 SensorService provider(SensorService::Profile::Unavailable);manager_marker=provider.Marker("ASensorManager_getInstance");check(manager_marker==0x7ff470000000ULL,"dedicated typed marker");
 for(int kind=0;kind<4;++kind){bool rejected=false;try{if(kind==0){SensorService invalid(static_cast<SensorService::Profile>(99));}else if(kind==1){SensorService invalid(SensorService::Profile::Unavailable,0);}else if(kind==2){SensorService invalid(SensorService::Profile::Unavailable,3);}else{provider.Marker("ASensorManager_getSensorList");}}catch(const std::invalid_argument&){rejected=true;}check(rejected,"invalid profile/marker/unsupported API rejected");}
 recomp::Runtime rt;active_runtime=&rt;provider.Install(rt);bool duplicate=false;try{provider.Install(rt);}catch(const std::logic_error&){duplicate=true;}check(duplicate,"duplicate Install rejected");
 rt.AddTraces(kTraces,std::size(kTraces));const recomp::Trace original[]={{SENSOR_HEAD,sub_704119f8},{0x704124d8,sub_704124d8}};rt.AddTraces(original,2);
 State direct{};seed(direct,manager_marker);direct.gpr.x0.qword=UINT64_MAX;direct.gpr.x30.qword=FIXTURE_RETURN;State expected=direct;expected.gpr.x0.qword=0;expected.gpr.pc.qword=FIXTURE_RETURN;alignas(16)uint8_t token[64];memset(token,0x6d,64);Memory*m=(Memory*)token;
#ifdef _WIN32
 // Measure Runtime/TLS/FENV effects through a matched private control import.
 // Capture LastError before _errno(), which may itself touch native TLS.
 const addr_t control_marker=manager_marker+8;rt.AddImport(control_marker,recomp::MakeBridge<addr_t()>([]{return addr_t(0);}));
 State control=direct;rt.Run(control,control_marker,m);control=direct;
 SetLastError(0x12345678);rt.Run(control,control_marker,m);control_last_error=GetLastError();
#endif
 errno=E2BIG;
#ifdef _WIN32
 SetLastError(0x12345678);
#endif
 Memory*returned=rt.Run(direct,manager_marker,m);
#ifdef _WIN32
 provider_last_error=GetLastError();
#endif
 const int after_errno=errno;
 check(returned==m&&!memcmp(&direct,&expected,sizeof(direct)),"full1200 direct bridge and pointer return zero");check(after_errno==E2BIG,"provider leaves errno unchanged");provider_errno_checked=1;
#ifdef _WIN32
 check(provider_last_error==control_last_error,"provider Runtime path matches native LastError control");
#endif
 elf_image image{};check(!elf_load(SENSOR_IMAGE,0x78000000,resolve,&image),"actual NDK sensor caller image");check(!run_ndk(image,"sensor_direct",UINT64_MAX)&&!run_ndk(image,"sensor_pointer",manager_marker),"actual NDK direct/function-pointer NULL return");
 State s{};seed(s,SENSOR_HEAD);for(unsigned iteration=0;iteration<(case_id==3?2U:1U);++iteration){seed(s,SENSOR_HEAD);check(rt.Run(s,SENSOR_HEAD,m)==m&&s.gpr.pc.qword==FIXTURE_RETURN,"complete original unavailable branch genuine RET/token");check_effects(iteration+1);}
 for(unsigned i=0;i<8;++i){uint32_t type=capability_types[i];if(case_id==2&&type<36){continue;}State cap{};seed(cap,0x704124d8);cap.gpr.x0.qword=UINT64_C(0xdeadbeef00000000)|type;check(rt.Run(cap,0x704124d8,m)==m&&!cap.gpr.x0.qword&&cap.gpr.pc.qword==FIXTURE_RETURN&&cap.gpr.sp.qword==entry_sp,"retained complete capability query returns false/RET/SP");for(unsigned reg=19;reg<=29;++reg){check(get64((uint8_t*)&cap.gpr.x0+reg*16)==port_seeds[reg],"capability callee-saved ABI");}++capability_checks;}
 for(auto byte:token){check(byte==0x6d,"opaque memory token bytes");}
 alignas(16)uint8_t snapshot[800]{};for(unsigned i=0;i<32;++i){put64(snapshot+i*8,get64((uint8_t*)&s.gpr.x0+i*16));}memcpy(snapshot+256,&s.simd,512);put64(snapshot+784,s.fpcr.flat);emit(snapshot,0,polls,polled);
}

#include "game_exception_diagnostic.h"
#include <array>
#include <cstring>
#include <stdexcept>

namespace {
unsigned checks=0;
void Check(bool value){++checks;if(!value)throw std::runtime_error("terminal diagnostic control failed");}
void SetEnvironment(){std::fesetround(FE_UPWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);errno=E2BIG;SetLastError(0x12003400);}
void Environment(){const auto last=GetLastError();const int error=errno;Check(last==0x12003400);Check(error==E2BIG);Check(std::fegetround()==FE_UPWARD);Check(std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO);}
}

int main(){try{
 static_assert(sizeof(State)==1200);
 auto*got=VirtualAlloc(reinterpret_cast<void*>(0x87400000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
 auto*global=VirtualAlloc(reinterpret_cast<void*>(0x87980000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
 Check(got==reinterpret_cast<void*>(0x87400000));Check(global==reinterpret_cast<void*>(0x87980000));
 *reinterpret_cast<uint64_t*>(0x87408e50)=0x87985200;*reinterpret_cast<uint64_t*>(0x87985200)=0x82610b88;
 auto*pages=static_cast<uint8_t*>(VirtualAlloc(nullptr,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(pages!=nullptr);
 DWORD previous=0;Check(VirtualProtect(pages+4096,4096,PAGE_NOACCESS,&previous)!=0);pages[4095]='X';
 alignas(16)uint64_t frames[16]{};frames[2]=reinterpret_cast<addr_t>(&frames[6]);frames[3]=0x8260d628;frames[6]=reinterpret_cast<addr_t>(&frames[10]);frames[7]=0xabc020;frames[10]=0;frames[11]=0xabc030;
 uint64_t typeinfo[2]={0x12345678,reinterpret_cast<addr_t>(pages+4095)};
 uint64_t header[16]{};header[1]=reinterpret_cast<addr_t>(typeinfo);header[4]=0;header[12]=0x434c4e47432b2b00;
 std::array<uint64_t,16>original_frames{};std::memcpy(original_frames.data(),frames,sizeof(frames));
 for(unsigned mode=0;mode<3;++mode){
  State state{};for(size_t i=0;i<sizeof(state);++i)reinterpret_cast<uint8_t*>(&state)[i]=static_cast<uint8_t>(i*13+mode);
  state.gpr.pc.qword=0;state.gpr.x30.qword=0x8260df44;state.gpr.x0.qword=0;
  state.gpr.sp.qword=mode==2?1:reinterpret_cast<addr_t>(frames);state.gpr.x29.qword=mode==2?UINT64_MAX-3:reinterpret_cast<addr_t>(&frames[2]);
  state.gpr.x19.qword=mode==0?reinterpret_cast<addr_t>(header):1;state.gpr.x8.qword=mode==0?reinterpret_cast<addr_t>(header):UINT64_MAX-3;
  const State before=state;SetEnvironment();GameExceptionDiagnostic::ReportNull(state);Environment();Check(!std::memcmp(&state,&before,sizeof(state)));
  Check(!std::memcmp(frames,original_frames.data(),sizeof(frames)));Check(header[1]==reinterpret_cast<addr_t>(typeinfo));Check(header[4]==0);
  Check(*reinterpret_cast<uint64_t*>(0x87408e50)==0x87985200);Check(*reinterpret_cast<uint64_t*>(0x87985200)==0x82610b88);Check(pages[4095]=='X');
 }
 Check(VirtualFree(got,0,MEM_RELEASE)!=0);Check(VirtualFree(global,0,MEM_RELEASE)!=0);Check(VirtualFree(pages,0,MEM_RELEASE)!=0);
 std::printf("GAME-EXCEPTION-DIAGNOSTIC-PASS checks=%u reports=3 State_bytes=%zu\n",checks,sizeof(State));return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"GAME-EXCEPTION-DIAGNOSTIC-FAIL %s\n",e.what());return 1;}}

#include "game_exception_diagnostic.h"
#include <array>
#include <cstring>
#include <stdexcept>

namespace {
unsigned checks=0;
void Check(bool value){++checks;if(!value)throw std::runtime_error("terminal diagnostic control failed");}
void SetEnvironment(){std::fesetround(FE_UPWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);errno=E2BIG;SetLastError(0x12003400);}
void Environment(){const auto last=GetLastError();const int error=errno;Check(last==0x12003400);Check(error==E2BIG);Check(std::fegetround()==FE_UPWARD);Check(std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO);}
State raise_before{};State*raise_address=nullptr;addr_t raise_pc=0;unsigned raise_calls=0,raise_mode=0;uint64_t*raise_header=nullptr;
alignas(16)std::array<uint8_t,64>input_token{},output_token{};
Memory* OriginalRaise(State&s,addr_t pc,Memory*m){
 Environment();Check(&s==raise_address);Check(pc==raise_pc);Check(m==reinterpret_cast<Memory*>(input_token.data()));Check(!std::memcmp(&s,&raise_before,sizeof(s)));++raise_calls;
 s.gpr.x5.qword^=0x9876;s.gpr.x0.qword=7;s.gpr.pc.qword=s.gpr.x30.qword;
 if(raise_mode==2){s.gpr.pc.qword=0x8457a118;s.gpr.x30.qword=0x8457a118;s.gpr.x21.qword=0x8799a000;s.gpr.sp.qword+=0x80;}
 if(raise_header)raise_header[4]=0x82610b88;
 std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID);errno=ERANGE;SetLastError(0x98761234);
 return reinterpret_cast<Memory*>(output_token.data());
}
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
 input_token.fill(0xa3);output_token.fill(0x6c);
 bool rejected=false;try{GameExceptionDiagnostic::ConfigureRaise(nullptr,true);}catch(const std::invalid_argument&){rejected=true;}Check(rejected);
 *reinterpret_cast<uint64_t*>(0x8740b950)=0x826263cc;
 for(unsigned mode=0;mode<4;++mode){
  State state{};for(size_t i=0;i<sizeof(state);++i)reinterpret_cast<uint8_t*>(&state)[i]=static_cast<uint8_t>(i*11+mode);
  header[4]=0;raise_header=mode==3?nullptr:header;raise_mode=mode;
  state.gpr.x0.qword=mode==3?1:reinterpret_cast<addr_t>(header)+0x60;state.gpr.pc.qword=0x826263cc;state.gpr.x30.qword=0x8260d5a0;state.gpr.x21.qword=reinterpret_cast<addr_t>(header);state.gpr.sp.qword=reinterpret_cast<addr_t>(frames);
  raise_before=state;raise_address=&state;raise_pc=0x826263cc;
  GameExceptionDiagnostic::ConfigureRaise(OriginalRaise,mode!=0);SetEnvironment();Memory*result=GameExceptionDiagnostic::Raise(state,raise_pc,reinterpret_cast<Memory*>(input_token.data()));
  const auto last=GetLastError();const int error=errno;Check(last==0x98761234);Check(error==ERANGE);Check(std::fegetround()==FE_DOWNWARD);Check(std::fetestexcept(FE_ALL_EXCEPT)==FE_INVALID);Check(result==reinterpret_cast<Memory*>(output_token.data()));
  State expected=raise_before;expected.gpr.x5.qword^=0x9876;expected.gpr.x0.qword=7;expected.gpr.pc.qword=expected.gpr.x30.qword;
  if(mode==2){expected.gpr.pc.qword=0x8457a118;expected.gpr.x30.qword=0x8457a118;expected.gpr.x21.qword=0x8799a000;expected.gpr.sp.qword+=0x80;}
  Check(!std::memcmp(&state,&expected,sizeof(state)));Check(header[4]==(mode==3?0:0x82610b88));
  for(uint8_t value:input_token){Check(value==0xa3);}
  for(uint8_t value:output_token){Check(value==0x6c);}
 }
 Check(raise_calls==4);Check(*reinterpret_cast<uint64_t*>(0x8740b950)==0x826263cc);
 Check(VirtualFree(got,0,MEM_RELEASE)!=0);Check(VirtualFree(global,0,MEM_RELEASE)!=0);Check(VirtualFree(pages,0,MEM_RELEASE)!=0);
 std::printf("GAME-EXCEPTION-DIAGNOSTIC-PASS checks=%u reports=3 raise_calls=%u State_bytes=%zu token_bytes=64\n",checks,raise_calls,sizeof(State));return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"GAME-EXCEPTION-DIAGNOSTIC-FAIL %s\n",e.what());return 1;}}

#include "signal_frame.h"
#include <algorithm>
#include <cstring>
#include <stdexcept>

namespace recomp::signal_frame {
namespace {
constexpr uint64_t kNzcv=0xf0000000ULL,kFpsrFlags=0x9f;
void Require(bool value,const char *why){if(!value)throw std::invalid_argument(why);}
bool Range(Bounds bounds,addr_t start,uint64_t size){
  return bounds.low&&bounds.high>bounds.low&&start>=bounds.low&&start<=bounds.high&&size<=bounds.high-start;
}
void Put(std::vector<uint8_t> &bytes,size_t offset,uint64_t value,unsigned width){
  if(offset>bytes.size()||width>bytes.size()-offset)throw std::logic_error("internal frame offset");
  for(unsigned i=0;i<width;++i)bytes[offset+i]=uint8_t(value>>(i*8));
}
uint64_t Get(const uint8_t *bytes,size_t offset,unsigned width){
  uint64_t value=0;for(unsigned i=0;i<width;++i)value|=uint64_t(bytes[offset+i])<<(i*8);return value;
}
uint64_t Gpr(const State &state,unsigned index){
  static_assert(offsetof(GPR,x0)==8&&offsetof(GPR,x30)==488);
  uint64_t value;std::memcpy(&value,reinterpret_cast<const uint8_t*>(&state.gpr)+index*16+8,8);return value;
}
void Gpr(State &state,unsigned index,uint64_t value){std::memcpy(reinterpret_cast<uint8_t*>(&state.gpr)+index*16+8,&value,8);}
uint64_t Nzcv(const State &s){return (uint64_t(bool(s.sr.n))<<31)|(uint64_t(bool(s.sr.z))<<30)|(uint64_t(bool(s.sr.c))<<29)|(uint64_t(bool(s.sr.v))<<28);}
uint32_t Fpsr(const State &s){return uint32_t((s.fpsr.flat&~kFpsrFlags)|bool(s.sr.ioc)|(uint64_t(bool(s.sr.dzc))<<1)|
  (uint64_t(bool(s.sr.ofc))<<2)|(uint64_t(bool(s.sr.ufc))<<3)|(uint64_t(bool(s.sr.ixc))<<4)|(uint64_t(bool(s.sr.idc))<<7));}
void Synchronize(State &s,uint64_t pstate,uint32_t fpcr,uint32_t fpsr){
  s.nzcv.flat=pstate&kNzcv;s.sr.n=(pstate>>31)&1;s.sr.z=(pstate>>30)&1;s.sr.c=(pstate>>29)&1;s.sr.v=(pstate>>28)&1;
  s.fpcr.flat=fpcr;s.fpsr.flat=fpsr;
  s.sr.ioc=fpsr&1;s.sr.dzc=(fpsr>>1)&1;s.sr.ofc=(fpsr>>2)&1;s.sr.ufc=(fpsr>>3)&1;s.sr.ixc=(fpsr>>4)&1;s.sr.idc=(fpsr>>7)&1;
}
void ValidateSaved(const State &s,Bounds bounds){
  Require(!(s.gpr.sp.qword&15)&&Range(bounds,s.gpr.sp.qword,0),"saved SP is outside registered stack or misaligned");
  Require(s.gpr.pc.qword&&!(s.gpr.pc.qword&3),"saved PC is null or misaligned");
}
}
Image Serialize(const State &state,const Metadata &metadata,const Request &request){
  ValidateSaved(state,request.interrupted_stack);
  Require(request.handler&&!(request.handler&3)&&request.restorer&&!(request.restorer&3),"handler/restorer must be aligned nonzero guest code addresses");
  Require(request.signal>0&&request.signal<=64,"invalid AArch64 signal number");
  Require(Get(metadata.siginfo.data(),0,4)==uint32_t(request.signal),"siginfo signum disagrees with handler argument");
  Require(!(state.fpcr.flat>>32)&&!(state.fpsr.flat>>32),"nonarchitectural high FPCR/FPSR bits cannot be serialized");
  Require(metadata.altstack.size<=UINT64_MAX-metadata.altstack.pointer,"saved alternate stack overflows address space");
  Require(request.stack_top>=16&&Range(request.delivery_stack,request.stack_top,0),"delivery stack top outside registered range");
  const addr_t record=(request.stack_top-16)&~addr_t(15);
  Require(record>=kFrameSize,"signal frame address underflows");
  const addr_t base=record-kFrameSize;
  Require(Range(request.delivery_stack,base,kFrameSize+kFrameRecordSize),"signal frame does not fit registered delivery stack");
  Image image;image.base=base;image.frame_record=record;image.info=base;image.ucontext=base+kUcontextOffset;
  image.bytes.resize(kFrameSize+kFrameRecordSize,0);
  auto &b=image.bytes;
  std::copy(metadata.siginfo.begin(),metadata.siginfo.end(),b.begin());
  Put(b,128,metadata.uc_flags,8);Put(b,136,metadata.uc_link,8);
  Put(b,144,metadata.altstack.pointer,8);Put(b,152,metadata.altstack.flags,4);Put(b,160,metadata.altstack.size,8);
  Put(b,168,metadata.mask,8);
  Put(b,kMachineOffset,metadata.fault_address,8);
  for(unsigned i=0;i<31;++i)Put(b,kMachineOffset+8+i*8,Gpr(state,i),8);
  Put(b,kMachineOffset+256,state.gpr.sp.qword,8);Put(b,kMachineOffset+264,state.gpr.pc.qword,8);
  const uint64_t pstate=(metadata.pstate&~kNzcv)|Nzcv(state);
  Put(b,kMachineOffset+272,pstate,8);
  Put(b,kFpsimdOffset,kFpsimdMagic,4);Put(b,kFpsimdOffset+4,kFpsimdSize,4);
  Put(b,kFpsimdOffset+8,Fpsr(state),4);Put(b,kFpsimdOffset+12,state.fpcr.flat,4);
  std::memcpy(b.data()+kFpsimdOffset+16,&state.simd,sizeof(state.simd));
  // The 16-byte null record and remaining reserved context bytes are zero.
  Put(b,kFrameSize,state.gpr.x29.qword,8);Put(b,kFrameSize+8,state.gpr.x30.qword,8);
  image.handler_state=state;
  Synchronize(image.handler_state,pstate,uint32_t(state.fpcr.flat),Fpsr(state));
  image.handler_state.gpr.x0.qword=uint32_t(request.signal);
  if(request.siginfo_handler){image.handler_state.gpr.x1.qword=image.info;image.handler_state.gpr.x2.qword=image.ucontext;}
  image.handler_state.gpr.sp.qword=base;image.handler_state.gpr.x29.qword=record;
  image.handler_state.gpr.x30.qword=request.restorer;image.handler_state.gpr.pc.qword=request.handler;
  // Linux clears TCO on handler entry. BTI/SVE/SME delivery policy is outside
  // this fixed FPSIMD-only serializer; full interrupted PSTATE stays in bytes.
  image.handler_pstate=pstate&~(uint64_t(1)<<25);
  return image;
}
Restored Restore(const View &view,addr_t base,Bounds allowed_stack,const State &baseline){
  Require(view.bytes&&view.size<=UINT64_MAX-view.base,"invalid or overflowing frame byte view");
  Require(!(base&15)&&base>=view.base,"misaligned or out-of-range signal frame");
  const uint64_t offset=base-view.base;
  Require(offset<=view.size&&kFrameSize+kFrameRecordSize<=view.size-offset,"truncated signal frame or FP-chain record");
  const uint8_t *b=view.bytes+offset;
  Restored result{baseline,{}};
  auto &m=result.metadata;
  std::copy(b,b+kSiginfoSize,m.siginfo.begin());
  m.uc_flags=Get(b,128,8);m.uc_link=Get(b,136,8);
  m.altstack.pointer=Get(b,144,8);m.altstack.flags=uint32_t(Get(b,152,4));m.altstack.size=Get(b,160,8);
  Require(m.altstack.size<=UINT64_MAX-m.altstack.pointer,"restored alternate stack overflows address space");
  m.mask=Get(b,168,8);m.fault_address=Get(b,kMachineOffset,8);m.pstate=Get(b,kMachineOffset+272,8);
  for(unsigned i=0;i<31;++i)Gpr(result.state,i,Get(b,kMachineOffset+8+i*8,8));
  result.state.gpr.sp.qword=Get(b,kMachineOffset+256,8);result.state.gpr.pc.qword=Get(b,kMachineOffset+264,8);
  ValidateSaved(result.state,allowed_stack);
  bool found=false,terminated=false;
  for(size_t cursor=kFpsimdOffset;cursor<kFrameSize;){
    Require(kFrameSize-cursor>=16,"truncated context header/terminator");
    const uint32_t magic=uint32_t(Get(b,cursor,4)),size=uint32_t(Get(b,cursor+4,4));
    if(!magic&&!size){terminated=true;break;}
    Require(magic&&size>=16&&!(size&15)&&size<=kFrameSize-cursor,"invalid context record size/alignment");
    Require(magic==kFpsimdMagic,"unsupported AArch64 context extension (SVE/SME/extra/ESR)");
    Require(!found&&size==kFpsimdSize,"duplicate or invalid FPSIMD record");
    const uint32_t fpsr=uint32_t(Get(b,cursor+8,4)),fpcr=uint32_t(Get(b,cursor+12,4));
    Synchronize(result.state,m.pstate,fpcr,fpsr);
    std::memcpy(&result.state.simd,b+cursor+16,sizeof(result.state.simd));
    found=true;cursor+=size;
  }
  Require(found&&terminated,"missing FPSIMD record or null context terminator");
  return result;
}
}  // namespace recomp::signal_frame

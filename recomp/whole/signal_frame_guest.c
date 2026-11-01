#include <signal.h>
#include <sys/ucontext.h>
#include <asm/sigcontext.h>
#include <stddef.h>
#include "signal_frame_driver.h"
_Static_assert(sizeof(siginfo_t)==128,"Android siginfo");
_Static_assert(sizeof(ucontext_t)==4560,"Android ucontext");
_Static_assert(sizeof(mcontext_t)==4384,"Android machine context");
_Static_assert(offsetof(ucontext_t,uc_mcontext)==176,"Android machine offset");
_Static_assert(sizeof(struct fpsimd_context)==528,"FPSIMD record");
static struct FrameReport *report;
void frame_install(struct FrameReport *value){report=value;}
__attribute__((visibility("hidden")))
void frame_body(int signo,siginfo_t *info,void *context,uint64_t entry_sp,uint64_t entry_fp){
  ucontext_t *uc=context;
  struct fpsimd_context *fp=(struct fpsimd_context*)uc->uc_mcontext.__reserved;
  struct FrameReport *r=report;
  uint64_t sizes[]={sizeof(siginfo_t),sizeof(ucontext_t),sizeof(mcontext_t),sizeof(stack_t),sizeof(sigset_t),
    offsetof(ucontext_t,uc_stack),offsetof(ucontext_t,uc_sigmask),offsetof(ucontext_t,uc_mcontext),
    offsetof(mcontext_t,regs),offsetof(mcontext_t,sp),offsetof(mcontext_t,pc),offsetof(mcontext_t,pstate),
    offsetof(mcontext_t,__reserved),sizeof(*fp),offsetof(struct fpsimd_context,vregs),sizeof(struct _aarch64_ctx)};
  for(unsigned i=0;i<16;++i)r->layout[i]=sizes[i];
  r->signo=signo;r->info_signo=info->si_signo;r->info_errno=info->si_errno;r->info_code=info->si_code;
  r->mask=*(uint64_t*)&uc->uc_sigmask;r->alt_pointer=(uint64_t)uc->uc_stack.ss_sp;
  r->alt_flags=uc->uc_stack.ss_flags;r->alt_size=uc->uc_stack.ss_size;
  r->sp=uc->uc_mcontext.sp;r->pc=uc->uc_mcontext.pc;r->pstate=uc->uc_mcontext.pstate;r->fault=uc->uc_mcontext.fault_address;
  r->fpcr=fp->fpcr;r->fpsr=fp->fpsr;r->magic=fp->head.magic;r->record_size=fp->head.size;
  r->entry_sp=entry_sp;r->entry_fp=entry_fp;r->chain_fp=((uint64_t*)entry_fp)[0];r->chain_lr=((uint64_t*)entry_fp)[1];
  for(unsigned i=0;i<31;++i)r->gpr[i]=uc->uc_mcontext.regs[i];
  uint64_t *q=(uint64_t*)fp->vregs;
  for(unsigned i=0;i<64;++i)r->vectors[i]=q[i];
  if(r->mutate){
    uc->uc_mcontext.regs[19]=r->new_root;
    uc->uc_mcontext.sp-=16;uc->uc_mcontext.pc+=4;uc->uc_mcontext.pstate^=1ULL<<31;
    q[62]=r->new_root;q[63]=r->new_root+8;
    fp->fpcr^=1u<<22;fp->fpsr^=0x9f;
    *(uint64_t*)&uc->uc_sigmask^=0x20;uc->uc_stack.ss_flags^=1;
    info->si_errno=17;
  }
}

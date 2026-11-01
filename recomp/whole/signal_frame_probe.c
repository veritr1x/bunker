#define _GNU_SOURCE
#include <signal.h>
#include <stdint.h>
#include <stddef.h>
#include <unistd.h>
#include <sys/ucontext.h>
#include <asm/sigcontext.h>
static unsigned char alternate[65536] __attribute__((aligned(16)));
static unsigned mode;
extern void frame_handler(int,siginfo_t*,void*);
__attribute__((visibility("hidden")))
void frame_body(int signo,siginfo_t *info,void *context,uint64_t sp,uint64_t fp){
  ucontext_t *uc=context;
  struct fpsimd_context *f=(struct fpsimd_context*)uc->uc_mcontext.__reserved;
  struct _aarch64_ctx *end=(struct _aarch64_ctx*)((unsigned char*)f+f->head.size);
  uint64_t facts[]={
    !(sp&15),(uint64_t)info==sp,(uint64_t)uc==sp+128,fp==sp+4688,
    ((uint64_t*)fp)[0]==uc->uc_mcontext.regs[29],((uint64_t*)fp)[1]==uc->uc_mcontext.regs[30],
    (uint64_t)f==sp+592,f->head.magic,f->head.size,end->magic,end->size,
    signo==SIGUSR1&&info->si_signo==SIGUSR1,
    sigismember(&uc->uc_sigmask,SIGUSR2)==1,
    (uint64_t)uc->uc_stack.ss_sp==(uint64_t)alternate,uc->uc_stack.ss_size==sizeof(alternate),uc->uc_stack.ss_flags==0,
    mode?(sp>=(uint64_t)alternate&&sp<(uint64_t)(alternate+sizeof(alternate))):!(sp>=(uint64_t)alternate&&sp<(uint64_t)(alternate+sizeof(alternate))),
    fp+16==(mode?(uint64_t)(alternate+sizeof(alternate)):uc->uc_mcontext.sp),
    sizeof(siginfo_t),sizeof(ucontext_t),sizeof(mcontext_t),sizeof(stack_t),
    offsetof(ucontext_t,uc_stack),offsetof(ucontext_t,uc_sigmask),offsetof(ucontext_t,uc_mcontext),
    offsetof(mcontext_t,regs),offsetof(mcontext_t,sp),offsetof(mcontext_t,pc),offsetof(mcontext_t,pstate),
    offsetof(mcontext_t,__reserved),sizeof(*f),offsetof(struct fpsimd_context,vregs)
  };
  if(write(STDOUT_FILENO,facts,sizeof(facts))!=(ssize_t)sizeof(facts))_exit(3);
}
int main(void){
  stack_t stack={.ss_sp=alternate,.ss_size=sizeof(alternate)};
  if(sigaltstack(&stack,0))return 1;
  sigset_t mask;sigemptyset(&mask);sigaddset(&mask,SIGUSR2);if(sigprocmask(SIG_BLOCK,&mask,0))return 1;
  for(mode=0;mode<2;++mode){
    struct sigaction action={0};action.sa_sigaction=frame_handler;action.sa_flags=SA_SIGINFO|(mode?SA_ONSTACK:0);
    sigemptyset(&action.sa_mask);if(sigaction(SIGUSR1,&action,0)||raise(SIGUSR1))return 1;
  }
}

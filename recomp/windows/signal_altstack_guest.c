#include "signal_altstack_fixture.h"
#include <stddef.h>
#include <errno.h>
#include <signal.h>
#include <sys/ucontext.h>
#include <asm/sigcontext.h>
_Static_assert(sizeof(stack_t)==24&&_Alignof(stack_t)==8,"ARM64 stack_t layout");
_Static_assert(offsetof(stack_t,ss_sp)==0&&offsetof(stack_t,ss_flags)==8&&offsetof(stack_t,ss_size)==16,"ARM64 stack_t offsets");
_Static_assert(MINSIGSTKSZ==5120&&SIGSTKSZ==16384,"actual ARM64 NDK minima");
extern void TEST_alt_dispatch(void);
extern void TEST_alt_nested(void);
extern uint64_t TEST_alt_lease_guards(void);
static struct AltReport *report;
uint64_t alt_call(const stack_t *set,stack_t *old){errno=71;int result=sigaltstack(set,old);return((uint64_t)(uint32_t)errno<<32)|(uint32_t)result;}
static int unchanged(const unsigned char *p){for(unsigned i=0;i<24;++i)if(p[i]!=0xa5)return 0;return 1;}
static void nested_handler(int sig,siginfo_t *info,void *context){
  (void)sig;(void)info;int saved=errno;ucontext_t *uc=context;stack_t q,old,disable={0};
  report->nested_frame=(uint64_t)info;report->nested_saved_sp=uc->uc_mcontext.sp;report->nested_raw_flags=uc->uc_stack.ss_flags;
  __asm__ volatile("mov %0,sp":"=r"(report->nested_sp));
  sigaltstack(0,&q);report->nested_query_flags=q.ss_flags;
  for(unsigned i=0;i<24;++i)((unsigned char*)&old)[i]=0xa5;
  disable.ss_flags=4;report->nested_onstack_result=(uint32_t)sigaltstack(&disable,&old);report->nested_onstack_errno=errno;report->nested_old_unchanged=unchanged((unsigned char*)&old);
  ++report->nested_count;errno=saved;
}
static void outer_handler(int sig,siginfo_t *info,void *context){
  (void)sig;int saved=errno;ucontext_t *uc=context;stack_t q,old,disable={0};
  report->outer_frame=(uint64_t)info;report->outer_saved_sp=uc->uc_mcontext.sp;report->outer_raw_flags=uc->uc_stack.ss_flags;
  __asm__ volatile("mov %0,sp":"=r"(report->outer_sp));
  report->root=uc->uc_mcontext.regs[20];struct fpsimd_context *fp=(struct fpsimd_context*)uc->uc_mcontext.__reserved;uint64_t *v=(uint64_t*)fp->vregs;report->vector_root[0]=v[62];report->vector_root[1]=v[63];
  sigaltstack(0,&q);report->outer_query_flags=q.ss_flags;report->query_pointer=(uint64_t)q.ss_sp;report->query_size=q.ss_size;
  report->lease_guards=TEST_alt_lease_guards();
  if(report->mode==1){
    stack_t replacement={0};replacement.ss_sp=(void*)report->replacement;replacement.ss_size=report->replacement_size;
    report->changed_result=(uint32_t)sigaltstack(&replacement,0);sigaltstack(0,&q);report->changed_query=(uint64_t)q.ss_sp;
  }else{
    for(unsigned i=0;i<24;++i)((unsigned char*)&old)[i]=0xa5;
    disable.ss_flags=SS_DISABLE;report->onstack_result=(uint32_t)sigaltstack(&disable,&old);report->onstack_errno=errno;report->onstack_old_unchanged=unchanged((unsigned char*)&old);
    TEST_alt_nested();
  }
  errno=saved;
}
int alt_handlers(struct AltReport *p,int use_onstack){
  report=p;struct sigaction a={0};a.sa_sigaction=outer_handler;a.sa_flags=SA_SIGINFO|(use_onstack?SA_ONSTACK:0);sigemptyset(&a.sa_mask);if(sigaction(30,&a,0))return -1;
  a.sa_sigaction=nested_handler;a.sa_flags=SA_SIGINFO;return sigaction(24,&a,0);
}
void alt_entry(void){TEST_alt_dispatch();}
void alt_return_boundary(void){}

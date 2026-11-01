#include "signal_delivery_fixture.h"
#include <errno.h>
#include <pthread.h>
#include <semaphore.h>
#include <signal.h>
#include <sys/ucontext.h>
#include <asm/sigcontext.h>
static struct DeliveryReport *report;
static void restart_handler(int signal){if(signal==24)++report->restarts;}
static void stop_handler(int signal,siginfo_t *info,void *context){
  ucontext_t *uc=context;
  struct fpsimd_context *fp=(struct fpsimd_context*)uc->uc_mcontext.__reserved;
  const int saved=errno;
  if(signal!=30||info->si_signo!=30)return;
  ++report->stops;report->error_before=saved;
  report->root=uc->uc_mcontext.regs[20];report->counter=uc->uc_mcontext.regs[21];
  uint64_t *vectors=(uint64_t*)fp->vregs;
  report->vector_root[0]=vectors[62];report->vector_root[1]=vectors[63];
  report->interrupted_sp=uc->uc_mcontext.sp;report->interrupted_pc=uc->uc_mcontext.pc;
  report->frame=(uint64_t)info;
  __asm__ volatile("mov %0,sp":"=r"(report->handler_sp));
  __asm__ volatile("mov %0,x29":"=r"(report->handler_fp));
  __asm__ volatile("mrs %0,tpidr_el0":"=r"(report->tls));
  report->worker_token=(uint64_t)pthread_self();
  sem_post((sem_t*)report->acknowledgment);
  sigset_t mask;sigfillset(&mask);sigdelset(&mask,24);
  // Always consume a restart, including one queued before this atomic wait.
  do{sigsuspend(&mask);}while(report->world_stopped);
  report->error_after=errno;
  sem_post((sem_t*)report->acknowledgment);
  errno=saved;
}
int delivery_install(struct DeliveryReport *value){
  report=value;struct sigaction action={0};
  action.sa_sigaction=stop_handler;action.sa_flags=SA_SIGINFO|SA_RESTART;
  sigfillset(&action.sa_mask);
  if(sigaction(30,&action,0))return -1;
  action.sa_handler=restart_handler;action.sa_flags=SA_RESTART;
  return sigaction(24,&action,0);
}
void delivery_return_boundary(void){}

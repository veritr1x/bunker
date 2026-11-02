#include "signal_sender_fixture.h"
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stddef.h>
#include <unistd.h>
static struct SenderReport *report;
extern void test_sender_checkpoint(void);
_Static_assert(sizeof(siginfo_t)==128 && _Alignof(siginfo_t)==8,"NDK siginfo size/alignment");
_Static_assert(offsetof(siginfo_t,si_signo)==0 && offsetof(siginfo_t,si_errno)==4 && offsetof(siginfo_t,si_code)==8,"NDK prefix");
_Static_assert(offsetof(siginfo_t,si_pid)==16 && offsetof(siginfo_t,si_uid)==20 && SI_TKILL==-6,"NDK sender");
_Static_assert(sizeof(struct SenderReport)==176,"NDK report");
static void handler(int number,siginfo_t *info,void *context){
  (void)context;
  report->handler_error=errno;report->signal_number=number;
  report->process_id=getpid();report->real_uid=getuid();report->token=pthread_self();
  __asm__ volatile("mov %0,sp":"=r"(report->handler_sp));
  __asm__ volatile("mov %0,x29":"=r"(report->handler_fp));
  for(unsigned i=0;i<128;++i)report->info[i]=((const unsigned char*)info)[i];
  ++report->calls;
}
__attribute__((visibility("default"))) int sender_configure(struct SenderReport *value){
  report=value;struct sigaction action={0};action.sa_sigaction=handler;action.sa_flags=SA_SIGINFO;
  sigemptyset(&action.sa_mask);return sigaction(30,&action,0);
}
__attribute__((visibility("default"))) int sender_invoke(uint64_t token,int32_t number,uint32_t indirect){
  const int saved=errno;int result;
  if(indirect){int(*volatile call)(pthread_t,int)=pthread_kill;result=call((pthread_t)token,number);}
  else result=pthread_kill((pthread_t)token,number);
  if(errno!=saved)report->caller_error_changed=1;
  return result;
}
__attribute__((visibility("default"))) int sender_checkpoint(void){test_sender_checkpoint();return 0;}
__attribute__((visibility("default"))) void sender_return_boundary(void){}

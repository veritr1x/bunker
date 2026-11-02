#include "signal_sender_fixture.h"
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
__thread volatile unsigned char reference_tls_alignment[64] __attribute__((aligned(64)));
void test_sender_checkpoint(void){}
int main(void){
  reference_tls_alignment[0]=1;
  struct SenderReport r={0};if(sender_configure(&r))return 1;
  const int32_t pid=getpid();const uint32_t uid=getuid();
  for(unsigned mode=0;mode<2;++mode){
    errno=731;if(sender_invoke(pthread_self(),30,mode))return 2;
    if(r.calls!=mode+1 || r.handler_error!=731 || r.caller_error_changed)return 3;
    siginfo_t copied;memcpy(&copied,r.info,sizeof(copied));siginfo_t *info=&copied;
    if(info->si_signo!=30 || info->si_errno || info->si_code!=SI_TKILL || info->si_pid!=pid || info->si_uid!=uid)return 4;
    printf("REFERENCE mode=%u count=%u pid=%d uid=%u code=%d raw=",mode,r.calls,pid,uid,info->si_code);
    for(unsigned i=0;i<128;++i)printf("%02x",r.info[i]);putchar('\n');
  }
  puts("SIGNAL-SENDER-ARM64-SUCCESS real-Bionic-process-identity");return 0;
}

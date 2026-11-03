#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
extern int guest_sleep(uint64_t,int,int*);
extern volatile uint32_t sleep_handlers;
extern void sleep_handler(int);
// Real native TLS with the ARM64 Bionic executable TLS alignment requirement.
// This reference is compiled -fno-emulated-tls; no host/provider TLS is faked.
static _Thread_local volatile unsigned reference_tls __attribute__((aligned(64)));
static uint64_t now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return(uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
struct send_job{pthread_t target;int done;};
static void*sender(void*argument){struct send_job*j=argument;while(!__atomic_load_n(&j->done,__ATOMIC_ACQUIRE)){struct timespec t={0,10000000};while(nanosleep(&t,&t)&&errno==EINTR){}if(!__atomic_load_n(&j->done,__ATOMIC_ACQUIRE))pthread_kill(j->target,SIGUSR1);}return 0;}
static void watchdog(int signal){(void)signal;const char text[]="usleep component reference watchdog\n";write(2,text,sizeof(text)-1);_exit(98);}
int main(void){
 reference_tls=17;if(reference_tls!=17)return 1;
 signal(SIGALRM,watchdog);alarm(30);
 unsigned records=0;
 for(int mode=0;mode<2;++mode){uint64_t durations[]={0,1,3000,1000000,1000001,UINT64_C(0x100000001)};
  for(unsigned i=0;i<sizeof(durations)/sizeof(*durations);++i){int e=0;uint64_t start=now();int r=guest_sleep(durations[i],mode,&e);uint64_t elapsed=now()-start;if(r||e!=731||elapsed<(uint64_t)(uint32_t)durations[i]*1000)return 2;printf("normal mode=%d low32=%u return=0 errno=731 elapsed=%llu\n",mode,(uint32_t)durations[i],(unsigned long long)elapsed);++records;}
  for(int restart=0;restart<2;++restart){struct sigaction a;memset(&a,0,sizeof(a));a.sa_handler=sleep_handler;a.sa_flags=restart?SA_RESTART:0;sigemptyset(&a.sa_mask);if(sigaction(SIGUSR1,&a,0))return 3;pthread_t child;struct send_job job={pthread_self(),0};sleep_handlers=0;int e=0;if(pthread_create(&child,0,sender,&job))return 4;int r=guest_sleep(UINT64_C(0x1ffffffff),mode,&e);__atomic_store_n(&job.done,1,__ATOMIC_RELEASE);pthread_join(child,0);if(r!=-1||e!=EINTR||sleep_handlers<1)return 5;printf("interrupt mode=%d restart=%d low32=4294967295 return=-1 errno=4 handlers=positive observed=%u\n",mode,restart,sleep_handlers);++records;}
 }
 printf("USLEEP-ARM64-SUCCESS records=%u\n",records);return 0;
}

#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
extern int guest_nanosleep(const struct timespec*,struct timespec*,int,int*);
extern void nanosleep_handler(int);
extern volatile uint32_t nanosleep_handlers;
extern volatile uintptr_t nanosleep_remaining_probe;
extern volatile int nanosleep_delay_handler;
extern volatile int64_t nanosleep_handler_seconds,nanosleep_handler_nanoseconds;
static _Thread_local volatile unsigned reference_tls __attribute__((aligned(64)));
static uint64_t now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return(uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
void nanosleep_fixture_delay(void){struct timespec t={0,60000000};while(nanosleep(&t,&t)&&errno==EINTR){}}
struct send_job{pthread_t target;int done,once;};
static void*sender(void*argument){struct send_job*j=argument;while(!__atomic_load_n(&j->done,__ATOMIC_ACQUIRE)){struct timespec t={0,10000000};while(nanosleep(&t,&t)&&errno==EINTR){}if(!__atomic_load_n(&j->done,__ATOMIC_ACQUIRE))pthread_kill(j->target,SIGUSR1);if(j->once)break;}return 0;}
static void watchdog(int signal){(void)signal;const char text[]="nanosleep component reference watchdog\n";write(2,text,sizeof(text)-1);_exit(98);}
static void reset(struct timespec*probe,int delay){nanosleep_handlers=0;nanosleep_remaining_probe=(uintptr_t)probe;nanosleep_delay_handler=delay;nanosleep_handler_seconds=-9;nanosleep_handler_nanoseconds=-9;}
int main(void){reference_tls=17;if(reference_tls!=17)return 1;signal(SIGALRM,watchdog);alarm(30);unsigned records=0;
 for(int mode=0;mode<2;++mode){
  const struct timespec durations[]={{0,0},{0,1},{0,1000},{0,2000000},{1,1}};
  for(unsigned i=0;i<sizeof(durations)/sizeof(*durations);++i){struct timespec rem={77,88};int e=0;uint64_t start=now();int r=guest_nanosleep(&durations[i],&rem,mode,&e);uint64_t elapsed=now()-start;if(r||e!=731||elapsed<(uint64_t)durations[i].tv_sec*1000000000+durations[i].tv_nsec||rem.tv_sec!=77||rem.tv_nsec!=88)return 2;printf("record normal mode=%d case=%u return=0 errno=731\n",mode,i);++records;}
  const struct timespec invalid[]={{-1,0},{0,-1},{0,1000000000}};
  // QEMU's syscall adapter copies a host remainder on EINVAL. Its contents on
  // that error are not the ARM reference oracle. Host tests separately require
  // no invalid-request output mutation from the retained Android kernel path.
  for(unsigned i=0;i<3;++i){struct timespec rem={77,88};int e=0;if(guest_nanosleep(&invalid[i],&rem,mode,&e)!=-1||e!=EINVAL)return 3;printf("record invalid mode=%d case=%u return=-1 errno=22\n",mode,i);++records;}
#ifdef NANOSLEEP_REFERENCE_NATIVE
  for(unsigned i=0;i<2;++i){int e=0;if(guest_nanosleep((const struct timespec*)(uintptr_t)i,0,mode,&e)!=-1||e!=EFAULT)return 4;printf("record fault mode=%d case=%u return=-1 errno=14\n",mode,i);++records;}
#endif
  for(int kind=0;kind<5;++kind){
#ifndef NANOSLEEP_REFERENCE_NATIVE
   // QEMU8.2.2 ignores target request/remainder copy errors. Its six EFAULT
   // cases are excluded, never printed as expected ARM successes. A separate
   // native Linux reference and translated host tests exercise those cases.
   if(kind==3)continue;
#endif
   struct sigaction a;memset(&a,0,sizeof(a));a.sa_handler=nanosleep_handler;a.sa_flags=kind==1?SA_RESTART:0;sigemptyset(&a.sa_mask);if(sigaction(SIGUSR1,&a,0))return 5;
   struct timespec request={0,200000000},rem={77,88};if(kind==2)request.tv_sec=INT64_MAX;
   struct timespec*output=kind==2?0:kind==3?(struct timespec*)(uintptr_t)1:kind==4?&request:&rem;
   reset((kind==2||kind==3)?0:output,kind==4);struct send_job job={pthread_self(),0,kind==4};pthread_t child;if(pthread_create(&child,0,sender,&job))return 6;
   int e=0;int r=guest_nanosleep(&request,output,mode,&e);__atomic_store_n(&job.done,1,__ATOMIC_RELEASE);pthread_join(child,0);
   int expected=kind==3?EFAULT:EINTR;if(r!=-1||e!=expected||nanosleep_handlers<1)return 7;
   if(output&&(kind!=3)){if(output->tv_sec!=0||output->tv_nsec<=0||output->tv_nsec>=200000000||nanosleep_handler_seconds!=output->tv_sec||nanosleep_handler_nanoseconds!=output->tv_nsec)return 8;}
   printf("record interrupt mode=%d kind=%d return=-1 errno=%d handlers=positive\n",mode,kind,expected);++records;
  }
 }
#ifdef NANOSLEEP_REFERENCE_NATIVE
 printf("NANOSLEEP-NATIVE-LINUX-SUCCESS records=%u\n",records);
#else
 printf("NANOSLEEP-ARM64-SUCCESS records=%u\n",records);
#endif
 return 0;
}

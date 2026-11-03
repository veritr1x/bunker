#include "futex_fixture.h"
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
static _Thread_local volatile uint32_t native_tls __attribute__((aligned(64)));
static void check(int okay,const char*message){if(!okay){fprintf(stderr,"FUTEX-REFERENCE-FAIL %s errno=%d\n",message,errno);exit(20);}}
static uint64_t now(void){struct timespec t;check(!clock_gettime(CLOCK_MONOTONIC,&t),"clock");return(uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void pause_short(void){struct timespec t={0,1000000};while(nanosleep(&t,&t)&&errno==EINTR){}}
static FutexCall args(uintptr_t address,uint64_t operation,uint64_t value,unsigned mode){FutexCall a={98,address,operation,value,(operation&0xffffffff)==0x81?UINT64_MAX:0,UINT64_MAX,UINT64_MAX,mode};return a;}
static int64_t invoke(uintptr_t address,uint64_t operation,uint64_t value,unsigned mode,int*error){FutexCall a=args(address,operation,value,mode);return guest_futex(&a,error);}
static void watchdog(int signal){(void)signal;const char text[]="futex reference watchdog\n";write(2,text,sizeof(text)-1);_exit(98);}
struct job{FutexCall args;int error;int64_t result;_Atomic unsigned ready,done;};
static void*waiter(void*argument){struct job*j=argument;native_tls=17;check(native_tls==17,"real workerTLS64");atomic_store(&j->ready,1);j->result=guest_futex(&j->args,&j->error);atomic_store(&j->done,1);return 0;}
static void start(struct job*j,pthread_t*t,uintptr_t address,unsigned mode){memset(j,0,sizeof(*j));atomic_init(&j->ready,0);atomic_init(&j->done,0);j->args=args(address,0x80,0,mode);check(!pthread_create(t,0,waiter,j),"create actual waiter");}
static void ready(struct job*j){uint64_t limit=now()+UINT64_C(5000000000);while(!atomic_load(&j->ready)){check(now()<limit,"waiter starts");pause_short();}}
static int64_t positive_wake(uintptr_t address,uint64_t count,unsigned mode){uint64_t limit=now()+UINT64_C(5000000000);for(;;){int error=0;int64_t r=invoke(address,0x81,count,mode,&error);check(r>=0&&error==731,"real wake result/errno");if(r)return r;check(now()<limit,"bounded real wake finds enrolled waiter");pause_short();}}
struct sender_job{pthread_t target;uintptr_t word;int wake_after_handler;_Atomic int done;int64_t positive;};
static void*sender(void*argument){struct sender_job*j=argument;for(unsigned i=0;i<20&&!atomic_load(&j->done);++i)pause_short();while(!atomic_load(&j->done)){check(!pthread_kill(j->target,SIGUSR1),"real caught signal");if(j->wake_after_handler&&__atomic_load_n(&futex_handler_count,__ATOMIC_ACQUIRE)){int error=0;int64_t r=invoke(j->word,0x81,1,1,&error);check(r>=0&&r<=1&&error==731,"real post-handler wake");if(r){j->positive=r;return 0;}}pause_short();}return 0;}
int main(void){
 setvbuf(stdout,0,_IOLBF,0);native_tls=7;check(native_tls==7,"real mainTLS64");signal(SIGALRM,watchdog);alarm(40);struct utsname u;check(!uname(&u),"actual reference kernel");printf("REFERENCE-KERNEL %s %s\n",u.sysname,u.release);
 _Alignas(4)uint32_t word=0;void*guard=mmap(0,4096,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);check(guard!=MAP_FAILED,"guard mapping");void*retired=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);check(retired!=MAP_FAILED&&!munmap(retired,4096),"actual unmapped key");unsigned records=0;
 for(unsigned mode=0;mode<2;++mode){
  const char*names[]={"mismatch","align-before-range","wait-read-fault","wake-null-poison","wake-guard-zero","wake-guard-negative","wake-unmapped","wake-outside-user"};
  uintptr_t addresses[]={(uintptr_t)&word,UINT64_MAX,(uintptr_t)guard,0,(uintptr_t)guard,(uintptr_t)guard,(uintptr_t)retired,UINT64_C(0x00fffffffffffffc)};
  uint64_t ops[]={0x80,0x80,0x80,UINT64_C(0x100000081),0x81,0x81,0x81,0x81};uint64_t values[]={UINT64_C(0x100000001),0,0,UINT64_C(0x100000001),0,UINT64_C(0x1ffffffff),1,1};int64_t expected[]={-1,-1,-1,0,0,0,0,-1};int errors[]={11,22,14,731,731,731,731,14};
  for(unsigned i=0;i<8;++i){int error=0;FutexCall call=args(addresses[i],ops[i],values[i],mode);if(i==0)call.nr=UINT64_C(0x100000062);if(i==3)call.nr=UINT64_C(0xffffffff00000062);int64_t r=guest_futex(&call,&error);check(r==expected[i]&&error==errors[i],names[i]);printf("PROBE mode=%u case=%s result=%lld errno=%d\n",mode,names[i],(long long)r,error);++records;}
 }
 // No ready flag is called kernel enrollment: positive kernel WAKE counts are
 // observed with a bounded retry, including the real zero/negative quirk.
 {
  struct job j[3];pthread_t t[3];for(unsigned i=0;i<3;++i)start(j+i,t+i,(uintptr_t)&word,i&1);for(unsigned i=0;i<3;++i)ready(j+i);unsigned total=0;uint64_t limit=now()+UINT64_C(5000000000);
  while(total<3){int error=0;int64_t r=invoke((uintptr_t)&word,0x81,2,1,&error);check(r>=0&&r<=2&&error==731,"wake at most requested2");total+=(unsigned)r;check(total<=3&&now()<limit,"exact wake accounting");if(!r)pause_short();}
  for(unsigned i=0;i<3;++i){check(!pthread_join(t[i],0)&&j[i].result==0&&j[i].error==731,"each actual selected waiter returns0");}printf("GROUP requested2 total3 returns3\n");++records;
 }
 {
  struct job j[2];pthread_t t[2];for(unsigned i=0;i<2;++i)start(j+i,t+i,(uintptr_t)&word,i);for(unsigned i=0;i<2;++i)ready(j+i);check(positive_wake((uintptr_t)&word,0,0)==1,"zero count selects one");check(positive_wake((uintptr_t)&word,UINT64_C(0x1ffffffff),1)==1,"signed negative low32 selects one");for(unsigned i=0;i<2;++i)check(!pthread_join(t[i],0)&&j[i].result==0&&j[i].error==731,"zero/negative selected returns");printf("GROUP zero1 negative1 returns2\n");++records;
 }
 {
  int error=0;check(invoke((uintptr_t)&word,0x81,1,0,&error)==0,"wake before wait stores no credits");struct job j;pthread_t t;start(&j,&t,(uintptr_t)&word,1);ready(&j);for(unsigned i=0;i<20;++i)pause_short();check(!atomic_load(&j.done),"no pre-wake credit return");check(positive_wake((uintptr_t)&word,1,0)==1,"later actual wake required");check(!pthread_join(t,0)&&j.result==0&&j.error==731,"later wake return");printf("GROUP no-credit later-wake1\n");++records;
 }
 for(unsigned i=0;i<64;++i){__atomic_store_n(&word,0,__ATOMIC_RELEASE);struct job j;pthread_t t;start(&j,&t,(uintptr_t)&word,i&1);__atomic_store_n(&word,1,__ATOMIC_RELEASE);int error=0;int64_t w=invoke((uintptr_t)&word,0x81,1,(i+1)&1,&error);check(!pthread_join(t,0),"race join");check(error==731&&((w==1&&j.result==0&&j.error==731)||(w==0&&j.result==-1&&j.error==11)),"compare/enroll wake race has only kernel-permitted outcomes");printf("RACE %u result=%lld errno=%d wake=%lld\n",i,(long long)j.result,j.error,(long long)w);}printf("RACES count=64 permitted-wake-or-EAGAIN\n");++records;
 for(unsigned scenario=0;scenario<3;++scenario){int restart=scenario!=0,change=scenario!=2;int valid=0;for(unsigned attempt=0;attempt<8&&!valid;++attempt){__atomic_store_n(&word,0,__ATOMIC_RELEASE);futex_handler_word=(uintptr_t)&word;futex_handler_mode=(uint32_t)change;futex_handler_count=0;futex_handler_wake=-99;struct sigaction action;memset(&action,0,sizeof(action));action.sa_handler=futex_handler;action.sa_flags=restart?SA_RESTART:0;sigemptyset(&action.sa_mask);check(!sigaction(SIGUSR1,&action,0),"install actual caught handler");struct sender_job job={pthread_self(),(uintptr_t)&word,!change,0,0};pthread_t child;check(!pthread_create(&child,0,sender,&job),"real sender");int error=0;int64_t result=invoke((uintptr_t)&word,0x80,0,scenario&1,&error);atomic_store(&job.done,1);check(!pthread_join(child,0),"sender joined before main exits");if(!restart&&result==-1&&error==11)continue;check(__atomic_load_n(&futex_handler_count,__ATOMIC_ACQUIRE)>=1&&futex_handler_wake==0,"handler sees withdrawn wait ticket/no credit");check((!restart&&result==-1&&error==4)||(restart&&change&&result==-1&&error==11)||(restart&&!change&&result==0&&error==901&&job.positive==1),"caught signal/restart original expectation");printf("SIGNAL restart=%d change=%d result=%lld errno=%d nested-wake=0\n",restart,change,(long long)result,error);++records;valid=1;}check(valid,"actual nonrestart EINTR observed within bounded attempts");}
 check(!munmap(guard,4096),"guard cleanup");printf("FUTEX-ARM64-SUCCESS records=%u\n",records);return 0;
}

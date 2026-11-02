#define _POSIX_C_SOURCE 200809L
#include "pthread_wait_fixture.h"
#include <pthread.h>
#include <signal.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
extern uint64_t wait_setup(struct PthreadWaitReport *),wait_launch(struct PthreadWaitReport *),wait_join(struct PthreadWaitReport *),wait_cleanup(struct PthreadWaitReport *);
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
static unsigned entered,finished;
static volatile sig_atomic_t handled;
static void check(int yes){if(!yes)abort();}
static void handler(int number){if(number==SIGUSR1)++handled;}
void wait_probe(struct PthreadWaitReport *r,unsigned phase){(void)r;check(!pthread_mutex_lock(&lock));if(phase==1)++entered;else ++finished;check(!pthread_cond_broadcast(&changed));check(!pthread_mutex_unlock(&lock));}
static void delay(long ms){struct timespec t={ms/1000,ms%1000*1000000};while(nanosleep(&t,&t)&&errno==EINTR){}}
int main(void){
  struct sigaction action={0};action.sa_handler=handler;sigemptyset(&action.sa_mask);check(!sigaction(SIGUSR1,&action,0));
  for(unsigned timed=0;timed<2;++timed){
    struct PthreadWaitReport r={0};r.timed=timed;
    struct timespec now;check(!clock_gettime(CLOCK_MONOTONIC,&now));r.seconds=now.tv_sec;r.nanoseconds=now.tv_nsec+250000000;
    if(r.nanoseconds>=1000000000){++r.seconds;r.nanoseconds-=1000000000;}
    check(!wait_setup(&r)&&!wait_launch(&r));
    check(!pthread_mutex_lock(&lock));while(entered<=timed)check(!pthread_cond_wait(&changed,&lock));check(!pthread_mutex_unlock(&lock));
    check(!pthread_mutex_lock((void *)r.mutex));check(!pthread_mutex_unlock((void *)r.mutex));
    check(!pthread_kill((pthread_t)r.thread,SIGUSR1));delay(30);
    check(!pthread_mutex_lock(&lock));check(finished==timed);check(!pthread_mutex_unlock(&lock));
    if(!timed){check(!pthread_mutex_lock((void *)r.mutex));r.permits=1;check(!pthread_cond_signal((void *)r.condition));check(!pthread_mutex_unlock((void *)r.mutex));}
    check(wait_join(&r)==0x600d&&!r.errors&&r.returns>=1&&r.result==(timed?ETIMEDOUT:0)&&!wait_cleanup(&r));
    printf("ARM64 native cond scenario=%u result=%llu owns=1 handled=%d\n",timed,(unsigned long long)r.result,(int)handled);
  }
  check(handled==2);puts("ARM64 native pthread reference passed");return 0;
}

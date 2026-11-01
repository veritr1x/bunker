#define _GNU_SOURCE
#include <signal.h>
#include <pthread.h>
#include <semaphore.h>
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>
extern int policy_guest(uint64_t,int64_t*);
static sem_t semaphore;
static pthread_t target;
static volatile sig_atomic_t calls;
static void handler(int signal){(void)signal;++calls;}
static void *sender(void *argument){
  (void)argument;struct timespec interval={0,20000000};nanosleep(&interval,0);pthread_kill(target,30);nanosleep(&interval,0);sem_post(&semaphore);return 0;
}
int main(void){
  int64_t out[64]={0};int count=policy_guest((uint64_t)pthread_self(),out);fwrite(&count,4,1,stdout);fwrite(out,8,count,stdout);
  target=pthread_self();
  for(unsigned timed=0;timed<2;++timed)for(unsigned restart=0;restart<2;++restart){
    calls=0;struct sigaction action={0};action.sa_handler=handler;action.sa_flags=restart?SA_RESTART:0;sigemptyset(&action.sa_mask);sigaction(30,&action,0);
    sem_init(&semaphore,0,0);pthread_t worker;pthread_create(&worker,0,sender,0);
    struct timespec deadline;clock_gettime(CLOCK_REALTIME,&deadline);++deadline.tv_sec;
    errno=0;int result=timed?sem_timedwait(&semaphore,&deadline):sem_wait(&semaphore);int error=errno;
    pthread_join(worker,0);int value;sem_getvalue(&semaphore,&value);
    int64_t fact[]={timed,restart,result,result?error:0,calls,value};fwrite(fact,8,6,stdout);sem_destroy(&semaphore);
  }
}

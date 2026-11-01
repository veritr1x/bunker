#include <signal.h>
#include <pthread.h>
#include <semaphore.h>
#include <stdint.h>
#include <errno.h>
#include <limits.h>
static volatile sig_atomic_t handled,handler_blocked;
void policy_handler(int signal){sigset_t mask;pthread_sigmask(SIG_SETMASK,0,&mask);handler_blocked=sigismember(&mask,signal);++handled;}
int policy_guest(uint64_t token,int64_t *out){
  unsigned n=0;out[n++]=sizeof(struct sigaction);out[n++]=sizeof(sigset_t);out[n++]=sizeof(sem_t);
  handled=handler_blocked=0;
  struct sigaction action={0},old_action;action.sa_handler=policy_handler;sigemptyset(&action.sa_mask);
  out[n++]=sigaction(30,&action,&old_action);
  sigset_t blocked,old,current,pending;sigemptyset(&blocked);sigaddset(&blocked,30);
  out[n++]=pthread_sigmask(SIG_BLOCK,&blocked,&old);
  out[n++]=pthread_kill((pthread_t)token,30);out[n++]=pthread_kill((pthread_t)token,30);
  sigpending(&pending);out[n++]=sigismember(&pending,30);
  errno=0;out[n++]=sigsuspend(&old);out[n++]=errno;
  out[n++]=handled;out[n++]=handler_blocked;
  pthread_sigmask(99,0,&current);out[n++]=sigismember(&current,30);
  sigpending(&pending);out[n++]=sigismember(&pending,30);
  pthread_sigmask(SIG_SETMASK,&old,0);
  action.sa_handler=SIG_IGN;out[n++]=sigaction(30,&action,0);out[n++]=pthread_kill((pthread_t)token,30);
  sigpending(&pending);out[n++]=sigismember(&pending,30);out[n++]=handled;
  sigaction(30,&old_action,0);
  sem_t semaphore;struct timespec bad={0,1000000000},past={0,0};
  out[n++]=sem_init(&semaphore,0,1);errno=0;out[n++]=sem_timedwait(&semaphore,&bad);out[n++]=errno;
  // glibc's invalid-nsec fast path differs from Android13. Drain any token
  // left by that reference so later common API records remain independent.
  while(sem_trywait(&semaphore)==0){}
  errno=0;out[n++]=sem_timedwait(&semaphore,&bad);out[n++]=errno;
  errno=0;out[n++]=sem_timedwait(&semaphore,&past);out[n++]=errno;
  errno=0;out[n++]=sem_trywait(&semaphore);out[n++]=errno;
  out[n++]=sem_post(&semaphore);int value=0;sem_getvalue(&semaphore,&value);out[n++]=value;
  out[n++]=sem_wait(&semaphore);out[n++]=sem_destroy(&semaphore);
  out[n++]=sem_init(&semaphore,0,SEM_VALUE_MAX);errno=0;out[n++]=sem_post(&semaphore);out[n++]=errno;
  out[n++]=sem_destroy(&semaphore);return n;
}

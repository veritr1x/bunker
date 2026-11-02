// This exact NDK object is linked into the ARM64 reference and lifted for Win.
#include "pthread_wait_fixture.h"
#include <pthread.h>
#include <time.h>
#include <errno.h>
extern void wait_probe(struct PthreadWaitReport *,unsigned);
static void *wait_worker(void *value){
  struct PthreadWaitReport *r=value;
  pthread_mutex_t *m=(void *)r->mutex;pthread_cond_t *c=(void *)r->condition;
  if(pthread_mutex_lock(m)){++r->errors;return (void *)1;}
  r->token=(uintptr_t)pthread_self();wait_probe(r,1);
  struct timespec deadline={r->seconds,r->nanoseconds};int result=0;
  while(!r->permits){
    result=r->timed?pthread_cond_timedwait(c,m,&deadline):pthread_cond_wait(c,m);
    ++r->returns;if(result)break;
  }
  r->result=(uint32_t)result;
  if(pthread_mutex_trylock(m)!=EBUSY)++r->errors;
  wait_probe(r,2);
  if(pthread_mutex_unlock(m))++r->errors;
  return (void *)(uintptr_t)0x600d;
}
uint64_t wait_setup(struct PthreadWaitReport *r){
  pthread_condattr_t attr;
  if(pthread_mutex_init((void *)r->mutex,0)||pthread_condattr_init(&attr))return 1;
  if(pthread_condattr_setclock(&attr,CLOCK_MONOTONIC)||pthread_cond_init((void *)r->condition,&attr)||pthread_condattr_destroy(&attr))return 2;
  return 0;
}
uint64_t wait_launch(struct PthreadWaitReport *r){return pthread_create((pthread_t *)&r->thread,0,wait_worker,r);}
uint64_t wait_join(struct PthreadWaitReport *r){void *result=0;return pthread_join((pthread_t)r->thread,&result)?1:(uintptr_t)result;}
uint64_t wait_cleanup(struct PthreadWaitReport *r){return pthread_cond_destroy((void *)r->condition)||pthread_mutex_destroy((void *)r->mutex);}

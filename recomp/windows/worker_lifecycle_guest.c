// Actual Android NDK pthread/signal/setjmp declarations and guest callbacks.
#include "worker_lifecycle_fixture.h"
#include <pthread.h>
#include <signal.h>
#include <setjmp.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdint.h>
_Static_assert(sizeof(jmp_buf)==256,"NDK jmp_buf size");
extern void lifecycle_probe(struct WorkerLifecycleReport *,unsigned,void *);
static pthread_key_t repeat_key,free_key;
static pthread_once_t once=PTHREAD_ONCE_INIT;
static unsigned retry_count;
static void repeat(void *value){
  struct WorkerLifecycleReport *r=value;++r->destructors;
  lifecycle_probe(r,3,0);
  // A fifth value must be discarded after exactly four destructor passes.
  if(pthread_setspecific(repeat_key,r))++r->errors;
}
static void exit_once(void){
  struct WorkerLifecycleReport *r=pthread_getspecific(repeat_key);
  lifecycle_probe(r,2,(void *)(uintptr_t)r->environment);
  pthread_exit((void *)0x7012);
}
static void successful_once(void){++retry_count;}
void *lifecycle_worker_entry(void *value){
  struct WorkerLifecycleReport *r=value;pthread_attr_t attr;void *base=0;size_t size=0;sigset_t mask;
  r->token=(uintptr_t)pthread_self();r->native_tid=gettid();
  if(pthread_getattr_np(pthread_self(),&attr)||pthread_attr_getstack(&attr,&base,&size)||pthread_attr_destroy(&attr))++r->errors;
  r->stack_low=(uintptr_t)base;r->stack_size=size;
  __asm__("mrs %0,tpidr_el0":"=r"(r->tls));
  if(pthread_sigmask(SIG_SETMASK,0,&mask))++r->errors;r->mask=*(uint64_t *)&mask;
  jmp_buf env;r->environment=(uintptr_t)&env;lifecycle_probe(r,1,&env);
  if(setjmp(env))++r->errors;
  void *allocation=malloc(64);r->allocation=(uintptr_t)allocation;
  if(!allocation||pthread_setspecific(free_key,allocation)||pthread_setspecific(repeat_key,r))++r->errors;
  if(r->mode==3){
    sigemptyset(&mask);sigaddset(&mask,SIGTERM);
    if(pthread_sigmask(SIG_SETMASK,&mask,0)||!r->child||pthread_create((pthread_t *)&r->child->thread,0,lifecycle_worker_entry,r->child))++r->errors;
    else{void *result=0;if(pthread_join((pthread_t)r->child->thread,&result)||result!=(void *)0x7010)++r->errors;}
  }
  if(r->mode==2){pthread_once(&once,exit_once);++r->errors;}
  lifecycle_probe(r,2,&env);
  if(r->mode==1)pthread_exit((void *)0x7011);
  return (void *)(uintptr_t)(0x7010+r->mode);
}
uint64_t lifecycle_setup(void){return pthread_key_create(&repeat_key,repeat)||pthread_key_create(&free_key,free);}
uint64_t lifecycle_create(struct WorkerLifecycleReport *r){
  pthread_attr_t attr;if(pthread_attr_init(&attr)||pthread_attr_setstacksize(&attr,65536))return 1;
  if(r->mode==4&&pthread_attr_setdetachstate(&attr,PTHREAD_CREATE_DETACHED))return 2;
  int result=pthread_create((pthread_t *)&r->thread,&attr,lifecycle_worker_entry,r);pthread_attr_destroy(&attr);return result;
}
uint64_t lifecycle_join(struct WorkerLifecycleReport *r){void *value=0;return pthread_join((pthread_t)r->thread,&value)?0:(uintptr_t)value;}
uint64_t lifecycle_retry_once(void){return pthread_once(&once,successful_once)?0:retry_count;}
uint64_t lifecycle_cleanup(void){return pthread_key_delete(repeat_key)||pthread_key_delete(free_key);}

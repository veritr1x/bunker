// Actual Android headers and AAPCS64 callers. The translated entry points below
// exercise real guest start/once/TLS-destructor functions on Windows workers.
#include <pthread.h>
#include <time.h>
#include <stdint.h>
#include <errno.h>
#include <limits.h>
#include <string.h>
#include <unistd.h>

static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition=PTHREAD_COND_INITIALIZER;
static pthread_once_t once=PTHREAD_ONCE_INIT;
static pthread_key_t key;
static unsigned ready,release_workers,count,once_count,destructor_count,errors;
static uintptr_t stack_bases[4],tls_bases[4],thread_ids[4];
static pid_t native_tids[4];
uint64_t guest_gettid(void){pid_t tid=gettid();return tid>0&&gettid()==tid?(uint32_t)tid:0;}
static void initialize(void){++once_count;}
static void destroy_value(void *value){
  pthread_mutex_lock(&mutex);
  if(pthread_getspecific(key))++errors;
  ++destructor_count;
  pthread_mutex_unlock(&mutex);
  if((uintptr_t)value==1)pthread_setspecific(key,(void*)2);
}
static void *worker(void *arg){
  uintptr_t i=(uintptr_t)arg;
  pthread_attr_t attr;void *base=0;size_t size=0;
  if(pthread_getattr_np(pthread_self(),&attr)||pthread_attr_getstack(&attr,&base,&size)||size<16384) return (void*)0xbad1;
  uintptr_t local=(uintptr_t)&attr;
  if(local<(uintptr_t)base||local>=(uintptr_t)base+size)return (void*)0xbad2;
  stack_bases[i]=(uintptr_t)base;thread_ids[i]=pthread_self();
  native_tids[i]=gettid();if(native_tids[i]<=0||gettid()!=native_tids[i])return (void*)0xbad4;
  __asm__("mrs %0,tpidr_el0":"=r"(tls_bases[i]));
  if(pthread_attr_destroy(&attr)||!pthread_equal(pthread_self(),thread_ids[i])||pthread_setname_np(pthread_self(),"bunker-worker")||pthread_setspecific(key,(void*)1))return (void*)0xbad3;
  pthread_once(&once,initialize);
  pthread_mutex_lock(&mutex);++ready;pthread_cond_broadcast(&condition);
  while(!release_workers)pthread_cond_wait(&condition,&mutex);
  pthread_mutex_unlock(&mutex);
  for(unsigned n=0;n<1500;++n){pthread_mutex_lock(&mutex);++count;pthread_mutex_unlock(&mutex);}
  return (void*)(0x100+i);
}
uint64_t guest_threads(void){
  pthread_t threads[4];void *result=0;pthread_attr_t attr;
  if(pthread_key_create(&key,destroy_value)||pthread_attr_init(&attr)||pthread_attr_setstacksize(&attr,65536))return 1;
  for(uintptr_t i=0;i<4;++i)if(pthread_create(&threads[i],&attr,worker,(void*)i))return 2;
  pthread_mutex_lock(&mutex);while(ready!=4)pthread_cond_wait(&condition,&mutex);
  release_workers=1;pthread_cond_broadcast(&condition);pthread_mutex_unlock(&mutex);
  for(unsigned i=0;i<4;++i)if(pthread_join(threads[i],&result)||(uintptr_t)result!=0x100+i)return 3;
  if(count!=6000||once_count!=1||destructor_count!=8||errors)return 4;
  for(unsigned i=0;i<4;++i)for(unsigned j=0;j<i;++j)if(stack_bases[i]==stack_bases[j]||tls_bases[i]==tls_bases[j]||thread_ids[i]==thread_ids[j]||native_tids[i]==native_tids[j])return 5;
  if(pthread_getspecific(key)||pthread_key_delete(key)||pthread_attr_destroy(&attr))return 6;
  return 0x600d;
}
static void *exit_worker(void *v){pthread_setspecific(key,(void*)1);pthread_exit(v);return 0;}
static void *identity(void *v){(void)v;return (void*)(uintptr_t)pthread_self();}
uint64_t guest_exit_lifetimes(void){
  pthread_t thread;void *value;uint64_t previous=0;
  unsigned before=destructor_count;
  if(pthread_key_create(&key,destroy_value)||pthread_create(&thread,0,exit_worker,(void*)0x123456)||pthread_join(thread,&value)||value!=(void*)0x123456||destructor_count!=before+2)return 1;
  if(pthread_key_delete(key))return 2;
  for(unsigned i=0;i<16;++i){if(pthread_create(&thread,0,identity,0)||pthread_join(thread,&value)||(uintptr_t)value!=(uintptr_t)thread||thread==(pthread_t)previous)return 3;previous=(uintptr_t)thread;}
  return 0x600e;
}
uint64_t guest_primitives(void){
  pthread_mutexattr_t ma;pthread_mutex_t recursive,errorcheck;pthread_condattr_t ca;pthread_cond_t cond;struct timespec time;
  if(pthread_mutexattr_init(&ma)||pthread_mutexattr_settype(&ma,PTHREAD_MUTEX_RECURSIVE)||pthread_mutex_init(&recursive,&ma))return 1;
  if(pthread_mutex_lock(&recursive)||pthread_mutex_lock(&recursive)||pthread_mutex_trylock(&recursive)||pthread_mutex_unlock(&recursive)||pthread_mutex_unlock(&recursive)||pthread_mutex_unlock(&recursive)||pthread_mutex_destroy(&recursive))return 2;
  if(pthread_mutexattr_settype(&ma,PTHREAD_MUTEX_ERRORCHECK)||pthread_mutex_init(&errorcheck,&ma)||pthread_mutex_lock(&errorcheck))return 3;
  if(pthread_mutex_lock(&errorcheck)!=EDEADLK||pthread_mutex_trylock(&errorcheck)!=EBUSY||pthread_mutex_destroy(&errorcheck)!=EBUSY)return 4;
  if(pthread_condattr_init(&ca)||pthread_condattr_setclock(&ca,CLOCK_MONOTONIC)||pthread_cond_init(&cond,&ca)||clock_gettime(CLOCK_MONOTONIC,&time))return 5;
  time.tv_nsec+=15000000;if(time.tv_nsec>=1000000000){time.tv_nsec-=1000000000;++time.tv_sec;}
  if(pthread_cond_timedwait(&cond,&errorcheck,&time)!=ETIMEDOUT||pthread_mutex_trylock(&errorcheck)!=EBUSY)return 6;
  time.tv_nsec=1000000000;if(pthread_cond_timedwait(&cond,&errorcheck,&time)!=EINVAL)return 7;
  if(pthread_mutex_unlock(&errorcheck)||pthread_mutex_destroy(&errorcheck)||pthread_mutexattr_destroy(&ma)||pthread_cond_destroy(&cond)||pthread_condattr_destroy(&ca))return 8;
  pthread_rwlock_t rw=PTHREAD_RWLOCK_INITIALIZER;
  if(pthread_rwlock_rdlock(&rw)||pthread_rwlock_rdlock(&rw)||pthread_rwlock_wrlock(&rw)!=EDEADLK||pthread_rwlock_unlock(&rw)||pthread_rwlock_unlock(&rw)||pthread_rwlock_wrlock(&rw)||pthread_rwlock_unlock(&rw)||pthread_rwlock_destroy(&rw))return 9;
  if(pthread_kill(pthread_self(),0)||pthread_kill(pthread_self(),10)!=ENOSYS||pthread_sigmask(0,0,0)!=ENOSYS||pthread_atfork(0,0,0)!=ENOSYS)return 10;
  return 0x600f;
}
static pthread_mutex_t detached_mutex=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t detached_cond=PTHREAD_COND_INITIALIZER;
static unsigned detached_done;
static void *detached_worker(void *arg){(void)arg;pthread_mutex_lock(&detached_mutex);detached_done=1;pthread_cond_broadcast(&detached_cond);pthread_mutex_unlock(&detached_mutex);return (void*)7;}
uint64_t guest_detach(void){
  pthread_attr_t attr;pthread_t thread;
  if(pthread_attr_init(&attr)||pthread_attr_setdetachstate(&attr,PTHREAD_CREATE_DETACHED)||pthread_create(&thread,&attr,detached_worker,0))return 1;
  if(pthread_join(thread,0)!=EINVAL||pthread_detach(thread)!=EINVAL)return 2;
  pthread_mutex_lock(&detached_mutex);while(!detached_done)pthread_cond_wait(&detached_cond,&detached_mutex);pthread_mutex_unlock(&detached_mutex);
  if(pthread_attr_destroy(&attr))return 3;
  if(pthread_create(&thread,0,detached_worker,0)||pthread_detach(thread)||pthread_join(thread,0)!=EINVAL)return 4;
  return 0x6010;
}
static pthread_once_t interrupted_once=PTHREAD_ONCE_INIT;
static unsigned interrupted_tries;
// A typed indirect call gives this fixture finite supported control flow
// (a tail branch or a call/return). A final direct noreturn call can otherwise
// end at zero linker padding, which the strict lifter correctly rejects.
static void (*volatile interrupted_exit)(void*)=pthread_exit;
static void interrupted_initialize(void){if(interrupted_tries++==0)interrupted_exit((void*)0x77);}
static void *once_worker(void *arg){(void)arg;pthread_once(&interrupted_once,interrupted_initialize);return (void*)0x88;}
uint64_t guest_once_exit(void){
  pthread_t t;void *v;
  if(pthread_create(&t,0,once_worker,0)||pthread_join(t,&v)||v!=(void*)0x77)return 1;
  if(pthread_create(&t,0,once_worker,0)||pthread_join(t,&v)||v!=(void*)0x88||interrupted_tries!=2)return 2;
  return 0x6011;
}
static unsigned four_count;
static void destroy_four(void *v){++four_count;pthread_setspecific(key,(void*)((uintptr_t)v+1));}
static void *four_worker(void *v){(void)v;pthread_setspecific(key,(void*)1);return 0;}
uint64_t guest_destructor_limit(void){
  pthread_t t;void *v;
  if(pthread_key_create(&key,destroy_four)||pthread_create(&t,0,four_worker,0)||pthread_join(t,&v)||four_count!=PTHREAD_DESTRUCTOR_ITERATIONS||pthread_key_delete(key))return 1;
  return 0x6012;
}
static void stack_initializer(void){volatile unsigned char scratch[4096];for(unsigned i=0;i<sizeof(scratch);++i)scratch[i]=(unsigned char)i;}
uint64_t guest_nested_stack(void){
  volatile uint64_t sentinel[128];pthread_once_t control=PTHREAD_ONCE_INIT;
  for(unsigned i=0;i<128;++i)sentinel[i]=0xabcdef0000000000ULL+i;
  if(pthread_once(&control,stack_initializer))return 1;
  for(unsigned i=0;i<128;++i)if(sentinel[i]!=0xabcdef0000000000ULL+i)return 2;
  return 0x6013;
}
uint64_t guest_boot_clock(struct timespec *out){
  if(clock_gettime(CLOCK_BOOTTIME,out)||out->tv_sec<0||out->tv_nsec<0||out->tv_nsec>=1000000000)return 1;
  return 0x6014;
}

#include <pthread.h>
#include <signal.h>
#include "worker_signal_lifecycle_fixture.h"
extern void test_observe(WorkerSignalReport*,unsigned);
static pthread_key_t key;
_Static_assert(sizeof(sigset_t)==8,"Android ARM64 sigset wire width");
_Static_assert(sizeof(WorkerSignalReport)==64,"report wire width");
static void destructor(void *value){
  WorkerSignalReport *r=value;++r->rounds;test_observe(r,1);
  if(r->rounds<4){if(pthread_setspecific(key,r))r->error=10;}
  else test_observe(r,2);
}
static void *worker(void *value){
  WorkerSignalReport *r=value;sigset_t mask,pending;stack_t alternate;
  r->token=pthread_self();
  if(pthread_sigmask(SIG_BLOCK,0,&mask)||sigpending(&pending)||sigaltstack(0,&alternate)){r->error=1;return 0;}
  __builtin_memcpy(&r->mask,&mask,8);__builtin_memcpy(&r->pending,&pending,8);r->alt_pointer=(uintptr_t)alternate.ss_sp;r->alt_size=alternate.ss_size;r->alt_flags=alternate.ss_flags;
  test_observe(r,0);
  if(pthread_setspecific(key,r)){r->error=2;return 0;}
  if(r->flags&2){pthread_t child;void *joined=0;if(pthread_create(&child,0,worker,r+1)||pthread_join(child,&joined)||(uintptr_t)joined!=0x1234)r->error=3;}
  if(r->flags&1)pthread_exit((void*)0x1234);
  return (void*)0x1234;
}
__attribute__((visibility("default"))) int signal_lifecycle_driver(WorkerSignalReport *r){
  pthread_t child;void *joined=0;int result=pthread_key_create(&key,destructor);if(result)return result;
  result=pthread_create(&child,0,worker,r);
  if(!result)result=pthread_join(child,&joined);
  r->joined=(uintptr_t)joined;int deleted=pthread_key_delete(key);return result?result:deleted;
}
__attribute__((visibility("default"))) int signal_lifecycle_try_create(WorkerSignalReport *r){
  pthread_t child=(pthread_t)0x11223344;int result=pthread_create(&child,0,worker,r);r->joined=child;return result;
}

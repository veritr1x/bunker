#include "thread_exit_domain_fixture.h"
#include <pthread.h>
#include <stdint.h>
extern void terminal_probe(struct ThreadExitReport *,unsigned);
static pthread_key_t key;
static pthread_once_t outer=PTHREAD_ONCE_INIT,inner=PTHREAD_ONCE_INIT;
static unsigned successes;
static void leave(struct ThreadExitReport*r){
 void(*volatile fn)(void*)=pthread_exit;fn((void*)(uintptr_t)(0x6000+r->mode));++r->after_exit;
}
static void inner_exit(void){struct ThreadExitReport*r=pthread_getspecific(key);++r->once_runs;leave(r);++r->after_once;}
static void outer_exit(void){struct ThreadExitReport*r=pthread_getspecific(key);++r->once_runs;pthread_once(&inner,inner_exit);++r->after_once;}
static void success(void){++successes;}
static void destroy(void *value){struct ThreadExitReport*r=value;++r->destructors;r->outer_at_tls=*(unsigned*)&outer;r->inner_at_tls=*(unsigned*)&inner;terminal_probe(r,2);}
void *terminal_entry(void *value){struct ThreadExitReport*r=value;r->thread=(uintptr_t)pthread_self();++r->entered;if(pthread_setspecific(key,r))++r->errors;terminal_probe(r,1);
 if(r->mode==1)pthread_exit((void*)0x6001);
 if(r->mode==2||r->mode==5)leave(r);
 if(r->mode==3){pthread_once(&outer,inner_exit);++r->after_once;}
 if(r->mode==4){pthread_once(&outer,outer_exit);++r->after_once;}
 return (void*)(uintptr_t)(0x6000+r->mode);
}
uint64_t terminal_setup(void){return pthread_key_create(&key,destroy);}
uint64_t terminal_retry(void){return pthread_once(&outer,success)||pthread_once(&inner,success)?99:successes;}
uint64_t terminal_cleanup(void){return pthread_key_delete(key);}

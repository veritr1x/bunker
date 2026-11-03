#define _GNU_SOURCE
#include "affinity_fixture.h"
#include <errno.h>
#include <pthread.h>
#include <unistd.h>
extern long affinity_raw(uint64_t,uint64_t,uint64_t,void*);
extern void affinity_stage(AffinityWorker*);
__attribute__((noinline)) void affinity_probe(int64_t number,int32_t pid,uint64_t size,void *mask,int indirect,AffinityRecord *out){
 out->before=UINT64_C(0x1122334455667788);out->padding=UINT32_C(0x55aacc33);errno=731;
 long (*volatile call)(long,...)=syscall;
 out->value=indirect?call((long)number,(long)pid,(unsigned long)size,mask,(long)-1,(long)0xbabe,(long)-1):syscall((long)number,(long)pid,(unsigned long)size,mask,(long)-1,(long)0xbabe,(long)-1);
 out->error=errno;out->after=UINT64_C(0x8877665544332211);
}
void affinity_poison(uint64_t number,uint64_t pid,uint64_t size,void *mask,AffinityRecord *out){
 out->before=UINT64_C(0x1122334455667788);out->padding=UINT32_C(0x55aacc33);errno=731;
 out->value=affinity_raw(number,pid,size,mask);out->error=errno;out->after=UINT64_C(0x8877665544332211);
}
void *affinity_worker(void *pointer){
 AffinityWorker *record=pointer;record->tid=(uint32_t)gettid();record->token=(uintptr_t)pthread_self();
 affinity_stage(record);
 affinity_probe(122,0,4,&record->initial_mask,0,&record->self_direct);
 affinity_probe(122,(int32_t)record->tid,4,&record->initial_mask,1,&record->self_indirect);
 return (void*)UINT64_C(0x12345678);
}

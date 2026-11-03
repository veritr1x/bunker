#define _GNU_SOURCE
#include "affinity_get_fixture.h"
#include <sched.h>
#include <errno.h>
#include <pthread.h>
#include <unistd.h>
extern void affinity_get_stage(uint64_t);
__attribute__((noinline)) void affinity_get_probe(int32_t pid,uint64_t size,void *mask,int form,AffinityGetRecord *record){
 record->before=UINT64_C(0x1122334455667788);errno=731;
 int(*volatile call)(pid_t,size_t,cpu_set_t*)=sched_getaffinity;
 record->value=form?call(pid,size,(cpu_set_t*)mask):sched_getaffinity(pid,size,(cpu_set_t*)mask);
 record->error=errno;record->after=UINT64_C(0x8877665544332211);
}
void *affinity_get_worker(void *unused){(void)unused;affinity_get_stage((uint64_t)gettid());return (void*)UINT64_C(0x12345678);}
__attribute__((noinline)) void affinity_set_probe(int32_t pid,uint64_t size,void *mask,int form,AffinityGetRecord *record){
 record->before=UINT64_C(0x1122334455667788);errno=731;
 int(*volatile call)(pid_t,size_t,const cpu_set_t*)=sched_setaffinity;
 record->value=form?call(pid,size,(const cpu_set_t*)mask):sched_setaffinity(pid,size,(const cpu_set_t*)mask);
 record->error=errno;record->after=UINT64_C(0x8877665544332211);
}

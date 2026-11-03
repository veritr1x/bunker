#define _GNU_SOURCE
#include "affinity_fixture.h"
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>
extern void affinity_probe(int64_t,int32_t,uint64_t,void*,int,AffinityRecord*);
extern void affinity_poison(uint64_t,uint64_t,uint64_t,void*,AffinityRecord*);
void affinity_stage(AffinityWorker *p){(void)p;abort();}
static unsigned checks,records;
#ifdef AFFINITY_NATIVE_LINUX
#define LABEL "NATIVE"
#else
#define LABEL "ARM64"
#endif
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
static void check(int yes,const char *why){++checks;if(!yes){fprintf(stderr,"affinity ARM64: %s\n",why);exit(1);}}
static void probe(unsigned id,int32_t pid,void *mask,int64_t expected,int error){
 for(int form=0;form<2;++form){AffinityRecord r={0};affinity_probe(122,pid,4,mask,form,&r);check(r.before==UINT64_C(0x1122334455667788)&&r.after==UINT64_C(0x8877665544332211)&&r.padding==UINT32_C(0x55aacc33),"caller output canaries");check(r.value==expected&&r.error==error,"actual selected oracle result/errno");printf(LABEL "-AFFINITY %u form=%d value=%lld errno=%d\n",id,form,(long long)r.value,r.error);++records;}
}
#ifdef AFFINITY_QEMU_DIVERGENCE
static void *owned(void *argument){
 (void)argument;native_tls=1234;check(native_tls==1234,"native Bionic TLS64");cpu_set_t saved,actual;CPU_ZERO(&saved);check(!sched_getaffinity(0,sizeof(saved),&saved),"actual QEMU compatible full allowed mask");uint32_t low=0;for(unsigned i=0;i<32;++i)if(CPU_ISSET((int)i,&saved))low|=UINT32_C(1)<<i;check(low!=0,"actual allowed low32 CPU exists");uint32_t one=low&(~low+1u),zero=0;
 long page=sysconf(_SC_PAGESIZE);char *allocation=mmap(NULL,(size_t)page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);check(allocation!=MAP_FAILED&&!mprotect(allocation+page,(size_t)page,PROT_NONE),"native QEMU guard page");memcpy(allocation+page-4,&one,4);
 printf("ARM64-QEMU-DIVERGENCE len4 rejected before copy/target; actual allowed low32=%#x\n",low);
 probe(0,0,&one,-1,22);probe(1,(int32_t)gettid(),&low,-1,22);probe(2,0,&one,-1,22);probe(3,0,allocation+page-4,-1,22);probe(4,0,allocation+page-5,-1,22);probe(5,0,&zero,-1,22);probe(6,-1,&one,-1,22);probe(7,-1,(void*)1,-1,22);probe(8,0,(void*)1,-1,22);
 const uint64_t nr[]={UINT64_C(0xabcdef010000007a),UINT64_C(0xffffabcd0000007a),122,122},pid[]={0,0,UINT64_C(0x1234567800000000),UINT64_C(0x12345678ffffffff)},size[]={4,UINT64_C(0xabcdef0100000004),UINT64_C(0xffffffff00000004),4};
 for(unsigned i=0;i<4;++i){AffinityRecord r={0};affinity_poison(nr[i],pid[i],size[i],&one,&r);check(r.before==UINT64_C(0x1122334455667788)&&r.after==UINT64_C(0x8877665544332211)&&r.value==-1&&r.error==22,"actual same NDK poisoned len4 QEMU divergence");printf("ARM64-AFFINITY-POISON %u value=%lld errno=%d\n",i,(long long)r.value,r.error);++records;}
 uint64_t wide=one;for(int form=0;form<2;++form){AffinityRecord r={0};affinity_probe(122,0,8,&wide,form,&r);check(r.value==0&&r.error==731,"separate QEMU len8 control actual syscall transport");CPU_ZERO(&actual);check(!sched_getaffinity(0,sizeof(actual),&actual),"len8 actual QEMU readback");for(unsigned i=0;i<CPU_SETSIZE;++i)check(!!CPU_ISSET((int)i,&actual)==(i<32&&!!(one&(UINT32_C(1)<<i))),"len8 control actual selected CPU");printf("ARM64-LEN8-CONTROL form=%d value=%lld errno=%d\n",form,(long long)r.value,r.error);}
 check(!sched_setaffinity(0,sizeof(saved),&saved),"restore own QEMU child mask");CPU_ZERO(&actual);check(!sched_getaffinity(0,sizeof(actual),&actual)&&!memcmp(&saved,&actual,sizeof(saved)),"QEMU own mask restored exact");check(!munmap(allocation,(size_t)page*2),"native guard cleanup");return NULL;
}
#else
static void *owned(void *argument){
 (void)argument;native_tls=1234;check(native_tls==1234,"native reference TLS64");cpu_set_t saved,actual;CPU_ZERO(&saved);check(!sched_getaffinity(0,sizeof(saved),&saved),"actual full allowed CPU mask");uint32_t low=0;for(unsigned i=0;i<32;++i)if(CPU_ISSET((int)i,&saved))low|=UINT32_C(1)<<i;
 check(low!=0,"fixture host must expose an actual allowed CPU below32");uint32_t one=low&(~low+1u);printf(LABEL "-CPU actual_allowed_low32=%#x selected=%#x\n",low,one);
 probe(0,0,&one,0,731);CPU_ZERO(&actual);check(!sched_getaffinity(0,sizeof(actual),&actual),"actual narrowed readback");for(unsigned i=0;i<CPU_SETSIZE;++i)check(!!CPU_ISSET((int)i,&actual)==(i<32&&!!(one&(UINT32_C(1)<<i))),"kernel selected requested eligible CPU only");
 probe(1,(int32_t)gettid(),&low,0,731);CPU_ZERO(&actual);check(!sched_getaffinity(0,sizeof(actual),&actual),"actual expanded readback");for(unsigned i=0;i<32;++i)check(!!CPU_ISSET((int)i,&actual)==!!(low&(UINT32_C(1)<<i)),"narrow then expand uses allowed ceiling");
 uint32_t unavailable=~low;check(unavailable!=0,"fixture host needs an unavailable low32 bit for clipping oracle");unavailable&=(~unavailable+1u);uint32_t mixed=one|unavailable;probe(2,0,&mixed,0,731);CPU_ZERO(&actual);check(!sched_getaffinity(0,sizeof(actual),&actual),"clipped readback");for(unsigned i=0;i<32;++i)check(!!CPU_ISSET((int)i,&actual)==!!(one&(UINT32_C(1)<<i)),"unavailable bits ignored with nonempty intersection");
 long page=sysconf(_SC_PAGESIZE);check(page>0,"native page size");char *allocation=mmap(NULL,(size_t)page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);check(allocation!=MAP_FAILED&&!mprotect(allocation+page,(size_t)page,PROT_NONE),"actual native guard page");
 memcpy(allocation+page-4,&one,4);probe(3,0,allocation+page-4,0,731);memcpy(allocation+page-5,&one,4);probe(4,0,allocation+page-5,0,731);
 uint32_t zero=0;probe(5,0,&zero,-1,22);probe(6,-1,&one,-1,3);probe(7,-1,(void*)1,-1,14);probe(8,0,(void*)1,-1,14);
 const uint64_t nr[]={UINT64_C(0xabcdef010000007a),UINT64_C(0xffffabcd0000007a),122,122};const uint64_t pid[]={0,0,UINT64_C(0x1234567800000000),UINT64_C(0x12345678ffffffff)};const uint64_t size[]={4,UINT64_C(0xabcdef0100000004),UINT64_C(0xffffffff00000004),4};
 for(unsigned i=0;i<4;++i){AffinityRecord r={0};affinity_poison(nr[i],pid[i],size[i],&one,&r);check(r.before==UINT64_C(0x1122334455667788)&&r.after==UINT64_C(0x8877665544332211)&&r.padding==UINT32_C(0x55aacc33)&&r.value==(i==3?-1:0)&&r.error==(i==3?3:731),"raw upper-register poison kernel int decode");printf(LABEL "-AFFINITY-POISON %u value=%lld errno=%d\n",i,(long long)r.value,r.error);++records;}
 errno=0;long zero_len=syscall(122L,0L,0UL,(void*)0,-1L,0xbabeL,-1L);printf(LABEL "-OUTSIDE-PROFILE zero_length_NULL value=%ld errno=%d; measured not Windows-profile equivalence\n",zero_len,errno);
 check(!sched_setaffinity(0,sizeof(saved),&saved),"restore only own native child's original full mask");CPU_ZERO(&actual);check(!sched_getaffinity(0,sizeof(actual),&actual)&&!memcmp(&saved,&actual,sizeof(saved)),"native restore readback exact");check(!munmap(allocation,(size_t)page*2),"native fixture mapping cleanup");return NULL;
}
#endif
int main(void){alarm(30);
#ifdef AFFINITY_NATIVE_LINUX
 extern long affinity_host_number(void);printf("NATIVE-KERNEL-NAMESPACE Android122 explicitly maps to host syscall%ld\n",affinity_host_number());
#endif
 cpu_set_t before,after;CPU_ZERO(&before);check(!sched_getaffinity(0,sizeof(before),&before),"parent affinity read-only before");pthread_t thread;int create=pthread_create(&thread,NULL,owned,NULL);if(create){fprintf(stderr,"pthread_create failed%d\n",create);return 1;}int joined=pthread_join(thread,NULL);check(!joined,"native child join");CPU_ZERO(&after);check(!sched_getaffinity(0,sizeof(after),&after)&&!memcmp(&before,&after,sizeof(before)),"parent affinity unchanged");
#ifdef AFFINITY_QEMU_DIVERGENCE
 printf("AFFINITY-ARM64-DIVERGENCE-QUALIFIED records=%u controls8=2 checks=%u\n",records,checks);
#else
 printf("AFFINITY-NATIVE-KERNEL-SUCCESS records=%u checks=%u\n",records,checks);
#endif
 return 0;}

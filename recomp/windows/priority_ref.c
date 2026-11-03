#include "priority_fixture.h"
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <unistd.h>
extern void priority_probe(int,uint32_t,int,PriorityRecord*);
extern void priority_poison(uint64_t,uint64_t,PriorityRecord*);
void priority_stage(PriorityWorker *p,int phase){(void)p;(void)phase;abort();}
static unsigned checks;
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
static void check(int yes,const char *why){++checks;if(!yes){fprintf(stderr,"priority ARM64: %s\n",why);exit(1);}}
static void probe(unsigned id,int which,uint32_t who,int expected,int error){
 for(int form=0;form<2;++form){PriorityRecord r={0};priority_probe(which,who,form,&r);check(r.before==UINT64_C(0x1122334455667788)&&r.after==UINT64_C(0x8877665544332211),"real NDK record canaries");check(r.value==expected&&r.error==error,"real Bionic priority result/errno");printf("ANDROID-PROBE %u form=%d value=%d errno=%d\n",id,form,r.value,r.error);}
}
static void *lower(void *arg){
 int *result=arg;errno=0;int before=getpriority(PRIO_PROCESS,0);check(errno==0,"child native initial query");int desired=before<10?10:before;
 errno=617;check(setpriority(PRIO_PROCESS,0,desired)==0,"only lower actual owned child CFS priority");errno=0;int actual=getpriority(PRIO_PROCESS,0);check(errno==0&&actual==desired,"actual native lowered nice readback");long raw=syscall(__NR_getpriority,PRIO_PROCESS,0);check(raw==20-actual,"independent ARM64 kernel raw priority result");*result=actual;printf("ANDROID-LOWER before=%d after=%d raw=%ld\n",before,actual,raw);return NULL;
}
int main(void){native_tls=0x1234;check(native_tls==0x1234,"real native Bionic TLS64");alarm(30);errno=0;int initial=getpriority(PRIO_PROCESS,0);check(!errno&&initial>=-20&&initial<=19,"native initial nice range");long raw=syscall(__NR_getpriority,0,0);check(raw==20-initial,"raw kernel result versus Bionic normalization");
 probe(0,0,0,initial,731);probe(1,0,(uint32_t)gettid(),initial,731);probe(2,-1,0,-1,22);probe(3,3,0,-1,22);probe(4,0,UINT32_MAX,-1,3);
 const uint64_t which[]={UINT64_C(0xabcdef0100000000),UINT64_C(0x11223344ffffffff),UINT64_C(0x1122334400000000)};const uint64_t who[]={UINT64_C(0x5566778800000000),0,UINT64_C(0xdeadbeefffffffff)};const int values[]={initial,-1,-1},errors[]={731,22,3};
 for(unsigned i=0;i<3;++i){PriorityRecord r={0};priority_poison(which[i],who[i],&r);check(r.value==values[i]&&r.error==errors[i]&&r.before==UINT64_C(0x1122334455667788)&&r.after==UINT64_C(0x8877665544332211),"actual raw upper-register poison normalizes low32");printf("ANDROID-POISON %u value=%d errno=%d\n",i,r.value,r.error);}
 pthread_t t;int final=0;check(!pthread_create(&t,NULL,lower,&final)&&!pthread_join(t,NULL),"native owned child lifecycle");check(final>=initial,"no native priority elevation");printf("PRIORITY-ARM64-SUCCESS checks=%u initial=%d records=13\n",checks,initial);return 0;
}

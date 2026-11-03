#define _GNU_SOURCE
#include "affinity_get_fixture.h"
#include <sched.h>
#include <unistd.h>
#include <sys/mman.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern void affinity_get_probe(int32_t,uint64_t,void*,int,AffinityGetRecord*);
extern void affinity_set_probe(int32_t,uint64_t,void*,int,AffinityGetRecord*);
void affinity_get_stage(uint64_t tid){(void)tid;abort();} /* host-only parked worker seam, never executed here */
_Thread_local __attribute__((aligned(64))) unsigned char affinity_tls_anchor;
static unsigned records;
static void check(int yes,const char*name){if(!yes){fprintf(stderr,"ARM getaffinity: %s\n",name);exit(1);}}
static void probe(unsigned id,int32_t pid,uint64_t size,void*mask,int rc,int error){for(int form=0;form<2;++form){AffinityGetRecord r;affinity_get_probe(pid,size,mask,form,&r);check(r.before==UINT64_C(0x1122334455667788)&&r.after==UINT64_C(0x8877665544332211)&&r.value==rc&&r.error==error,"return/errno/canaries");printf("GET-AFFINITY %u form=%d rc=%d errno=%d\n",id,form,r.value,r.error);++records;}}
static void setprobe(unsigned id,int32_t pid,void*mask,int rc,int error){for(int form=0;form<2;++form){AffinityGetRecord r;affinity_set_probe(pid,128,mask,form,&r);check(r.before==UINT64_C(0x1122334455667788)&&r.after==UINT64_C(0x8877665544332211)&&r.value==rc&&r.error==error,"setter return/errno/guards");printf("SET-AFFINITY %u form=%d rc=%d errno=%d\n",id,form,r.value,r.error);++records;}}
int main(void){affinity_tls_anchor=1;
 unsigned char expected[128],mask[130];check(sched_getaffinity(0,128,(cpu_set_t*)expected)==0,"real Bionic getter");
 for(int form=0;form<2;++form){memset(mask,0xa5,sizeof(mask));AffinityGetRecord r;affinity_get_probe((int32_t)gettid(),128,mask+1,form,&r);check(!r.value&&r.error==731&&mask[0]==0xa5&&mask[129]==0xa5&&!memcmp(mask+1,expected,128),"unaligned exact128 output/native mask");printf("GET-AFFINITY 0 form=%d rc=%d errno=%d\n",form,r.value,r.error);++records;}
 unsigned char *pages=mmap(NULL,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);check(pages!=MAP_FAILED&&mprotect(pages+4096,4096,PROT_NONE)==0,"real page guard");probe(1,0,128,pages+4096-128,0,731);check(!memcmp(pages+4096-128,expected,128),"exact guarded footprint");
 probe(2,-1,128,(void*)1,-1,3);probe(3,0,128,(void*)1,-1,14);
 memset(pages,0xa5,128);check(!mprotect(pages,4096,PROT_READ),"readonly mask");probe(4,0,128,pages,-1,14);for(int i=0;i<128;++i)check(pages[i]==0xa5,"RO unchanged");
 probe(5,-1,0,(void*)1,-1,22);probe(6,-1,4,(void*)1,-1,22);probe(7,-1,129,(void*)1,-1,22);
 unsigned char selected[128]={0},readback[128];int first=-1;for(int i=0;i<1024;++i)if(expected[i/8]&(1u<<(i%8))){first=i;break;}check(first>=0,"real nonempty affinity");selected[first/8]=(unsigned char)(1u<<(first%8));
 setprobe(0,0,selected,0,731);check(!sched_getaffinity(0,128,(cpu_set_t*)readback)&&!memcmp(readback,selected,128),"real narrow/readback");check(!sched_setaffinity(0,128,(cpu_set_t*)expected),"restore real original affinity");
 unsigned char zero[128]={0};setprobe(1,0,zero,-1,22);setprobe(2,-1,zero,-1,3);setprobe(3,-1,(void*)1,-1,14);setprobe(4,0,(void*)1,-1,14);
 printf("GET-AFFINITY-ARM64-PASS records=%u mask=",records);for(int i=0;i<128;++i)printf("%02x",expected[i]);puts("");munmap(pages,8192);return 0;
}

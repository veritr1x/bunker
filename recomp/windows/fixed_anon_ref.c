#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
extern void*fixed_guest_map(uint64_t,uint64_t,int,int,int,int64_t,int,int*);
extern int fixed_guest_protect(uint64_t,uint64_t,int,int,int*);
static _Thread_local volatile unsigned tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;int error=0;unsigned records=0;for(int form=0;form<2;form++){unsigned char*p=mmap(0,12288,3,0x22,-1,0);if(p==MAP_FAILED)return 1;for(int cycle=0;cycle<2;cycle++){memset(p,0x51,4096);memset(p+4096,0xa7,4096);memset(p+8192,0x93,4096);void*r=fixed_guest_map((uintptr_t)(p+4096),4096,0,0x32,-1,0,form,&error);if(r!=p+4096||error!=731)return 2;if(fixed_guest_protect((uintptr_t)(p+4096),4096,cycle?7:3,form,&error)||error!=731)return 3;for(unsigned i=0;i<4096;i++){if(p[i]!=0x51||p[4096+i]!=0||p[8192+i]!=0x93)return 4;}printf("FIXED-REF form=%d cycle=%d exact=1 zero=1 outside=1 protection=%d errno=%d\n",form,cycle,cycle?7:3,error);++records;}if(munmap(p,12288))return 5;}printf("FIXED-ANON-ARM-PASS records=%u TLS=%u\n",records,tls_canary);return records!=4||tls_canary!=17;}

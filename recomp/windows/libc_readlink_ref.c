#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include <string.h>
extern int64_t guest_readlink(const char*,void*,uint64_t,int,int,int*);
__thread unsigned char reference_tls[64] __attribute__((aligned(64)));
static void call(const char *label,const char *path,int nullout,uint64_t capacity,int indirect){
 unsigned char bytes[512];memset(bytes,0xa5,sizeof bytes);int error=-1;
 volatile uintptr_t zero=0;
 int64_t n=guest_readlink(path,nullout?(void*)zero:bytes,capacity,indirect,731,&error);
 printf("%s mode=%d count=%lld errno=%d canary=%02x",label,indirect,(long long)n,error,bytes[capacity<sizeof bytes?(size_t)capacity:sizeof bytes-1]);
 if(n>0){printf(" bytes=");for(int64_t i=0;i<n;++i)printf("%02x",bytes[i]);}putchar('\n');
}
int main(void){reference_tls[0]=1;__asm__ volatile(""::"r"(reference_tls):"memory");char own[80];snprintf(own,sizeof own,"/proc/%d/exe",getpid());volatile uintptr_t zero=0;
 for(int mode=0;mode<2;++mode){call("self","/proc/self/exe",0,511,mode);call("pid",own,0,511,mode);call("one","/proc/self/exe",0,1,mode);call("zero","/proc/self/exe",0,0,mode);call("nullpath-zero",(const char*)zero,0,0,mode);call("nullout-zero","/proc/self/exe",1,0,mode);call("bothnull-zero",(const char*)zero,1,0,mode);call("nullpath-one",(const char*)zero,0,1,mode);call("nullout-one","/proc/self/exe",1,1,mode);}
 return 0;}

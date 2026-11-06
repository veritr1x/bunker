// TEST-only original eight-byte helper + original PLT, real Bionic mutex target.
#include <elf.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
static pthread_mutex_t real_mutex=PTHREAD_MUTEX_INITIALIZER;
static uintptr_t field;
static atomic_int entered,returned;
static _Thread_local volatile unsigned tls_canary __attribute__((aligned(64)));
static int observed_mutex_lock(pthread_mutex_t*p){if(p!=&real_mutex||field!=(uintptr_t)p||&field==(uintptr_t*)p)abort();atomic_store(&entered,1);return pthread_mutex_lock(p);}
static void*worker(void*unused){(void)unused;int(*call)(uintptr_t*)=(void*)0x82550e3c;int result=call(&field);if(result||pthread_mutex_unlock(&real_mutex))abort();atomic_store(&returned,1);return 0;}
int main(int argc,char**argv){tls_canary=17;if(argc!=2)return 1;FILE*f=fopen(argv[1],"rb");if(!f)return 2;Elf64_Ehdr e;Elf64_Phdr ph[32];if(fread(&e,1,sizeof(e),f)!=sizeof(e)||e.e_phnum>32||e.e_machine!=183)return 3;fseek(f,e.e_phoff,SEEK_SET);if(fread(ph,sizeof(*ph),e.e_phnum,f)!=e.e_phnum)return 4;if(mmap((void*)0x80000000,0x8000000,7,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)0x80000000)return 5;for(unsigned i=0;i<e.e_phnum;i++)if(ph[i].p_type==PT_LOAD){fseek(f,ph[i].p_offset,SEEK_SET);if(fread((void*)(0x80000000+ph[i].p_vaddr),1,ph[i].p_filesz,f)!=ph[i].p_filesz)return 6;}fclose(f);
 static const unsigned char original[]={0x00,0x00,0x40,0xf9,0x1c,0xec,0xed,0x17};if(memcmp((void*)0x82550e3c,original,8))return 7;
 const uint32_t*plt=(const void*)0x820cbeb0;if((plt[0]&0x9f00001f)!=0x90000010||(plt[1]&0xffc003ff)!=0xf9400211||plt[3]!=0xd61f0220)return 8;int64_t imm=((plt[0]>>5)&0x7ffff)*4+((plt[0]>>29)&3);if(imm&(1<<20))imm-=1<<21;uintptr_t got=(0x820cbeb0&~(uintptr_t)4095)+imm*4096+(((plt[1]>>10)&0xfff)*8);*(uintptr_t*)got=(uintptr_t)observed_mutex_lock;
 __builtin___clear_cache((char*)0x80000000,(char*)0x88000000);field=(uintptr_t)&real_mutex;if(pthread_mutex_lock(&real_mutex))return 9;pthread_t thread;if(pthread_create(&thread,0,worker,0))return 10;for(unsigned i=0;!atomic_load(&entered)&&i<2000;i++)usleep(1000);if(!atomic_load(&entered)||atomic_load(&returned))return 11;if(pthread_mutex_unlock(&real_mutex)||pthread_join(thread,0)||!atomic_load(&returned)||tls_canary!=17)return 12;printf("ORIGINAL-MUTEX-FORWARDER-ARM-PASS bytes=8 field_distinct=1 actual_mutex_calls=1 contended=1 result=0 pointer_bits=%zu TLS=%u\n",sizeof(uintptr_t)*8,tls_canary);return 0;}

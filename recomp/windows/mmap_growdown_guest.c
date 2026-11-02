#include <sys/mman.h>
#include <errno.h>
#include <stdint.h>
_Static_assert(MAP_GROWSDOWN==0x100&&MAP_STACK==0x20000&&MAP_PRIVATE==2&&MAP_ANONYMOUS==0x20,"exact ARM64 NDK mmap flags");
uint64_t growdown_original(void){errno=71;void*p=mmap(0,0x40000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_GROWSDOWN|MAP_STACK,-1,0);return((uint64_t)(uint32_t)errno<<32)|(p==MAP_FAILED);}
uint64_t growdown_malformed(uint64_t length,int protection,int flags,int64_t offset){errno=71;void*p=mmap(0,length,protection,flags,-1,offset);return((uint64_t)(uint32_t)errno<<32)|(p==MAP_FAILED);}
uint64_t growdown_zero_noreplace(void){return growdown_malformed(8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_GROWSDOWN|MAP_STACK|MAP_FIXED_NOREPLACE,0);}

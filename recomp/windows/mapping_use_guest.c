#include <stdint.h>
#include <sys/mman.h>
#include <errno.h>
void *mapping_guest_map(uint64_t length){return mmap(0,length,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);}
int mapping_guest_protect(void *base,uint64_t length,int protection){return mprotect(base,length,protection);}
int mapping_guest_unmap(void *base,uint64_t length){return munmap(base,length);}
uint64_t mapping_guest_touch(volatile uint8_t *base,uint64_t length){base[0]=0x35;base[length-1]=0xa7;return((uint64_t)base[0]<<8)|base[length-1];}

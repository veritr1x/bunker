#include <stdint.h>
#include <errno.h>
#include <sys/mman.h>
void *growth_map(uint64_t length,int flags){return mmap(0,length,PROT_READ|PROT_WRITE,flags,-1,0);}
void *growth_map_at(void *address,uint64_t length,int protection,int flags){return mmap(address,length,protection,flags,-1,0);}
int growth_unmap(void *address,uint64_t length){return munmap(address,length);}
int growth_protect(void *address,uint64_t length,int protection){return mprotect(address,length,protection);}
uint64_t growth_read(const volatile uint64_t *address){return *address;}
void growth_write(volatile uint64_t *address,uint64_t value){*address=value;}
uint64_t growth_exclusive(uint64_t *address,uint64_t value){
  uint64_t previous;uint32_t status;
  __asm__ volatile("ldaxr %0,[%2]\n\tstlxr %w1,%3,[%2]":"=&r"(previous),"=&r"(status):"r"(address),"r"(value):"memory");
  return status?UINT64_MAX:previous;
}
uint32_t growth_errno(void){return (uint32_t)errno;}

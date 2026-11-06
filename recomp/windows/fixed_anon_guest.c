#include <stdint.h>
#include <sys/mman.h>
#include <errno.h>
_Static_assert(sizeof(void*)==8&&sizeof(off_t)==8,"actual AArch64 mmap ABI");
_Static_assert((MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED)==0x32,"actual fixed anonymous flags");
static void*(*volatile mapper)(void*,size_t,int,int,int,off_t)=mmap;
static int(*volatile protector)(void*,size_t,int)=mprotect;
void*fixed_guest_map(uint64_t address,uint64_t length,int prot,int flags,int fd,int64_t offset,int pointer,int*error){errno=731;void*r=pointer?mapper((void*)address,length,prot,flags,fd,offset):mmap((void*)address,length,prot,flags,fd,offset);*error=errno;return r;}
int fixed_guest_protect(uint64_t address,uint64_t length,int prot,int pointer,int*error){errno=731;int r=pointer?protector((void*)address,length,prot):mprotect((void*)address,length,prot);*error=errno;return r;}

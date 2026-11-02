#include <unistd.h>
#include <errno.h>
#include <stdint.h>
_Static_assert(sizeof(ssize_t)==8&&sizeof(size_t)==8,"Android LP64 readlink ABI");
int64_t guest_readlink(const char *path,void *output,uint64_t size,int indirect,int sentinel,int *error){
 errno=sentinel;
 __typeof__(&readlink) volatile query=readlink;
 ssize_t result=indirect?query(path,output,size):readlink(path,output,size);
 *error=errno;return result;
}

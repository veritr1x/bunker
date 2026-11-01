#include <errno.h>
#include <stdint.h>
#include <unistd.h>
_Static_assert(sizeof(void*)==8 && sizeof(int)==4,"Android remove ABI");
_Static_assert(EISDIR==21 && ENOTDIR==20 && ENOTEMPTY==39 && EBUSY==16,"Android removal errors");
uint64_t guest_remove(const char *path,int directory,int indirect){
  errno=123;int result;
  if(indirect){int(*volatile operation)(const char*)=directory?rmdir:unlink;result=operation(path);}
  else result=directory?rmdir(path):unlink(path);
  return (uint64_t)(uint32_t)errno<<32|(uint32_t)result;
}

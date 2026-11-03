#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
_Static_assert(sizeof(Dl_info)==32,"Android LP64 Dl_info");
_Static_assert(offsetof(Dl_info,dli_fname)==0&&offsetof(Dl_info,dli_fbase)==8&&offsetof(Dl_info,dli_sname)==16&&offsetof(Dl_info,dli_saddr)==24,"Android wire fields");
__attribute__((noinline)) int guest_dladdr(const void *address,Dl_info *out,int indirect,int *error){
 errno=731;
 int result;
 if(indirect){int(*volatile call)(const void*,Dl_info*)=dladdr;result=call(address,out);}else result=dladdr(address,out);
 *error=errno;return result;
}
__attribute__((noinline)) void *guest_dlsym(void *handle,const char *name){void*(*volatile call)(void*,const char*)=dlsym;return call(handle,name);}

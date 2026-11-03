#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern int guest_dladdr(const void*,Dl_info*,int,int*);
// Same NDK object, with its Bionic errno accessor bound to this real glibc
// process's native TLS errno. dladdr itself is the dynamic glibc implementation.
extern int *__errno_location(void);
int *__errno(void){return __errno_location();}
int main(int argc,char**argv){
 if(argc!=2)return 2;
 void*h=dlopen(argv[1],RTLD_NOW);if(!h){fprintf(stderr,"%s\n",dlerror());return 3;}
 void *v2=dlsym(h,"fixture_v2");if(!v2||dlsym(h,"fixture_versioned")!=v2)return 8;
 dlerror();if(dlsym(h,"fixture_hidden_only")||!dlerror())return 9;
 puts("version default=V2 hidden-only=missing");
 const char*names[]={"fixture_function","fixture_data"};
 for(unsigned n=0;n<2;++n){void*p=dlsym(h,names[n]);if(!p)return 4;
  for(unsigned offset=0;offset<2;++offset)for(int indirect=0;indirect<2;++indirect){
   Dl_info out;memset(&out,0xa5,sizeof(out));int error=0;
   int r=guest_dladdr((char*)p+offset,&out,indirect,&error);
   if(r!=1||error!=731||!out.dli_fname||strcmp(out.dli_fname,argv[1])||!out.dli_fbase||!out.dli_sname||strcmp(out.dli_sname,names[n])||out.dli_saddr!=p)return 5;
   printf("known %s offset=%u indirect=%d return=%d errno=%d base-offset=%llu\n",out.dli_sname,offset,indirect,r,error,(unsigned long long)((uintptr_t)p-(uintptr_t)out.dli_fbase));
  }
 }
 for(int indirect=0;indirect<2;++indirect){Dl_info out,before;memset(&out,0xa5,sizeof(out));before=out;int error=0;int r=guest_dladdr((void*)1,&out,indirect,&error);if(r||error!=731||memcmp(&out,&before,32))return 6;printf("unknown indirect=%d return=0 errno=731 untouched=32\n",indirect);}
 if(dlclose(h))return 7;
 puts("DLADDR-ARM64-GLIBC-SUCCESS records=10");return 0;
}

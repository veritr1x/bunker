#include <time.h>
#include <stddef.h>
_Static_assert(sizeof(clockid_t)==4 && (clockid_t)-1<0,"signed Android clock ID");
_Static_assert(sizeof(struct timespec)==16 && offsetof(struct timespec,tv_nsec)==8,"Android LP64 timespec");
int pthread_clock_direct(clockid_t id,struct timespec *output){return clock_getres(id,output);}
int pthread_clock_indirect(clockid_t id,struct timespec *output){int(*volatile query)(clockid_t,struct timespec*)=clock_getres;return query(id,output);}

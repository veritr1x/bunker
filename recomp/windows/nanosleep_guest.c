#include <errno.h>
#include <stdint.h>
#include <time.h>
extern int nanosleep_direct(const struct timespec*,struct timespec*);
extern int nanosleep_indirect(const struct timespec*,struct timespec*);
extern void nanosleep_fixture_delay(void);
volatile uint32_t nanosleep_handlers;
volatile uintptr_t nanosleep_remaining_probe;
volatile int nanosleep_delay_handler;
volatile int64_t nanosleep_handler_seconds,nanosleep_handler_nanoseconds;
void nanosleep_handler(int signal){
 nanosleep_handlers+=(uint32_t)(signal==10);
 if(nanosleep_remaining_probe){const struct timespec*p=(const struct timespec*)nanosleep_remaining_probe;nanosleep_handler_seconds=p->tv_sec;nanosleep_handler_nanoseconds=p->tv_nsec;}
 if(nanosleep_delay_handler)nanosleep_fixture_delay();
 errno=901;
}
__attribute__((noinline)) int guest_nanosleep(const struct timespec*request,struct timespec*remaining,int mode,int*error){errno=731;int result=mode?nanosleep_indirect(request,remaining):nanosleep_direct(request,remaining);*error=errno;return result;}
void nanosleep_return(void){}

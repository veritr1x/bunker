#include <stdint.h>
#include <errno.h>
extern int sleep_direct(uint64_t);
extern int sleep_indirect(uint64_t);
volatile uint32_t sleep_handlers;
void sleep_handler(int signal){sleep_handlers+=(uint32_t)(signal==10);errno=901;}
__attribute__((noinline)) int guest_sleep(uint64_t us,int mode,int *error){errno=731;int r=mode?sleep_indirect(us):sleep_direct(us);*error=errno;return r;}
void sleep_return(void){}

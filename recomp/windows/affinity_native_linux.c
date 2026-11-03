// Independent real native Linux kernel oracle. Android122 is explicitly
// mapped to the host architecture's SYS_sched_setaffinity, never forwarded.
#define _GNU_SOURCE
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <sys/syscall.h>
#include <unistd.h>
long affinity_host_number(void){return SYS_sched_setaffinity;}
long android_affinity_syscall(long number,...){
 if((uint32_t)number!=122){errno=ENOSYS;return -1;}
 va_list args;va_start(args,number);long pid=va_arg(args,long);unsigned long length=va_arg(args,unsigned long);void *mask=va_arg(args,void*);long tail4=va_arg(args,long),tail5=va_arg(args,long),tail6=va_arg(args,long);va_end(args);
 return syscall(SYS_sched_setaffinity,pid,length,mask,tail4,tail5,tail6);
}

#include <unistd.h>
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
_Static_assert(sizeof(pid_t)==4 && (pid_t)-1<0,"Android signed32 pid_t");
struct pid_result {pid_t first,second;int32_t error,reserved;int64_t widened;};
_Static_assert(sizeof(struct pid_result)==24 && offsetof(struct pid_result,widened)==16,"Android PID observation layout");
int64_t guest_pid(struct pid_result *out,int indirect,int sentinel){
  errno=sentinel;
  __typeof__(&getpid) volatile query=getpid;
  pid_t first=indirect?query():getpid();
  pid_t second=indirect?query():getpid();
  out->first=first;out->second=second;out->error=errno;out->widened=(int64_t)first;
  return (int64_t)second;
}
pid_t guest_pid_return(void){return getpid();}

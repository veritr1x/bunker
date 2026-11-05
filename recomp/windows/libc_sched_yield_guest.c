#include <sched.h>
#include <errno.h>
#include <stdint.h>
struct YieldResult { int32_t status,error; int64_t widened; };
int64_t guest_sched_yield(int indirect,int sentinel,struct YieldResult*output){
  errno=sentinel;
  int status;
  if(indirect){int(*volatile function)(void)=sched_yield;status=function();}
  else status=sched_yield();
  output->status=status;output->error=errno;output->widened=status;
  return status;
}

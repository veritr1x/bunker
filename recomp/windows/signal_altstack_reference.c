#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <ucontext.h>
#include <unistd.h>
static unsigned char a[262144] __attribute__((aligned(16))),b[262144] __attribute__((aligned(16)));
static uintptr_t outer_sp,nested_sp,outer_saved,nested_saved;
static unsigned outer_raw,nested_raw,outer_query,nested_query,mode,changed;
static int onstack_rc,onstack_errno;
static void nested(int signal,siginfo_t *info,void *context){
  (void)signal;(void)info;ucontext_t *u=context;stack_t q;__asm__ volatile("mov %0,sp":"=r"(nested_sp));nested_saved=u->uc_mcontext.sp;nested_raw=u->uc_stack.ss_flags;sigaltstack(0,&q);nested_query=q.ss_flags;
}
static void handler(int signal,siginfo_t *info,void *context){
  (void)signal;(void)info;ucontext_t *u=context;stack_t q;__asm__ volatile("mov %0,sp":"=r"(outer_sp));outer_saved=u->uc_mcontext.sp;outer_raw=u->uc_stack.ss_flags;sigaltstack(0,&q);outer_query=q.ss_flags;
  if(mode){stack_t replacement={.ss_sp=b,.ss_flags=0,.ss_size=sizeof(b)};int r=sigaltstack(&replacement,0);sigaltstack(0,&q);changed=r==0&&q.ss_sp==b;}
  else{stack_t invalid={.ss_sp=0,.ss_flags=4,.ss_size=0};errno=71;onstack_rc=sigaltstack(&invalid,0);onstack_errno=errno;raise(SIGUSR2);}
}
static void signal_cases(void){
  stack_t x={.ss_sp=a,.ss_flags=0,.ss_size=sizeof(a)},q;sigaltstack(&x,0);
  struct sigaction action={0};sigemptyset(&action.sa_mask);action.sa_sigaction=nested;action.sa_flags=SA_SIGINFO;sigaction(SIGUSR2,&action,0);action.sa_sigaction=handler;action.sa_flags=SA_SIGINFO|SA_ONSTACK;sigaction(SIGUSR1,&action,0);raise(SIGUSR1);
  printf("delivery alt=%d nested_below=%d normal_saved=%d nested_saved=%d raw=%u/%u query=%u/%u onstack=%d/%d\n",outer_sp>(uintptr_t)a&&outer_sp<=(uintptr_t)(a+sizeof(a)),nested_sp>(uintptr_t)a&&nested_sp<outer_sp,outer_saved<(uintptr_t)a||outer_saved>(uintptr_t)(a+sizeof(a)),nested_saved>(uintptr_t)a&&nested_saved<outer_sp+512,outer_raw,nested_raw,outer_query,nested_query,onstack_rc,onstack_errno);
  mode=1;action.sa_flags=SA_SIGINFO;sigaction(SIGUSR1,&action,0);raise(SIGUSR1);sigaltstack(0,&q);
  printf("normal_change normal=%d observed_b=%u restored_a=%d raw=%u query=%u\n",outer_sp<(uintptr_t)a||outer_sp>(uintptr_t)(a+sizeof(a)),changed,q.ss_sp==a,outer_raw,outer_query);
}
static void print_case(const char *name,const stack_t *set,int alias){
  struct {uint64_t before;stack_t value;uint64_t after;} output;memset(&output,0xa5,sizeof(output));
  if(alias)output.value=*set;
  errno=71;int result=sigaltstack(alias?&output.value:set,&output.value),error=errno;
  const unsigned char *raw=(const unsigned char*)&output.value;int unchanged=1;for(unsigned i=0;i<24;++i)if(raw[i]!=0xa5)unchanged=0;
  const unsigned char *pad=raw+12;
  unsigned kind=output.value.ss_sp==0?0:output.value.ss_sp==a?1:output.value.ss_sp==b?2:9;
  printf("%s result=%d errno=%d kind=%u flags=%u size=%llu pad=%02x%02x%02x%02x untouched=%d guards=%d\n",name,result,error,kind,(unsigned)output.value.ss_flags,(unsigned long long)output.value.ss_size,pad[0],pad[1],pad[2],pad[3],unchanged,output.before==UINT64_C(0xa5a5a5a5a5a5a5a5)&&output.after==UINT64_C(0xa5a5a5a5a5a5a5a5));
}
int main(void){
  printf("layout size=%zu align=%zu flags=%zu length=%zu\n",sizeof(stack_t),_Alignof(stack_t),offsetof(stack_t,ss_flags),offsetof(stack_t,ss_size));
  stack_t x={.ss_sp=a,.ss_flags=0,.ss_size=sizeof(a)},y={.ss_sp=b,.ss_flags=0,.ss_size=sizeof(b)},off={.ss_sp=(void*)1,.ss_flags=SS_DISABLE,.ss_size=1},small={.ss_sp=a,.ss_flags=0,.ss_size=5119},bad={.ss_sp=a,.ss_flags=4,.ss_size=0},restore_failed={0};
  print_case("initial",0,0);print_case("install_a",&x,0);print_case("query_a",0,0);print_case("alias_b",&y,1);print_case("query_b",0,0);print_case("small",&small,0);print_case("invalid",&bad,0);print_case("restore_a",&x,0);print_case("disable",&off,0);print_case("query_disabled",0,0);print_case("unity_restore_zero",&restore_failed,0);
  errno=71;int result=sigaltstack(&x,(void*)1),error=errno;stack_t q={0};sigaltstack(0,&q);printf("bad_old result=%d errno=%d committed=%d\n",result,error,q.ss_sp==a&&q.ss_size==sizeof(a));
  signal_cases();sigaltstack(&off,0);return 0;
}

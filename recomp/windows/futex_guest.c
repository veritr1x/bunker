#include "futex_fixture.h"
#include <errno.h>
volatile uint32_t futex_handler_count,futex_handler_mode;
volatile uintptr_t futex_handler_word;
volatile int64_t futex_handler_wake;
__attribute__((noinline)) int64_t guest_futex(const FutexCall*call,int*error){
 errno=731;int64_t result=call->mode?futex_indirect(call->nr,call->address,call->operation,call->value,call->timeout,call->address2,call->value3):futex_direct(call->nr,call->address,call->operation,call->value,call->timeout,call->address2,call->value3);*error=errno;return result;
}
void futex_handler(int signal){
 if(signal!=10)return;
 __atomic_store_n(&futex_handler_count,__atomic_load_n(&futex_handler_count,__ATOMIC_RELAXED)+1,__ATOMIC_RELEASE);
 volatile uint32_t*word=(volatile uint32_t*)futex_handler_word;
 if(futex_handler_mode&1)__atomic_store_n(word,1,__ATOMIC_RELEASE);
 futex_handler_wake=futex_direct(98,(uintptr_t)word,0x81,1,UINT64_MAX,UINT64_MAX,UINT64_MAX);
 errno=901;
}
void futex_return(void){}

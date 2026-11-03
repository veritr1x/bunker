#pragma once
#include <stdint.h>
#include <stddef.h>
typedef struct {uint64_t nr,address,operation,value,timeout,address2,value3,mode;} FutexCall;
extern int64_t futex_direct(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
extern int64_t futex_indirect(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
extern int64_t guest_futex(const FutexCall*,int*);
extern void futex_handler(int);
extern void futex_return(void);
extern volatile uint32_t futex_handler_count,futex_handler_mode;
extern volatile uintptr_t futex_handler_word;
extern volatile int64_t futex_handler_wake;

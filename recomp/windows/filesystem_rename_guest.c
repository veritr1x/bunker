#include <stdio.h>
#include <stdint.h>
#include <errno.h>
_Static_assert(sizeof(void*)==8 && sizeof(int)==4,"Android rename ABI");
uint64_t guest_rename(const char *source,const char *destination,int indirect){
 errno=123;int value;
 if(indirect){int(*volatile operation)(const char*,const char*)=rename;value=operation(source,destination);}
 else value=rename(source,destination);
 return (uint64_t)(uint32_t)errno<<32|(uint32_t)value;
}

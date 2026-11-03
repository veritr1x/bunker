#include <stdint.h>
#include <stdio.h>
#include <string.h>
extern void display_fcsel_native(uint64_t,uint32_t,uint8_t*);
int main(void){for(unsigned n=0;n<4;++n){unsigned error=n&1;uint32_t input=n<2?0x42f00000:0;uint8_t out[16],expected[16]={0};uint32_t selected=error?0:input;memcpy(expected,&selected,4);display_fcsel_native(error?0:0x40000000,input,out);if(memcmp(out,expected,16))return 1;printf("ORACLE %08x %u %08x\n",input,error,selected);}puts("DISPLAY-FCSEL-ARM-SUCCESS 4");return 0;}

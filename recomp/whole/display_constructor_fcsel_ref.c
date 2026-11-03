#include <stdint.h>
#include <stdio.h>
#include <string.h>
extern void display_constructor_fcsel_native(uint32_t,uint8_t*);
int main(void){const uint32_t inputs[]={0x42f00000,0,0x41200000};const uint32_t expected[]={0x42f00000,0x42700000,0x41200000};for(unsigned n=0;n<3;++n){uint8_t out[16],want[16]={0};memcpy(want,&expected[n],4);display_constructor_fcsel_native(inputs[n],out);if(memcmp(out,want,16))return 1;printf("ORACLE %08x %08x\n",inputs[n],expected[n]);}puts("DISPLAY-CONSTRUCTOR-FCSEL-ARM-SUCCESS 3");return 0;}

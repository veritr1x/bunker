#include <stdint.h>
#include <stdio.h>
extern uint32_t numeric_promotion(uint32_t);
int main(void){
 const uint32_t inputs[]={0,0x80000000,1,0x80000001,0x007fffff,0x00800000,0x3f800000,0xbf800000,0x3eaaaaab,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00000,0xffc12345,0x7fa12345,0xffa12345,0x7fffffff};
 for(unsigned i=0;i<sizeof(inputs)/sizeof(inputs[0]);++i)printf("%08x %08x\n",inputs[i],numeric_promotion(inputs[i]));return 0;
}

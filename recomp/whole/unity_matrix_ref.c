#include <stdint.h>
#include "unity_matrix_driver.h"
extern void unity_matrix_call(uint8_t*,const uint8_t*,const uint8_t*,uint8_t*,uint64_t,uint64_t);
int main(int argc,char **argv){return run_matrix_cases(unity_matrix_call,argc>1&&!strcmp(argv[1],"diagnostic"));}

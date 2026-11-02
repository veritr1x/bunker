#include <stdio.h>
#include <stdint.h>
#include <errno.h>
_Static_assert(sizeof(unsigned long long)==8,"Android unsigned long long output width");
_Static_assert(sizeof(int)==4,"Android scanf return width");
int64_t guest_sscanf(const char *input,const char *format,unsigned long long *output,int indirect,int sentinel,int *error){
  errno=sentinel;
  __typeof__(&sscanf) volatile scan=sscanf;
  int result=indirect?scan(input,format,output):sscanf(input,format,output);
  *error=errno;
  return (int64_t)result;
}

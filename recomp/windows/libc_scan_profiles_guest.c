#include <stdio.h>
#include <stdint.h>
int64_t guest_scan_profiles(const char*input,const char*format,void*a,void*b,void*c,void*d){return sscanf(input,format,a,b,c,d);}

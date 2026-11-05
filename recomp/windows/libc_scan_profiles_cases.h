#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static const char*const scan_formats[]={"%15[^:]:%[^\n]","%15[^\n:]:%3[/]%[^\n/?#]%[^\n]","%[^\n/?#]%[^\n]","[%*45[0123456789abcdefABCDEF:.]%c","%llu"};
struct ScanCase {unsigned format;const char*input;};
static const struct ScanCase scan_cases[]={
 {0,""},{0,":"},{0,"abc"},{0,"abc:"},{0,"abc:def"},{0,"abc:def\nx"},{0,"abc:\rdef"},{0,"a\nb:c"},{0,"123456789012345:tail"},{0,"1234567890123456:tail"},{0,"http://host/path?x#z"},{0,"\xc3\xa9:\xe6\x97\xa5"},
 {1,""},{1,"http:"},{1,"http:/"},{1,"http:///a"},{1,"http:////a"},{1,"http://host/path?x#z"},{1,"http://host?x"},{1,"https://host#fragment"},{1,"a:\\host"},{1,"a\nb://host/tail"},{1,"123456789012345://host/t"},{1,"1234567890123456://host/t"},{1,"http://\xc3\xa9/\xe6\x97\xa5"},{1,"http://host\r/tail\nx"},
 {2,""},{2,"/"},{2,"?"},{2,"#"},{2,"host"},{2,"host/path?x#z"},{2,"host?"},{2,"host\nrest"},{2,"host\r/tail"},{2,"\xc3\xa9/\xe6\x97\xa5"},
 {3,""},{3,"["},{3,"[]"},{3,"[::1]"},{3,"[::1]rest"},{3,"[z]"},{3,"[a\n"},{3,"[012345678901234567890123456789012345678901234]"},{3,"[0123456789012345678901234567890123456789012345]"},
 {4,""},{4,"x"},{4,"42"},{4,"18446744073709551615"},{4,"18446744073709551616"},{4,"-1"}
};
struct ScanBuffers {uint64_t alignment;unsigned char bytes[4][112];};
static inline void ScanInitialize(struct ScanBuffers*out){memset(out,0xa5,sizeof(*out));}
static inline void ScanRecord(unsigned index,int status,int error,const struct ScanBuffers*out){
 printf("REC %u %d %d ",index,status,error);const unsigned char*p=(const unsigned char*)out;for(unsigned n=0;n<sizeof(*out);++n)printf("%02x",p[n]);putchar('\n');
}
#define SCAN_CASE_COUNT (sizeof(scan_cases)/sizeof(scan_cases[0]))

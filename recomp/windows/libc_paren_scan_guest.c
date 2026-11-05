#include <stdio.h>
#include <stdint.h>
typedef int(*Scanner)(const char*,const char*,...);
static Scanner volatile scanner=sscanf;
static const char*const formats[]={" HTTP/%d.%d %d"," HTTP/2 %d"," HTTP %3d"," RTSP/%d.%d %3d","(%u)"};
int64_t guest_paren_scan(const char*input,unsigned profile,int*major,int*minor,int*status,int indirect){if(profile==4){if(indirect)return scanner(input,formats[profile],(unsigned int*)major);return sscanf(input,formats[profile],(unsigned int*)major);}if(indirect)return scanner(input,formats[profile],major,minor,status);return sscanf(input,formats[profile],major,minor,status);}

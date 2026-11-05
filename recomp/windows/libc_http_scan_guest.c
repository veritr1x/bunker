#include <stdio.h>
#include <stdint.h>
typedef int(*Scanner)(const char*,const char*,...);
static Scanner volatile scanner=sscanf;
static const char*const formats[]={" HTTP/%d.%d %d"," HTTP/2 %d"," HTTP %3d"," RTSP/%d.%d %3d"};
int64_t guest_http_scan(const char*input,unsigned profile,int*major,int*minor,int*status,int indirect){if(indirect)return scanner(input,formats[profile],major,minor,status);return sscanf(input,formats[profile],major,minor,status);}

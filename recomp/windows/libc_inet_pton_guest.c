#include <arpa/inet.h>
#include <stdint.h>
int64_t guest_inet_pton(int family,const char*input,void*output,int indirect){if(indirect){int(*volatile function)(int,const char*,void*)=inet_pton;return function(family,input,output);}return inet_pton(family,input,output);}

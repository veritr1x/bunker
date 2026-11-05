#include <netdb.h>
#include <stdint.h>
#include <stddef.h>
_Static_assert(sizeof(struct addrinfo)==48,"Android LP64 addrinfo size");
_Static_assert(offsetof(struct addrinfo,ai_addrlen)==16,"Android addrlen32");
_Static_assert(sizeof(((struct addrinfo*)0)->ai_addrlen)==4,"Android socklen32");
_Static_assert(offsetof(struct addrinfo,ai_canonname)==24,"Android canon before address");
_Static_assert(offsetof(struct addrinfo,ai_addr)==32,"Android address offset");
_Static_assert(offsetof(struct addrinfo,ai_next)==40,"Android next offset");
int64_t guest_getaddrinfo(const char*node,const char*service,const struct addrinfo*hints,struct addrinfo**output,int indirect){if(indirect){int(*volatile fn)(const char*,const char*,const struct addrinfo*,struct addrinfo**)=getaddrinfo;return fn(node,service,hints,output);}return getaddrinfo(node,service,hints,output);}
void guest_freeaddrinfo(struct addrinfo*output,int indirect){if(indirect){void(*volatile fn)(struct addrinfo*)=freeaddrinfo;fn(output);}else freeaddrinfo(output);}
uintptr_t guest_gai_strerror(int error,int indirect){if(indirect){const char*(*volatile fn)(int)=gai_strerror;return (uintptr_t)fn(error);}return (uintptr_t)gai_strerror(error);}

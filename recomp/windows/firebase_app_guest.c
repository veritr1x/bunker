#include <stdint.h>
#include <stddef.h>
extern void *malloc(size_t);
extern void free(void*);
extern void TEST_replay(void);
static volatile uint64_t *record;
static uint64_t hash(const char*s){uint64_t h=0; if(s)while(*s)h=h*131+(unsigned char)*s++;return h;}
#define E(N) __attribute__((visibility("default"))) void exception##N(const char*s){record[N]++;record[20+N]=hash(s);}
E(0) E(1) E(2) E(3) E(4) E(5) E(6) E(7) E(8) E(9) E(10)
#define A(N) __attribute__((visibility("default"))) void argument##N(const char*s,const char*p){record[11+N]++;record[31+N]=hash(s);record[34+N]=hash(p);}
A(0) A(1) A(2)
__attribute__((visibility("default"))) void log_message(int level,const char*s){record[14]++;record[37]=(uint32_t)level;record[38]=hash(s);}
__attribute__((visibility("default"))) const char* string_copy(const char*s){record[15]++;record[39]=hash(s);TEST_replay();size_t n=0;while(s[n])++n;char*p=malloc(n+1);for(size_t i=0;i<=n;++i)p[i]=s[i];record[40]=(uintptr_t)p;return p;}
typedef void(*Ecb)(const char*);typedef void(*Acb)(const char*,const char*);
__attribute__((visibility("default"))) void register_all(uintptr_t e,uintptr_t a,uintptr_t s,uintptr_t l,uint64_t*r){record=r;((void(*)(Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb))e)(exception0,exception1,exception2,exception3,exception4,exception5,exception6,exception7,exception8,exception9,exception10);((void(*)(Acb,Acb,Acb))a)(argument0,argument1,argument2);((void(*)(const char*(*)(const char*)))s)(string_copy);((void(*)(void(*)(int,const char*)))l)(log_message);}
__attribute__((visibility("default"))) uint64_t call0(uintptr_t f){return ((uint64_t(*)(void))f)();}
__attribute__((visibility("default"))) uint64_t call1(uintptr_t f,uintptr_t a){return ((uint64_t(*)(uintptr_t))f)(a);}
__attribute__((visibility("default"))) uint64_t call2(uintptr_t f,uintptr_t a,uintptr_t b){return ((uint64_t(*)(uintptr_t,uintptr_t))f)(a,b);}
__attribute__((visibility("default"))) uint64_t default_name(uintptr_t f){const char*p=((const char*(*)(void))f)();uint64_t h=hash(p);record[41]=(uintptr_t)p;free((void*)p);record[16]++;return h;}

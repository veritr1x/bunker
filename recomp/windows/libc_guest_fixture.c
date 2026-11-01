#define _GNU_SOURCE
#include <stdlib.h>
#include <malloc.h>
#include <string.h>
#include <strings.h>
#include <stdint.h>
#include <errno.h>
#include <ctype.h>
#include <math.h>
extern int __cxa_atexit(void (*)(void *), void *, void *);
extern void __cxa_finalize(void *);
extern char **environ;
_Static_assert(sizeof(long)==8 && sizeof(size_t)==8, "fixture requires Android LP64");
#define REQUIRE(x) do { if (!(x)) return __LINE__; } while (0)
int guest_allocators(void) {
    unsigned char *p = calloc(33,3);REQUIRE(p && !((uintptr_t)p&15));
    for(unsigned i=0;i<99;++i)REQUIRE(p[i]==0);
    memset(p,0x8d,99);unsigned char *q=realloc(p,4096);REQUIRE(q);
    for(unsigned i=0;i<99;++i)REQUIRE(q[i]==0x8d);
    errno=0;REQUIRE(!realloc(q,SIZE_MAX)&&errno==ENOMEM&&q[98]==0x8d);free(q);
    errno=0;REQUIRE(!calloc(SIZE_MAX,2)&&errno==ENOMEM);
    p=malloc(0);REQUIRE(p);free(p);free(NULL);
    p=memalign(256,513);REQUIRE(p&&!((uintptr_t)p&255));memset(p,0x37,513);
    q=realloc(p,1024);REQUIRE(q);for(unsigned i=0;i<513;++i)REQUIRE(q[i]==0x37);free(q);
    void *aligned=(void *)0x1234;errno=123;
    REQUIRE(posix_memalign(&aligned,3,100)==EINVAL&&aligned==(void *)0x1234&&errno==123);
    REQUIRE(!posix_memalign(&aligned,512,100)&&aligned&&!((uintptr_t)aligned&511));free(aligned);
    char b[32];memcpy(b,"0123456789",11);REQUIRE(memmove(b+2,b,8)==b+2&&!memcmp(b,"0101234567",10));
    REQUIRE(memchr(b,'1',10)==b+1&&memrchr(b,'1',10)==b+3);
    return 0;
}
int guest_strings(void) {
    char b[64],n[8];strcpy(b,"Bun");strcat(b,"ker");strncat(b,"XYZ",2);
    REQUIRE(!strcmp(b,"BunkerXY")&&strlen(b)==8&&strnlen(b,3)==3);
    memset(n,0x7f,sizeof(n));strncpy(n,"hi",5);REQUIRE(n[2]==0&&n[4]==0&&n[5]==0x7f);
    REQUIRE(!strncmp(b,"Bunker",6)&&strchr(b,'k')==b+3&&strrchr(b,'X')==b+6);
    REQUIRE(strstr(b,"ker")==b+3&&strpbrk(b,"XY")==b+6);
    REQUIRE(!strcasecmp("BuNkEr","bunker")&&!strncasecmp("AbcX","aBCy",3));
    REQUIRE(strlcpy(n,"long string",sizeof(n))==11&&!strcmp(n,"long st"));
    char *p=strdup(b);REQUIRE(p&&!strcmp(p,b));free(p);
    char *save=NULL;strcpy(b,",one::two,,");p=strtok_r(b,",:",&save);REQUIRE(p&&!strcmp(p,"one"));
    p=strtok_r(NULL,",:",&save);REQUIRE(p&&!strcmp(p,"two")&&!strtok_r(NULL,",:",&save));
    REQUIRE(isalpha('A')&&isalpha('z')&&!isalpha(0x80)&&isspace('\n')&&!isspace('!'));
    REQUIRE(isxdigit('f')&&!isxdigit('g')&&islower('a')&&isupper('A')&&isprint(' '));
    REQUIRE(tolower('Q')=='q'&&toupper('q')=='Q'&&tolower(-1)==-1);
    return 0;
}
int guest_parsing(void) {
    char *end;const char *s;
    errno=117;s="9223372036854775807tail";REQUIRE(strtol(s,&end,10)==INT64_MAX&&end==s+19&&errno==117);
    s="-9223372036854775808!";REQUIRE(strtoll(s,&end,10)==INT64_MIN&&end==s+20);
    errno=0;s="9223372036854775808999x";REQUIRE(strtol(s,&end,10)==INT64_MAX&&end==s+22&&errno==ERANGE);
    errno=0;s="-9223372036854775809x";REQUIRE(strtoll(s,&end,10)==INT64_MIN&&end==s+20&&errno==ERANGE);
    errno=0;s="18446744073709551615x";REQUIRE(strtoul(s,&end,10)==UINT64_MAX&&end==s+20&&errno==0);
    s="18446744073709551616x";REQUIRE(strtoull(s,&end,10)==UINT64_MAX&&end==s+20&&errno==ERANGE);
    errno=0;s="-1!";REQUIRE(strtoul(s,&end,0)==UINT64_MAX&&end==s+2&&errno==0);
    s="  -0x10rest";REQUIRE(strtol(s,&end,0)==-16&&end==s+7);
    s="0xG";REQUIRE(strtol(s,&end,0)==0&&end==s+1);
    s=" +oops";errno=87;REQUIRE(strtol(s,&end,10)==0&&end==s&&errno==87);
    errno=0;s="123";REQUIRE(strtol(s,&end,1)==0&&end==s&&errno==EINVAL);
    errno=17;s="0b2";REQUIRE(strtol(s,&end,0)==0&&end==s+1&&errno==17);
    s="0b1011";REQUIRE(strtoull(s,&end,2)==0&&end==s+1);
    s="0x";REQUIRE(strtoul(s,&end,16)==0&&end==s+1);
    s=" \t+";REQUIRE(strtoll(s,&end,10)==0&&end==s);
    REQUIRE(atol("4294967297")==INT64_C(4294967297)&&atoi("-123")==-123);
    s="1.25x";REQUIRE(strtod(s,&end)==1.25&&end==s+4&&strtof("-2.5",NULL)==-2.5f);
    return 0;
}
int guest_math(void) {
    int e;double ip;float fp;
    REQUIRE(sin(0.0)==0.0&&cosf(0.0f)==1.0f&&sqrt(81.0)==9.0&&sqrtf(25.0f)==5.0f);
    REQUIRE(pow(2.0,10.0)==1024.0&&ldexp(1.5,10)==1536.0&&fmod(7.5,2.0)==1.5);
    REQUIRE(frexpf(12.0f,&e)==0.75f&&e==4&&modf(-2.25,&ip)==-0.25&&ip==-2.0);
    REQUIRE(modff(3.5f,&fp)==0.5f&&fp==3.0f);
    errno=0;REQUIRE(isnan(sqrt(-1.0))&&errno==EDOM);
    return 0;
}
static uint64_t *order;static unsigned count;
static void destructor(void *arg) {
    uintptr_t v=(uintptr_t)arg;order[count++]=v;
    if(v==3){__cxa_atexit(destructor,(void *)4,(void *)0xa001);__cxa_finalize((void *)0xa001);}
}
static void plain(void){order[count++]=9;}
int guest_lifecycle(uint64_t *output) {
    order=output;count=0;
    REQUIRE(!__cxa_atexit(destructor,(void *)1,(void *)0xa001));
    REQUIRE(!__cxa_atexit(destructor,(void *)2,(void *)0xa002));
    REQUIRE(!__cxa_atexit(destructor,(void *)3,(void *)0xa001));REQUIRE(!atexit(plain));
    __cxa_finalize((void *)0xa001);REQUIRE(count==3&&order[0]==3&&order[1]==4&&order[2]==1);
    __cxa_finalize((void *)0xa001);REQUIRE(count==3);
    __cxa_finalize((void *)0xa002);REQUIRE(count==4&&order[3]==2);
    __cxa_finalize(NULL);REQUIRE(count==5&&order[4]==9);__cxa_finalize(NULL);REQUIRE(count==5);
    return 0;
}
int guest_environment(void) {
    REQUIRE(getenv("BUNKER_TEST")&&!strcmp(getenv("BUNKER_TEST"),"configured"));
    REQUIRE(!getenv("BUNKER_HOST_ONLY_TEST"));
    REQUIRE(!setenv("NEW_GUEST","value",1)&&!strcmp(getenv("NEW_GUEST"),"value"));
    REQUIRE(!setenv("NEW_GUEST","other",0)&&!strcmp(getenv("NEW_GUEST"),"value"));
    REQUIRE(!setenv("NEW_GUEST","other",1)&&!strcmp(getenv("NEW_GUEST"),"other"));
    int found=0;for(char **e=environ;*e;++e)if(!strcmp(*e,"NEW_GUEST=other"))found=1;REQUIRE(found);
    REQUIRE(!unsetenv("NEW_GUEST")&&!getenv("NEW_GUEST"));errno=0;
    REQUIRE(setenv("bad=name","value",1)==-1&&errno==EINVAL);return 0;
}

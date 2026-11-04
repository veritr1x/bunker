#include <time.h>
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
_Static_assert(sizeof(time_t)==8 && (time_t)-1<0,"signed64 Bionic time_t");
_Static_assert(sizeof(struct tm)==56&&_Alignof(struct tm)==8,"Bionic tm56/8");
_Static_assert(offsetof(struct tm,tm_isdst)==32&&offsetof(struct tm,tm_gmtoff)==40&&offsetof(struct tm,tm_zone)==48,"Bionic tm tail layout");
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
struct input {const char*label;int year,mon,day,hour,min,sec,isdst;long hint;};
static const struct input cases[]={
 {"epoch",1970,0,1,0,0,0,0,0},{"minus_one",1969,11,31,23,59,59,0,0},
 {"pre_epoch",1960,0,1,0,0,0,-1,0},{"post2038",2040,0,1,0,0,0,-1,0},
 {"leap2000",2000,1,29,12,0,0,-1,0},{"nonleap1900",1900,1,29,0,0,0,-1,0},
 {"normalize",2024,12,0,25,-61,121,-1,0},{"neg_month",2024,-13,1,0,0,0,-1,0},
 {"winter_auto",2024,0,15,12,0,0,-1,0},{"winter_std",2024,0,15,12,0,0,0,0},{"winter_dst",2024,0,15,12,0,0,1,0},
 {"summer_auto",2024,6,15,12,0,0,-1,0},{"summer_std",2024,6,15,12,0,0,0,0},{"summer_dst",2024,6,15,12,0,0,1,0},
 {"fold_auto",2024,10,3,1,30,0,-1,0},{"fold_std",2024,10,3,1,30,0,0,0},{"fold_dst",2024,10,3,1,30,0,1,0},
 {"gap_auto",2024,2,10,2,30,0,-1,0},{"gap_std",2024,2,10,2,30,0,0,0},{"gap_dst",2024,2,10,2,30,0,1,0},
 {"gap_dst2",2024,2,10,2,30,0,2,0},{"fold_hint_std",2024,10,3,1,30,0,-1,-18000},{"fold_hint_dst",2024,10,3,1,30,0,-1,-14400},
 {"fold_bad_hint",2024,10,3,1,30,0,-1,19800},{"year_low",-10000,0,1,0,0,0,-1,0},{"year_high",100000,0,1,0,0,0,-1,0}
};
static const char*patterns[]={"%a %A %b %B %c %x %X %r","%F %T %D %R %j %U %W %u %w %V %g %G %z %Z","%e %k %l %C %y %Y %p %P","%_d %-d %0d %^a %#A %Ec %Od","%s %% %n %t"};
static void fields(const struct tm*t){unsigned pad;memcpy(&pad,(const char*)t+36,4);printf("%d,%d,%d,%d,%d,%d,%d,%d,%d,%ld,%s,%u",t->tm_sec,t->tm_min,t->tm_hour,t->tm_mday,t->tm_mon,t->tm_year,t->tm_wday,t->tm_yday,t->tm_isdst,t->tm_gmtoff,t->tm_zone?t->tm_zone:"NULL",pad);}
int main(int argc,char**argv){
 tls_canary=17;
 if(argc>1&&!strcmp(argv[1],"null")){errno=22;time_t(*volatile call)(struct tm*)=mktime;time_t r=call(NULL);printf("NULL|%lld|%d\n",(long long)r,errno);return tls_canary!=17;}
 const char*tz=getenv("TZ");if(!tz)return 2;tzset();
 printf("ABI|%zu|%zu|%zu|%zu|%zu|%zu\n",sizeof(time_t),sizeof(struct tm),_Alignof(struct tm),offsetof(struct tm,tm_year),offsetof(struct tm,tm_gmtoff),offsetof(struct tm,tm_zone));
 for(size_t i=0;i<sizeof(cases)/sizeof(cases[0]);++i){const struct input*c=cases+i;struct tm t;memset(&t,0xa5,sizeof(t));t.tm_sec=c->sec;t.tm_min=c->min;t.tm_hour=c->hour;t.tm_mday=c->day;t.tm_mon=c->mon;t.tm_year=c->year-1900;t.tm_wday=77;t.tm_yday=88;t.tm_isdst=c->isdst;t.tm_gmtoff=c->hint;t.tm_zone=NULL;errno=22;time_t r=mktime(&t);int error=errno;printf("MK|%s|%lld|%d|",c->label,(long long)r,error);fields(&t);putchar('\n');}
 time_t epoch=0;struct tm*l=localtime(&epoch);struct tm saved=*l;const char*zone=l->tm_zone;char name[128];snprintf(name,sizeof(name),"%s",zone);struct tm*g=gmtime(&epoch);
 printf("SHARED|%d|%d|%s|%s\n",l==g,zone!=NULL,name,zone);printf("GM|0|");fields(g);putchar('\n');
 struct tm local;localtime_r(&epoch,&local);printf("LOCAL|0|");fields(&local);putchar('\n');
 for(size_t cap=0;cap<8;++cap){char b[24];memset(b,'!',sizeof(b));errno=22;size_t n=strftime(b+8,cap,"%Z",&saved);printf("FMT|%zu|%zu|%d|",cap,n,errno);for(size_t j=0;j<sizeof(b);++j)printf("%02x",(unsigned char)b[j]);putchar('\n');}
 const time_t stamps[]={0,-1,1577707200,1609502400,951825600};
 for(size_t i=0;i<sizeof(stamps)/sizeof(stamps[0]);++i)for(size_t k=0;k<sizeof(patterns)/sizeof(patterns[0]);++k){struct tm t;localtime_r(stamps+i,&t);char b[512];memset(b,0,sizeof(b));errno=22;size_t n=strftime(b,sizeof(b),patterns[k],&t);printf("FCASE|%lld|%zu|%zu|%d|",(long long)stamps[i],k,n,errno);for(size_t j=0;j<n;++j)printf("%02x",(unsigned char)b[j]);putchar('\n');}
 printf("DIFF|%.0f|%.0f|%.0f\n",difftime(INT64_MAX,INT64_MAX-1),difftime(INT64_MIN+1,INT64_MIN),difftime(INT64_MAX,INT64_MIN));return tls_canary!=17;
}

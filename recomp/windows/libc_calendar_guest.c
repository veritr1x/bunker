#include <time.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
_Static_assert(sizeof(time_t)==8&&(time_t)-1<0,"signed64 time_t");
_Static_assert(sizeof(struct tm)==56&&_Alignof(struct tm)==8,"Bionic tm56 ABI");
_Static_assert(offsetof(struct tm,tm_sec)==0&&offsetof(struct tm,tm_min)==4&&offsetof(struct tm,tm_hour)==8&&offsetof(struct tm,tm_mday)==12&&offsetof(struct tm,tm_mon)==16&&offsetof(struct tm,tm_year)==20&&offsetof(struct tm,tm_wday)==24&&offsetof(struct tm,tm_yday)==28&&offsetof(struct tm,tm_isdst)==32&&offsetof(struct tm,tm_gmtoff)==40&&offsetof(struct tm,tm_zone)==48,"all tm offsets");
struct request{uint32_t operation,indirect;int32_t sentinel,pad;uint64_t a,b,c,d;};
struct result{uint64_t integer;double floating;int32_t error,pad;};
uint64_t guest_calendar(const struct request*q,struct result*r){
 errno=q->sentinel;uint64_t value=0;double floating=0;
 switch(q->operation){
 case 0:{__typeof__(&mktime)volatile f=mktime;value=(uint64_t)(q->indirect?f((struct tm*)q->a):mktime((struct tm*)q->a));break;}
 case 1:{__typeof__(&localtime)volatile f=localtime;value=(uint64_t)(q->indirect?f((time_t*)q->a):localtime((time_t*)q->a));break;}
 case 2:{__typeof__(&localtime_r)volatile f=localtime_r;value=(uint64_t)(q->indirect?f((time_t*)q->a,(struct tm*)q->b):localtime_r((time_t*)q->a,(struct tm*)q->b));break;}
 case 3:{__typeof__(&gmtime)volatile f=gmtime;value=(uint64_t)(q->indirect?f((time_t*)q->a):gmtime((time_t*)q->a));break;}
 case 4:{__typeof__(&gmtime_r)volatile f=gmtime_r;value=(uint64_t)(q->indirect?f((time_t*)q->a,(struct tm*)q->b):gmtime_r((time_t*)q->a,(struct tm*)q->b));break;}
 case 5:{__typeof__(&time)volatile f=time;value=(uint64_t)(q->indirect?f((time_t*)q->a):time((time_t*)q->a));break;}
 case 6:{__typeof__(&difftime)volatile f=difftime;floating=q->indirect?f((time_t)q->a,(time_t)q->b):difftime((time_t)q->a,(time_t)q->b);break;}
 case 7:{__typeof__(&strftime)volatile f=strftime;value=q->indirect?f((char*)q->a,(size_t)q->b,(const char*)q->c,(struct tm*)q->d):strftime((char*)q->a,(size_t)q->b,(const char*)q->c,(struct tm*)q->d);break;}
 default:value=UINT64_MAX;break;
 }
 r->integer=value;r->floating=floating;r->error=errno;return value;
}
uint64_t guest_calendar_layout(unsigned i){const uint64_t a[]={sizeof(time_t),sizeof(struct tm),_Alignof(struct tm),offsetof(struct tm,tm_year),offsetof(struct tm,tm_gmtoff),offsetof(struct tm,tm_zone),sizeof(struct request),sizeof(struct result)};return i<8?a[i]:UINT64_MAX;}

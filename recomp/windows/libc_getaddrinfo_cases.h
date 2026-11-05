#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* Exact Android LP64 public addrinfo, never the host's native netdb layout. */
struct GaiAddr {int32_t flags,family,type,protocol;uint32_t length,padding;uint64_t canon,address,next;};
struct GaiCase {const char*node;const char*service;int32_t flags,family,type,protocol;int null_hints,bad_hint;};
#define GAI_CASE(n,s,f,a,t,p) {n,s,f,a,t,p,0,0}
static const struct GaiCase gai_cases[]={
 GAI_CASE("127.0.0.1","80",12,2,1,6),GAI_CASE("192.0.2.123","443",12,2,1,6),GAI_CASE("255.255.255.255","65535",12,2,2,17),
 GAI_CASE("0.0.0.0","0",12,2,1,0),GAI_CASE("127.0.0.1",0,4,2,1,6),GAI_CASE("127.0.0.1","123",12,2,2,0),
 GAI_CASE("::1","80",12,10,1,6),GAI_CASE("2001:db8::1","443",12,10,1,6),GAI_CASE("::","65535",12,10,2,17),
 GAI_CASE("::ffff:192.0.2.1","0",12,10,1,6),GAI_CASE("::1",0,4,10,1,6),GAI_CASE("1:2:3:4:5:6:7:8","123",12,10,2,17),
 GAI_CASE("127.0.0.1","80",12,0,1,6),GAI_CASE("::1","80",12,0,1,6),
 GAI_CASE("127.0.0.1","80",14,2,1,6),GAI_CASE("::1","80",14,10,1,6),
 GAI_CASE(0,"80",8,2,1,6),GAI_CASE(0,"80",9,2,1,6),GAI_CASE(0,"123",8,10,2,17),GAI_CASE(0,"123",9,10,2,17),
 GAI_CASE(0,"80",8,0,1,6),GAI_CASE(0,"80",9,0,1,6),GAI_CASE(0,0,0,0,0,0),
 GAI_CASE("127.0.0.1","80",12,2,0,0),GAI_CASE("127.0.0.1",0,4,2,0,0),
 GAI_CASE("127.0.0.1",0,4,2,3,0),GAI_CASE("127.0.0.1",0,4,2,3,255),
 GAI_CASE("127.0.0.1","http",4,2,1,6),GAI_CASE("127.0.0.1","https",4,2,1,6),GAI_CASE("127.0.0.1","domain",4,2,2,17),
 GAI_CASE("127.0.0.1","http",12,2,1,6),GAI_CASE("127.0.0.1","gai-no-such-service-9357",4,2,1,6),
 GAI_CASE("127.0.0.1","65536",12,2,1,6),GAI_CASE("127.0.0.1","-1",12,2,1,6),GAI_CASE("127.0.0.1","",12,2,1,6),
 GAI_CASE("127.0.0.1","80x",12,2,1,6),GAI_CASE("127.0.0.1","00080",12,2,1,6),
 GAI_CASE("not-a-numeric-address","80",12,0,1,6),GAI_CASE("256.1.2.3","80",12,2,1,6),GAI_CASE("1::2::3","80",12,10,1,6),
 GAI_CASE("127.0.0.1","80",12,10,1,6),GAI_CASE("::1","80",12,2,1,6),
 GAI_CASE("127.0.0.1","80",12,23,1,6),GAI_CASE("127.0.0.1","80",12,-1,1,6),
 GAI_CASE("127.0.0.1","80",0x4000000c,2,1,6),GAI_CASE("127.0.0.1","80",-1,2,1,6),
 GAI_CASE("127.0.0.1","80",12,2,99,0),GAI_CASE("127.0.0.1","80",12,2,1,17),GAI_CASE("127.0.0.1","80",12,2,2,6),
 GAI_CASE("127.0.0.1","80",12,2,1,255),GAI_CASE("127.0.0.1","80",12,2,0,6),GAI_CASE("127.0.0.1","80",12,2,0,17),
 GAI_CASE("127.0.0.1","80",0x80c,10,1,6),GAI_CASE("127.0.0.1","80",0x90c,10,1,6),
 GAI_CASE("::1","80",0x80c,10,1,6),GAI_CASE("::1","80",0x90c,10,1,6),
 GAI_CASE("127.1","80",12,2,1,6),GAI_CASE("2130706433","80",12,2,1,6),GAI_CASE("0x7f000001","80",12,2,1,6),GAI_CASE("0177.0.0.1","80",12,2,1,6),
 {"127.0.0.1","80",0,0,0,0,1,0},{"::1","80",0,0,0,0,1,0},
 GAI_CASE("127.0.0.1","+80",12,2,1,6),GAI_CASE("127.0.0.1","-0",12,2,1,6),GAI_CASE("127.0.0.1"," 80",12,2,1,6),
 GAI_CASE("127.0.0.1","80 ",12,2,1,6),GAI_CASE("127.0.0.1","99999999999999999999999999999999999999",12,2,1,6),
 GAI_CASE("127.0.0.1","65535",12,2,1,6),GAI_CASE("", "80",12,2,1,6),GAI_CASE("",0,4,2,1,6),
 GAI_CASE(0,"",8,2,1,6),GAI_CASE("127.0.0.1","80",0x10c,2,1,6),GAI_CASE("127.0.0.1","80",0x20c,2,1,6),
 {"127.0.0.1","80",12,2,1,6,0,1},{"127.0.0.1","80",12,2,1,6,0,2},{"127.0.0.1","80",12,2,1,6,0,3},{"127.0.0.1","80",12,2,1,6,0,4}
};
#define GAI_CASE_COUNT (sizeof(gai_cases)/sizeof(gai_cases[0]))
static const int gai_errors[]={0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,-1,INT32_MIN,INT32_MAX};
#define GAI_ERROR_COUNT (sizeof(gai_errors)/sizeof(gai_errors[0]))
static inline struct GaiAddr GaiHints(const struct GaiCase*c){struct GaiAddr h;memset(&h,0,sizeof(h));h.flags=c->flags;h.family=c->family;h.type=c->type;h.protocol=c->protocol;if(c->bad_hint==1)h.length=16;else if(c->bad_hint==2)h.canon=1;else if(c->bad_hint==3)h.address=1;else if(c->bad_hint==4)h.next=1;return h;}
static inline int GaiCompareRows(const void*a,const void*b){return strcmp((const char*)a,(const char*)b);}
static inline int GaiRecord(unsigned index,unsigned mode,int result,int error,const struct GaiAddr*head){
 char rows[32][768];unsigned count=0;const struct GaiAddr*p=head;
 if(result==0){while(p){if(count==32||p->length>128||!p->address)return 0;char*at=rows[count];int n=snprintf(at,768,"%d,%d,%d,%d,%u,",p->flags,p->family,p->type,p->protocol,p->length);if(n<0||n>100)return 0;at+=n;const unsigned char*address=(const unsigned char*)(uintptr_t)p->address;for(unsigned k=0;k<p->length;++k){sprintf(at,"%02x",address[k]);at+=2;}*at++=',';const unsigned char*canon=(const unsigned char*)(uintptr_t)p->canon;if(canon){unsigned k=0;for(;canon[k]&&k<192;++k){sprintf(at,"%02x",canon[k]);at+=2;}if(k==192)return 0;}else *at++='-';*at=0;++count;p=(const struct GaiAddr*)(uintptr_t)p->next;}}
 qsort(rows,count,sizeof(rows[0]),GaiCompareRows);printf("REC %u %u %d %d %d %u",index,mode,result,error,head==0,count);for(unsigned k=0;k<count;++k)printf(" [%s]",rows[k]);putchar('\n');return 1;
}
static inline int GaiErrorRecord(unsigned mode,int code,const char*text){if(!text)return 0;printf("ERR %u %d ",mode,code);unsigned k=0;for(;text[k]&&k<192;++k)printf("%02x",(unsigned char)text[k]);if(k==192)return 0;putchar('\n');return 1;}

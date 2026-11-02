#pragma once
#include <stdint.h>
#include <stddef.h>
#define BSEARCH_MAX_ROWS 33
typedef struct BSearchReport {
 uint64_t abi_before[20],abi_after[20];
 uint64_t count,size;
 int32_t key;
 uint32_t comparator,duplicates,nested;
 int64_t found;
 uint32_t calls,indices[128];
 int32_t results[128],errno_before,errno_after;
 uint32_t nested_calls,nested_found,post_write;
 uint64_t before_canary;
 uint8_t rows[BSEARCH_MAX_ROWS*32];
 uint64_t after_canary;
} BSearchReport;
typedef struct BSearchKey {uint32_t value,padding;BSearchReport*report;} BSearchKey;
#ifdef BSEARCH_DRIVER
#include <stdio.h>
#include <string.h>
static void prepare_bsearch(BSearchReport*r,uint64_t count,uint64_t size,int32_t key,unsigned comparator,unsigned duplicate,unsigned nested){
 memset(r,0,sizeof(*r));r->count=count;r->size=size;r->key=key;r->comparator=comparator;r->duplicates=duplicate;r->nested=nested;r->found=-2;r->before_canary=UINT64_C(0x123456789abcdef0);r->after_canary=UINT64_C(0xfedcba9876543210);
 memset(r->rows,0xa7,sizeof(r->rows));
 for(unsigned n=0;n<BSEARCH_MAX_ROWS;++n){uint32_t value=(duplicate?n/3:n)*2;memcpy(r->rows+n*(size?size:16),&value,4);}
}
static int execute_bsearch_records(void(*invoke)(BSearchReport*)){
 unsigned records=0;const unsigned counts[]={0,1,2,3,4,5,8,16,17,31,33};
 for(unsigned kind=0;kind<4;++kind)for(unsigned duplicate=0;duplicate<2;++duplicate)for(unsigned c=0;c<sizeof(counts)/sizeof(counts[0]);++c){
  unsigned count=counts[c];for(int key=-2;key<=(int)count*2+2;++key){
   BSearchReport r;prepare_bsearch(&r,count,duplicate?32:16,key,kind,duplicate,0);invoke(&r);
   if(memcmp(r.abi_before,r.abi_after,sizeof(r.abi_before))||r.before_canary!=UINT64_C(0x123456789abcdef0)||r.after_canary!=UINT64_C(0xfedcba9876543210)||r.calls>128)return 31;
   printf("RECORD %u %u %u %d %llu %lld %u %d %d %u %u",kind,duplicate,count,key,(unsigned long long)r.size,(long long)r.found,r.calls,r.errno_before,r.errno_after,r.post_write,r.nested_calls);
   for(unsigned n=0;n<r.calls;++n){printf(" %u:%d",r.indices[n],r.results[n]);}putchar('\n');++records;
  }
 }
 for(unsigned kind=0;kind<4;++kind)for(int key=-2;key<=2;key+=2){
  BSearchReport r;prepare_bsearch(&r,7,0,key,kind,0,0);invoke(&r);
  if(memcmp(r.abi_before,r.abi_after,sizeof(r.abi_before))||r.calls>128)return 32;
  printf("ZERO %u %d %lld %u %d",kind,key,(long long)r.found,r.calls,r.errno_after);for(unsigned n=0;n<r.calls;++n)printf(" %u:%d",r.indices[n],r.results[n]);putchar('\n');++records;
 }
 BSearchReport r;prepare_bsearch(&r,17,16,22,2,0,1);invoke(&r);
 if(memcmp(r.abi_before,r.abi_after,sizeof(r.abi_before))||!r.nested_calls||r.nested_found!=1)return 33;
 printf("NESTED %lld %u %u %u\n",(long long)r.found,r.calls,r.nested_calls,r.nested_found);++records;
 printf("BSEARCH-RECORDS-SUCCESS %u\n",records);return 0;
}
#endif

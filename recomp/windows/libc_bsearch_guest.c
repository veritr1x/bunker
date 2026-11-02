#include "libc_bsearch_fixture.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
extern int bsearch_original_comparator(const void*,const void*);
extern int bsearch_poison_comparator(const void*,const void*);
int bsearch_logged_comparator(const void*key,const void*element){
 const BSearchKey*k=key;BSearchReport*r=k->report;uint32_t value;memcpy(&value,element,4);
 int32_t result;
 if(r->comparator&1)result=bsearch_original_comparator(key,element);
 else result=(int32_t)k->value<(int32_t)value?INT32_MIN:(int32_t)k->value>(int32_t)value?INT32_MAX:0;
 unsigned slot=r->calls++;
 if(slot<128){r->indices[slot]=r->size?(uint32_t)(((const uint8_t*)element-r->rows)/r->size):0;r->results[slot]=result;}
 if(r->nested&&slot==0){
  BSearchReport inner;memset(&inner,0,sizeof(inner));inner.count=3;inner.size=16;
  for(uint32_t n=0;n<3;++n){uint32_t v=n*2;memcpy(inner.rows+n*16,&v,4);}
  BSearchKey inner_key={2,0,&inner};
  void*found=bsearch(&inner_key,inner.rows,3,16,bsearch_logged_comparator);
  r->nested_calls=inner.calls;r->nested_found=found==inner.rows+16;
 }
 errno=900+(int)r->calls;
 return result;
}
int bsearch_guest_case(BSearchReport*r){
 BSearchKey key={(uint32_t)r->key,0,r};
 int(*compare)(const void*,const void*)=(r->comparator&2)?bsearch_poison_comparator:bsearch_logged_comparator;
 void*(*volatile search)(const void*,const void*,size_t,size_t,int(*)(const void*,const void*))=bsearch;
 errno=777;r->errno_before=errno;
 void*found=search(&key,r->rows,r->count,r->size,compare);
 r->errno_after=errno;
 r->found=found?(r->size?(int64_t)(((uint8_t*)found-r->rows)/r->size):0):-1;
 if(found){uint32_t tag=0x31415926;memcpy((uint8_t*)found+4,&tag,4);uint32_t actual;memcpy(&actual,(uint8_t*)found+4,4);r->post_write=actual;}
 return 0;
}
uintptr_t bsearch_guest_empty(void){void*(*volatile search)(const void*,const void*,size_t,size_t,int(*)(const void*,const void*))=bsearch;return(uintptr_t)search(0,0,0,UINT64_MAX,0);}
uintptr_t bsearch_guest_raw(uintptr_t key,uintptr_t base,uint64_t count,uint64_t size,uintptr_t compare){return(uintptr_t)bsearch((const void*)key,(const void*)base,count,size,(int(*)(const void*,const void*))compare);}

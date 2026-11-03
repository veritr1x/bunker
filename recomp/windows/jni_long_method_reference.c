#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
extern jlong long_zero(JNIEnv*,jobject,jmethodID,int,uint64_t*);
extern jlong long_mixed(JNIEnv*,jobject,jmethodID,jobject,jlong,jint,int,uint64_t*);
static jlong expected,wide;static jint integer;static unsigned calls;
static const uintptr_t owner=0x12345678,reference=0x87654321;
static jlong body(JNIEnv *e,jobject o,jmethodID m,va_list args){
 (void)e;if((uintptr_t)o!=owner)abort();++calls;va_list copy;va_copy(copy,args);
 if((uintptr_t)m==2){if((uintptr_t)va_arg(copy,jobject)!=reference||va_arg(copy,jlong)!=wide||va_arg(copy,jint)!=integer)abort();}
 else if((uintptr_t)m!=1)abort();va_end(copy);return expected;
}
static jlong direct(JNIEnv *e,jobject o,jmethodID m,...){va_list v;va_start(v,m);jlong result=body(e,o,m,v);va_end(v);return result;}
static jlong array(JNIEnv *e,jobject o,jmethodID m,const jvalue *a){
 (void)e;if((uintptr_t)o!=owner)abort();++calls;
 if((uintptr_t)m==2){if((uintptr_t)a[0].l!=reference||a[1].j!=wide||a[2].i!=integer)abort();}else if((uintptr_t)m!=1)abort();return expected;
}
int main(void){
 struct JNINativeInterface table={0};table.CallLongMethod=direct;table.CallLongMethodV=body;table.CallLongMethodA=array;JNIEnv env=&table;
 const jlong values[]={0,1,-1,INT64_MIN,INT64_MAX,INT64_C(0x100000000),-INT64_C(0x100000001),INT64_C(0x123456789abcdef),-INT64_C(0x123456789abcdef)};
 for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);++i)for(int mixed=0;mixed<2;++mixed)for(int form=0;form<3;++form){
  expected=values[i];wide=values[(i+3)%9];integer=(i&1)?INT32_MIN:INT32_MAX;uint64_t out[2]={0,0};
  jlong result=mixed?long_mixed(&env,(jobject)owner,(jmethodID)2,(jobject)reference,wide,integer,form,out):long_zero(&env,(jobject)owner,(jmethodID)1,form,out);
  if(result!=expected||out[0]!=UINT64_C(0x123456789abcdef0)||out[1]!=((uint64_t)result^UINT64_C(0xfedcba9876543210)))return 2;
  printf("%u %d %d %016llx %016llx\n",i,mixed,form,(unsigned long long)result,(unsigned long long)out[1]);
 }
 return calls==54?0:3;
}

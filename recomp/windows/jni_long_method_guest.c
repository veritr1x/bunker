#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
_Static_assert(sizeof(jlong)==8 && sizeof(jvalue)==8,"Android LP64 JNI long");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallLongMethod)==52*8,"JNI long direct slot");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallLongMethodV)==53*8,"JNI long V slot");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallLongMethodA)==54*8,"JNI long A slot");
static __attribute__((noinline)) jlong long_v(JNIEnv *e,jobject o,jmethodID m,int fixed,...){
 va_list v;va_start(v,fixed);struct {uint64_t a,b,c;int32_t d,f;} before,after;
 __builtin_memcpy(&before,&v,32);jlong result=(*e)->CallLongMethodV(e,o,m,v);__builtin_memcpy(&after,&v,32);va_end(v);
 return before.a==after.a&&before.b==after.b&&before.c==after.c&&before.d==after.d&&before.f==after.f?result:INT64_C(0x445566778899);
}
jlong long_zero(JNIEnv *e,jobject o,jmethodID m,int form,uint64_t *out){
 jlong result;struct {uint64_t before;jvalue args[1];uint64_t after;} data={UINT64_C(0x1122334455667788),{{0}},UINT64_C(0x8877665544332211)};
 if(form==0)result=(*e)->CallLongMethod(e,o,m);else if(form==1)result=long_v(e,o,m,0);else result=(*e)->CallLongMethodA(e,o,m,data.args);
 out[0]=data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)?UINT64_C(0x123456789abcdef0):0;
 out[1]=(uint64_t)result^UINT64_C(0xfedcba9876543210);return result;
}
jlong long_mixed(JNIEnv *e,jobject o,jmethodID m,jobject ref,jlong wide,jint integer,int form,uint64_t *out){
 jlong result;struct {uint64_t before;jvalue args[3];uint64_t after;} data={UINT64_C(0x1122334455667788),{{0},{0},{.j=(jlong)UINT64_C(0xa5a5a5a500000000)}},UINT64_C(0x8877665544332211)};
 data.args[0].l=ref;data.args[1].j=wide;data.args[2].i=integer;
 if(form==0)result=(*e)->CallLongMethod(e,o,m,ref,wide,integer);else if(form==1)result=long_v(e,o,m,0,ref,wide,integer);else result=(*e)->CallLongMethodA(e,o,m,data.args);
 out[0]=data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)&&data.args[0].l==ref&&data.args[1].j==wide&&data.args[2].i==integer&&((uint64_t)data.args[2].j>>32)==UINT64_C(0xa5a5a5a5)?UINT64_C(0x123456789abcdef0):0;
 out[1]=(uint64_t)result^UINT64_C(0xfedcba9876543210);return result;
}

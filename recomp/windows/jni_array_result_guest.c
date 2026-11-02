#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
_Static_assert(sizeof(jvalue)==8,"Android LP64 JNI argument slot");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallObjectMethod)==34*8,"Android object method slots");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallStaticObjectMethod)==114*8,"Android static object method slots");
static jobject via_v(JNIEnv *e,jobject owner,jmethodID method,int stat,...){va_list v;va_start(v,stat);jobject r=stat?(*e)->CallStaticObjectMethodV(e,(jclass)owner,method,v):(*e)->CallObjectMethodV(e,owner,method,v);va_end(v);return r;}
static jobject stack_v(JNIEnv *e,jobject owner,jmethodID method,int stat,int a,int b,int c,int last,...){va_list v;va_start(v,last);jobject r=stat?(*e)->CallStaticObjectMethodV(e,(jclass)owner,method,v):(*e)->CallObjectMethodV(e,owner,method,v);va_end(v);return r;}
jobject array_result_zero(JNIEnv *e,jobject owner,jmethodID method,int mode,int stat,uint64_t *guard){
 struct {uint64_t before;jvalue unused;uint64_t after;} data={UINT64_C(0x1122334455667788),{.j=(jlong)UINT64_C(0xaabbccddeeff0011)},UINT64_C(0x8877665544332211)};
 jobject result;
 if(mode==0)result=stat?(*e)->CallStaticObjectMethod(e,(jclass)owner,method):(*e)->CallObjectMethod(e,owner,method);
 else if(mode==1)result=via_v(e,owner,method,stat);
 else result=stat?(*e)->CallStaticObjectMethodA(e,(jclass)owner,method,mode==2?&data.unused:0):(*e)->CallObjectMethodA(e,owner,method,mode==2?&data.unused:0);
 *guard=data.before==UINT64_C(0x1122334455667788)&&data.unused.j==(jlong)UINT64_C(0xaabbccddeeff0011)&&data.after==UINT64_C(0x8877665544332211)?UINT64_C(0x123456789abcdef0):0;return result;
}
jobject array_result_one(JNIEnv *e,jobject owner,jmethodID method,jobject input,int mode,int stat,uint64_t *guard){
 struct {uint64_t before;jvalue value;uint64_t after;} data={UINT64_C(0x1122334455667788),{.l=input},UINT64_C(0x8877665544332211)};
 jobject result;
 if(mode==0)result=stat?(*e)->CallStaticObjectMethod(e,(jclass)owner,method,input):(*e)->CallObjectMethod(e,owner,method,input);
 else if(mode==1)result=via_v(e,owner,method,stat,input);
 else if(mode==2)result=stat?(*e)->CallStaticObjectMethodA(e,(jclass)owner,method,&data.value):(*e)->CallObjectMethodA(e,owner,method,&data.value);
 else result=stack_v(e,owner,method,stat,1,2,3,4,input);
 *guard=data.before==UINT64_C(0x1122334455667788)&&data.value.l==input&&data.after==UINT64_C(0x8877665544332211)?UINT64_C(0x123456789abcdef0):0;return result;
}

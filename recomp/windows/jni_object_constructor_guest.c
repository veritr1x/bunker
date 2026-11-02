#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
_Static_assert(__builtin_offsetof(struct JNINativeInterface,NewObjectV)==29*8,"actual Android JNI constructor slot");
static jobject via_v(JNIEnv *e,jclass c,jmethodID m,...){va_list v;va_start(v,m);jobject result=(*e)->NewObjectV(e,c,m,v);va_end(v);return result;}
jobject object_construct(JNIEnv *e,jclass c,jmethodID m,int mode,uint64_t *guard){
 struct {uint64_t before;jvalue unused;uint64_t after;} data={UINT64_C(0x1122334455667788),{.j=(jlong)UINT64_C(0x8877665544332211)},UINT64_C(0x123456789abcdef0)};
 jobject result;if(mode==0)result=(*e)->NewObject(e,c,m);else if(mode==1)result=via_v(e,c,m);else result=(*e)->NewObjectA(e,c,m,mode==2?&data.unused:0);
 *guard=(data.before==UINT64_C(0x1122334455667788)&&data.unused.j==(jlong)UINT64_C(0x8877665544332211)&&data.after==UINT64_C(0x123456789abcdef0))?UINT64_C(0xfedcba9876543210):0;
 return result;
}
jclass object_construct_class(JNIEnv *e,jobject o){return (*e)->GetObjectClass(e,o);}

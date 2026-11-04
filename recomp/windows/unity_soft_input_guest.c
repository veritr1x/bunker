#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallVoidMethodV)==62*8,"actual Android void V slot");
static void via_v(JNIEnv*e,jobject o,jmethodID m,...){va_list v;va_start(v,m);(*e)->CallVoidMethodV(e,o,m,v);va_end(v);}
uint64_t soft_hide(JNIEnv*e,jobject o,jmethodID m,jint mode){if(mode==0)(*e)->CallVoidMethod(e,o,m);else if(mode==1)via_v(e,o,m);else (*e)->CallVoidMethodA(e,o,m,0);return UINT64_C(0x123456789abcdef0);}
uint64_t soft_probe(JNIEnv*e,jobject o,jmethodID m,jobject value,jint integer,jint mode){struct{uint64_t before;jvalue args[2];uint64_t after;}a={UINT64_C(0x1122334455667788),{{.j=0},{.j=(jlong)UINT64_C(0xa5a5a5a5a5a5a5a5)}},UINT64_C(0x8877665544332211)};a.args[0].l=value;a.args[1].i=integer;if(mode==0)(*e)->CallVoidMethod(e,o,m,value,integer);else if(mode==1)via_v(e,o,m,value,integer);else (*e)->CallVoidMethodA(e,o,m,a.args);return a.before==UINT64_C(0x1122334455667788)&&a.after==UINT64_C(0x8877665544332211)&&a.args[0].l==value&&a.args[1].i==integer?UINT64_C(0xfedcba9876543210):0;}

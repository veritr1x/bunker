#include <jni.h>
#include <stdarg.h>
#include <stddef.h>
_Static_assert(offsetof(struct JNINativeInterface,CallBooleanMethodV)==38*8,"actual NDK boolean V slot");
static jobject ov(JNIEnv *e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->CallObjectMethodV(e,o,m,a);va_end(a);return r;}
static jboolean bv(JNIEnv *e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jboolean r=(*e)->CallBooleanMethodV(e,o,m,a);va_end(a);return r;}
static jobject split_v(JNIEnv *e,jobject o,jmethodID m,int a,int b,int c,int last,...){va_list v;va_start(v,last);jobject r=(*e)->CallObjectMethodV(e,o,m,v);va_end(v);return r;}
static jobject nv(JNIEnv *e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->NewObjectV(e,c,m,a);va_end(a);return r;}
static void vv(JNIEnv *e,jobject o,jmethodID m,...){va_list a;va_start(a,m);(*e)->CallVoidMethodV(e,o,m,a);va_end(a);}
jobject guest_context_zero(JNIEnv *e,jobject o,jmethodID m,int mode){if(mode==0)return (*e)->CallObjectMethod(e,o,m);if(mode==1)return ov(e,o,m);return (*e)->CallObjectMethodA(e,o,m,0);}
jobject guest_context_one(JNIEnv *e,jobject o,jmethodID m,jobject key,int mode){if(mode==0)return (*e)->CallObjectMethod(e,o,m,key);if(mode==1)return ov(e,o,m,key);jvalue a[1];a[0].l=key;return (*e)->CallObjectMethodA(e,o,m,a);}
jobject guest_context_two(JNIEnv *e,jobject o,jmethodID m,jobject key,jobject fallback,int mode){if(mode==0)return (*e)->CallObjectMethod(e,o,m,key,fallback);if(mode==1)return ov(e,o,m,key,fallback);if(mode==3)return split_v(e,o,m,1,2,3,4,key,fallback);jvalue a[2];a[0].l=key;a[1].l=fallback;return (*e)->CallObjectMethodA(e,o,m,a);}
int guest_context_boolean(JNIEnv *e,jobject o,jmethodID m,jobject key,int mode){if(mode==0)return (*e)->CallBooleanMethod(e,o,m,key);if(mode==1)return bv(e,o,m,key);jvalue a[1];a[0].l=key;return (*e)->CallBooleanMethodA(e,o,m,a);}
jobject guest_context_construct(JNIEnv *e,jclass c,jmethodID m,jobject source,jobject charset,int mode){if(mode==0)return (*e)->NewObject(e,c,m,source,charset);if(mode==1)return nv(e,c,m,source,charset);jvalue a[2];a[0].l=source;a[1].l=charset;return (*e)->NewObjectA(e,c,m,a);}
int guest_context_close(JNIEnv *e,jobject o,jmethodID m,int mode){if(mode==0)(*e)->CallVoidMethod(e,o,m);else if(mode==1)vv(e,o,m);else (*e)->CallVoidMethodA(e,o,m,0);return 0x1234;}

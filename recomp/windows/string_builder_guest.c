#include <jni.h>
#include <stdarg.h>
#include <stddef.h>
_Static_assert(offsetof(struct JNINativeInterface,NewObjectV)==29*8,"NDK NewObjectV slot");
_Static_assert(offsetof(struct JNINativeInterface,CallObjectMethodV)==35*8,"NDK CallObjectMethodV slot");
static jobject new_v(JNIEnv *e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->NewObjectV(e,c,m,a);va_end(a);return r;}
static jobject object_v(JNIEnv *e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->CallObjectMethodV(e,o,m,a);va_end(a);return r;}
static jobject stack_v(JNIEnv *e,jobject o,jmethodID m,int a,int b,int c,int d,int last,...){va_list v;va_start(v,last);jobject r=(*e)->CallObjectMethodV(e,o,m,v);va_end(v);return r;}
jobject guest_builder_new(JNIEnv *e,jclass c,jmethodID m,int mode){
  if(mode==0)return (*e)->NewObject(e,c,m);
  if(mode==1)return new_v(e,c,m);
  return (*e)->NewObjectA(e,c,m,0);
}
jobject guest_builder_append(JNIEnv *e,jobject o,jmethodID m,jstring s,int mode){
  if(mode==0)return (*e)->CallObjectMethod(e,o,m,s);
  if(mode==1)return object_v(e,o,m,s);
  if(mode==3)return stack_v(e,o,m,1,2,3,4,5,s);
  jvalue a[1];a[0].l=s;return (*e)->CallObjectMethodA(e,o,m,a);
}
jobject guest_builder_string(JNIEnv *e,jobject o,jmethodID m,int mode){
  if(mode==0)return (*e)->CallObjectMethod(e,o,m);
  if(mode==1)return object_v(e,o,m);
  return (*e)->CallObjectMethodA(e,o,m,0);
}

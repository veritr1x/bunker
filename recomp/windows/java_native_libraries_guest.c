#include <jni.h>
#include <stdarg.h>
#include <stddef.h>
_Static_assert(offsetof(struct JNINativeInterface,CallObjectMethod)==34*8,"NDK direct object slot");
_Static_assert(offsetof(struct JNINativeInterface,CallObjectMethodV)==35*8,"NDK V object slot");
_Static_assert(offsetof(struct JNINativeInterface,CallObjectMethodA)==36*8,"NDK A object slot");
static jobject invoke_v(JNIEnv*e,jobject loader,jmethodID method,...){
  va_list a;va_start(a,method);jobject result=(*e)->CallObjectMethodV(e,loader,method,a);va_end(a);return result;
}
static jobject stack_v(JNIEnv*e,jobject loader,jmethodID method,int a,int b,int c,int d,int last,...){
  va_list v;va_start(v,last);jobject result=(*e)->CallObjectMethodV(e,loader,method,v);va_end(v);return result;
}
jobject guest_find_library(JNIEnv*e,jobject loader,jmethodID method,jstring name,int mode){
  if(mode==0)return (*e)->CallObjectMethod(e,loader,method,name);
  if(mode==1)return invoke_v(e,loader,method,name);
  if(mode==3)return stack_v(e,loader,method,1,2,3,4,5,name);
  jvalue a[1];a[0].l=name;return (*e)->CallObjectMethodA(e,loader,method,a);
}

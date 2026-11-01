#include <jni.h>
#include <stdarg.h>
#include <stddef.h>
_Static_assert(offsetof(struct JNINativeInterface, CallStaticObjectMethodV) == 115 * 8, "NDK static V slot");
_Static_assert(sizeof(jvalue) == 8, "NDK jvalue width");
static jobject loader_v(JNIEnv *e, jobject c, jmethodID m, ...) {
  va_list a; va_start(a,m); jobject r=(*e)->CallObjectMethodV(e,c,m,a); va_end(a); return r;
}
static jobject name_v(JNIEnv *e, jclass c, jmethodID m, ...) {
  va_list a; va_start(a,m); jobject r=(*e)->CallStaticObjectMethodV(e,c,m,a); va_end(a); return r;
}
jobject guest_invoke_loader(JNIEnv *e, jclass c, jmethodID m, int mode) {
  if(mode==0)return (*e)->CallObjectMethod(e,c,m);
  if(mode==1)return loader_v(e,c,m);
  return (*e)->CallObjectMethodA(e,c,m,0);
}
jobject guest_loader(JNIEnv *e, jclass c, int mode) {
  jclass type=(*e)->GetObjectClass(e,c);
  jmethodID m=(*e)->GetMethodID(e,type,"getClassLoader","()Ljava/lang/ClassLoader;");
  (*e)->DeleteLocalRef(e,type);
  return guest_invoke_loader(e,c,m,mode);
}
jobject guest_name(JNIEnv *e, jclass c, jstring name, jboolean init, jobject loader, int mode) {
  jmethodID m=(*e)->GetStaticMethodID(e,c,"forName","(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;");
  if(mode==0)return (*e)->CallStaticObjectMethod(e,c,m,name,init,loader);
  if(mode==1)return name_v(e,c,m,name,init,loader);
  jvalue args[3];args[0].l=name;args[1].z=init;args[2].l=loader;
  return (*e)->CallStaticObjectMethodA(e,c,m,args);
}

#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
static uint32_t TEST_invokes,TEST_deletes;
JNIEXPORT jobject JNICALL proxy_TEST_native_invoke(JNIEnv *e,jclass c,jlong p,jclass owner,jobject method,jobjectArray args){(void)e;(void)c;(void)p;(void)owner;(void)method;(void)args;++TEST_invokes;return 0;}
JNIEXPORT void JNICALL proxy_TEST_native_delete(JNIEnv *e,jclass c,jlong p){(void)e;(void)c;(void)p;++TEST_deletes;}
uint64_t proxy_TEST_counts(void){return((uint64_t)TEST_deletes<<32)|TEST_invokes;}
jint proxy_TEST_register(JNIEnv *e){
  jclass c=(*e)->FindClass(e,"bitter/jnibridge/JNIBridge");
  JNINativeMethod methods[]={{"invoke","(JLjava/lang/Class;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;",(void*)proxy_TEST_native_invoke},{"delete","(J)V",(void*)proxy_TEST_native_delete}};
  jint r=(*e)->RegisterNatives(e,c,methods,2);(*e)->DeleteLocalRef(e,c);return r;
}
static jobject factory_v(JNIEnv *e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->CallStaticObjectMethodV(e,c,m,a);va_end(a);return r;}
jobject proxy_factory(JNIEnv *e,jlong p,jobjectArray interfaces,jint mode){
  jclass c=(*e)->FindClass(e,"bitter/jnibridge/JNIBridge");jmethodID m=(*e)->GetStaticMethodID(e,c,"newInterfaceProxy","(J[Ljava/lang/Class;)Ljava/lang/Object;");jobject r;
  if(mode==0)r=(*e)->CallStaticObjectMethod(e,c,m,p,interfaces);
  else if(mode==1)r=factory_v(e,c,m,p,interfaces);
  else{jvalue a[2];a[0].j=p;a[1].l=interfaces;r=(*e)->CallStaticObjectMethodA(e,c,m,a);}
  (*e)->DeleteLocalRef(e,c);return r;
}
static void disable_v(JNIEnv *e,jclass c,jmethodID m,...){va_list a;va_start(a,m);(*e)->CallStaticVoidMethodV(e,c,m,a);va_end(a);}
void proxy_disable(JNIEnv *e,jobject proxy,jint mode){
  jclass c=(*e)->FindClass(e,"bitter/jnibridge/JNIBridge");jmethodID m=(*e)->GetStaticMethodID(e,c,"disableInterfaceProxy","(Ljava/lang/Object;)V");
  if(mode==0)(*e)->CallStaticVoidMethod(e,c,m,proxy);
  else if(mode==1)disable_v(e,c,m,proxy);
  else{jvalue a[1];a[0].l=proxy;(*e)->CallStaticVoidMethodA(e,c,m,a);}
  (*e)->DeleteLocalRef(e,c);
}
static void service_v(JNIEnv *e,jobject p,jmethodID m,...){va_list a;va_start(a,m);(*e)->CallVoidMethodV(e,p,m,a);va_end(a);}
void proxy_service(JNIEnv *e,jobject p,jint which,jint mode){
  const char *names[]={"onServiceDisconnected","onBindingDied","onNullBinding","onServiceConnected"};
  const char *signature=which==3?"(Landroid/content/ComponentName;Landroid/os/IBinder;)V":"(Landroid/content/ComponentName;)V";
  jclass c=(*e)->GetObjectClass(e,p);jmethodID m=(*e)->GetMethodID(e,c,names[which],signature);
  if(mode==0)(*e)->CallVoidMethod(e,p,m,0,0);
  else if(mode==1)service_v(e,p,m,0,0);
  else{jvalue a[2];a[0].l=0;a[1].l=0;(*e)->CallVoidMethodA(e,p,m,a);}
  (*e)->DeleteLocalRef(e,c);
}
jobject proxy_object(JNIEnv *e,jobject p,jint which){
  jclass c=(*e)->GetObjectClass(e,p);jobject r=0;
  if(which==0){jmethodID m=(*e)->GetMethodID(e,c,"toString","()Ljava/lang/String;");r=(*e)->CallObjectMethod(e,p,m);}
  if(which==1){jmethodID m=(*e)->GetMethodID(e,c,"equals","(Ljava/lang/Object;)Z");r=(jobject)(uintptr_t)(*e)->CallBooleanMethod(e,p,m,p);}
  if(which==2){jmethodID m=(*e)->GetMethodID(e,c,"hashCode","()I");r=(jobject)(uintptr_t)(*e)->CallIntMethod(e,p,m);}
  (*e)->DeleteLocalRef(e,c);return r;
}

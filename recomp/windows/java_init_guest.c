#include <jni.h>
#include <stdint.h>
jobject java_context_resolver(JNIEnv *e,jobject activity){
  jclass c=(*e)->GetObjectClass(e,activity);
  jmethodID m=(*e)->GetMethodID(e,c,"getContentResolver","()Landroid/content/ContentResolver;");
  jobject out=(*e)->CallObjectMethod(e,activity,m);(*e)->DeleteLocalRef(e,c);return out;
}
jboolean java_google_ar(JNIEnv *e,jobject player){
  jclass c=(*e)->GetObjectClass(e,player);jmethodID m=(*e)->GetMethodID(e,c,"initializeGoogleAr","()Z");
  jboolean out=(*e)->CallBooleanMethod(e,player,m);(*e)->DeleteLocalRef(e,c);return out;
}
uint32_t java_service_interface(JNIEnv *e){
  uint32_t bits=0;jclass service=(*e)->FindClass(e,"android/content/ServiceConnection"),object=(*e)->FindClass(e,"java/lang/Object");
  if(service&&!(*e)->ExceptionCheck(e))bits|=1;
  if(!(*e)->GetSuperclass(e,service))bits|=2;
  if((*e)->IsAssignableFrom(e,service,object)&&!(*e)->IsAssignableFrom(e,object,service))bits|=4;
  jclass cls=(*e)->GetObjectClass(e,service);jmethodID flag=(*e)->GetMethodID(e,cls,"isInterface","()Z");
  if((*e)->CallBooleanMethod(e,service,flag)&&!(*e)->CallBooleanMethod(e,object,flag))bits|=8;
  if((*e)->GetMethodID(e,service,"onServiceConnected","(Landroid/content/ComponentName;Landroid/os/IBinder;)V")&&
     (*e)->GetMethodID(e,service,"onServiceDisconnected","(Landroid/content/ComponentName;)V")&&
     (*e)->GetMethodID(e,service,"onBindingDied","(Landroid/content/ComponentName;)V")&&
     (*e)->GetMethodID(e,service,"onNullBinding","(Landroid/content/ComponentName;)V"))bits|=16;
  jobject bad=(*e)->AllocObject(e,service);jthrowable error=(*e)->ExceptionOccurred(e);(*e)->ExceptionClear(e);
  jclass instantiate=(*e)->FindClass(e,"java/lang/InstantiationException");
  if(!bad&&error&&(*e)->IsInstanceOf(e,error,instantiate))bits|=32;
  if(error)(*e)->DeleteLocalRef(e,error);
  if(!(*e)->GetMethodID(e,service,"<init>","()V")&&(*e)->ExceptionCheck(e))bits|=64;
  (*e)->ExceptionClear(e);
  for(unsigned i=0;i<1;++i){if((*e)->IsInstanceOf(e,0,service))bits|=128;}
  (*e)->DeleteLocalRef(e,service);(*e)->DeleteLocalRef(e,object);(*e)->DeleteLocalRef(e,cls);(*e)->DeleteLocalRef(e,instantiate);
  return bits;
}

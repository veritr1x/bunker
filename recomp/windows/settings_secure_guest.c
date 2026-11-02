#include <jni.h>
#include <stdarg.h>
static jobject secure_v(JNIEnv *e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->CallStaticObjectMethodV(e,c,m,a);va_end(a);return r;}
jobject secure_resolver(JNIEnv *e,jobject activity){
  jclass c=(*e)->GetObjectClass(e,activity);jmethodID m=(*e)->GetMethodID(e,c,"getContentResolver","()Landroid/content/ContentResolver;");
  jobject r=(*e)->CallObjectMethod(e,activity,m);(*e)->DeleteLocalRef(e,c);return r;
}
jobject secure_android_id_constant(JNIEnv *e){
  jclass c=(*e)->FindClass(e,"android/provider/Settings$Secure");
  jfieldID f=(*e)->GetStaticFieldID(e,c,"ANDROID_ID","Ljava/lang/String;");
  jobject r=(*e)->GetStaticObjectField(e,c,f);(*e)->DeleteLocalRef(e,c);return r;
}
jobject secure_get(JNIEnv *e,jobject resolver,jstring name,jint mode){
  jclass c=(*e)->FindClass(e,"android/provider/Settings$Secure");
  jmethodID m=(*e)->GetStaticMethodID(e,c,"getString","(Landroid/content/ContentResolver;Ljava/lang/String;)Ljava/lang/String;");
  jobject r;
  if(mode==0)r=(*e)->CallStaticObjectMethod(e,c,m,resolver,name);
  else if(mode==1)r=secure_v(e,c,m,resolver,name);
  else{jvalue a[2];a[0].l=resolver;a[1].l=name;r=(*e)->CallStaticObjectMethodA(e,c,m,a);}
  (*e)->DeleteLocalRef(e,c);return r;
}

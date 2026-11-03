#include <jni.h>
#include <stdint.h>
static jobject object_v(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->CallObjectMethodV(e,o,m,a);va_end(a);return r;}
static jint int_v(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jint r=(*e)->CallIntMethodV(e,o,m,a);va_end(a);return r;}
static jlong long_v(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jlong r=(*e)->CallLongMethodV(e,o,m,a);va_end(a);return r;}
static jfloat float_v(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jfloat r=(*e)->CallFloatMethodV(e,o,m,a);va_end(a);return r;}
static jboolean bool_v(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jboolean r=(*e)->CallBooleanMethodV(e,o,m,a);va_end(a);return r;}
static jmethodID method(JNIEnv*e,jobject o,const char*name,const char*sig){jclass c=(*e)->GetObjectClass(e,o);jmethodID m=(*e)->GetMethodID(e,c,name,sig);(*e)->DeleteLocalRef(e,c);return m;}
jobject wd_service(JNIEnv*e,jobject context,jstring name){jmethodID m=method(e,context,"getSystemService","(Ljava/lang/String;)Ljava/lang/Object;");return (*e)->CallObjectMethod(e,context,m,name);}
jobject wd_get(JNIEnv*e,jobject manager,jint id,jint form){jmethodID m=method(e,manager,"getDisplay","(I)Landroid/view/Display;");jvalue a[1];a[0].i=id;return form==0?(*e)->CallObjectMethod(e,manager,m,id):form==1?object_v(e,manager,m,id):(*e)->CallObjectMethodA(e,manager,m,a);}
jint wd_int(JNIEnv*e,jobject display,const char*name,jint form){jmethodID m=method(e,display,name,"()I");return form==0?(*e)->CallIntMethod(e,display,m):form==1?int_v(e,display,m):(*e)->CallIntMethodA(e,display,m,0);}
jlong wd_long(JNIEnv*e,jobject display,const char*name,jint form){jmethodID m=method(e,display,name,"()J");return form==0?(*e)->CallLongMethod(e,display,m):form==1?long_v(e,display,m):(*e)->CallLongMethodA(e,display,m,0);}
uint32_t wd_float(JNIEnv*e,jobject display,jint form){jmethodID m=method(e,display,"getRefreshRate","()F");union{jfloat f;uint32_t u;}b;b.f=form==0?(*e)->CallFloatMethod(e,display,m):form==1?float_v(e,display,m):(*e)->CallFloatMethodA(e,display,m,0);return b.u;}
jboolean wd_bool(JNIEnv*e,jobject display,jint form){jmethodID m=method(e,display,"isWideColorGamut","()Z");return form==0?(*e)->CallBooleanMethod(e,display,m):form==1?bool_v(e,display,m):(*e)->CallBooleanMethodA(e,display,m,0);}
jobject wd_metrics(JNIEnv*e){jclass c=(*e)->FindClass(e,"android/util/DisplayMetrics");jmethodID m=(*e)->GetMethodID(e,c,"<init>","()V");jobject r=(*e)->NewObjectA(e,c,m,0);(*e)->DeleteLocalRef(e,c);return r;}
void wd_fill(JNIEnv*e,jobject display,jobject metrics){jmethodID m=method(e,display,"getRealMetrics","(Landroid/util/DisplayMetrics;)V");jvalue a[1];a[0].l=metrics;(*e)->CallVoidMethodA(e,display,m,a);}
jint wd_field(JNIEnv*e,jobject metrics,const char*name){jclass c=(*e)->GetObjectClass(e,metrics);jfieldID f=(*e)->GetFieldID(e,c,name,"I");(*e)->DeleteLocalRef(e,c);return (*e)->GetIntField(e,metrics,f);}
jmethodID wd_window_id(JNIEnv*e,jint native_owner){jclass c=(*e)->FindClass(e,native_owner?"android/app/NativeActivity":"android/app/Activity");jmethodID m=(*e)->GetMethodID(e,c,"getWindowManager","()Landroid/view/WindowManager;");(*e)->DeleteLocalRef(e,c);return m;}
jobject wd_window_manager(JNIEnv*e,jobject activity,jint form){jmethodID m=wd_window_id(e,1);return form==0?(*e)->CallObjectMethod(e,activity,m):form==1?object_v(e,activity,m):(*e)->CallObjectMethodA(e,activity,m,0);}
jobject wd_default_display(JNIEnv*e,jobject manager,jint form){jclass c=(*e)->FindClass(e,"android/view/WindowManager");jmethodID m=(*e)->GetMethodID(e,c,"getDefaultDisplay","()Landroid/view/Display;");(*e)->DeleteLocalRef(e,c);return form==0?(*e)->CallObjectMethod(e,manager,m):form==1?object_v(e,manager,m):(*e)->CallObjectMethodA(e,manager,m,0);}
jboolean wd_instance(JNIEnv*e,jobject object,const char*name){jclass c=(*e)->FindClass(e,name);jboolean result=(*e)->IsInstanceOf(e,object,c);(*e)->DeleteLocalRef(e,c);return result;}
jboolean wd_window_interface(JNIEnv*e){jclass c=(*e)->FindClass(e,"android/view/WindowManager"),meta=(*e)->FindClass(e,"java/lang/Class");jmethodID m=(*e)->GetMethodID(e,meta,"isInterface","()Z");jboolean result=(*e)->CallBooleanMethod(e,c,m);(*e)->DeleteLocalRef(e,meta);(*e)->DeleteLocalRef(e,c);return result;}

#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
uint32_t runnable_interface_metadata(JNIEnv *e){
 jclass runnable=(*e)->FindClass(e,"java/lang/Runnable"),type=(*e)->FindClass(e,"java/lang/Class");
 jmethodID is_interface=(*e)->GetMethodID(e,type,"isInterface","()Z");uint32_t bits=0;
 if(runnable&&(*e)->CallBooleanMethod(e,runnable,is_interface))bits|=1;
 if(!(*e)->GetSuperclass(e,runnable)&&!(*e)->ExceptionCheck(e))bits|=2;
 if((*e)->GetMethodID(e,runnable,"run","()V"))bits|=4;
 if(!(*e)->AllocObject(e,runnable)&&(*e)->ExceptionCheck(e))bits|=8;(*e)->ExceptionClear(e);
 if(!(*e)->NewObjectA(e,runnable,0,0)&&(*e)->ExceptionCheck(e))bits|=16;(*e)->ExceptionClear(e);
 if(!(*e)->GetMethodID(e,runnable,"<init>","()V")&&(*e)->ExceptionCheck(e))bits|=32;(*e)->ExceptionClear(e);
 (*e)->DeleteLocalRef(e,type);(*e)->DeleteLocalRef(e,runnable);return bits;
}
static void run_v(JNIEnv *e,jobject p,jmethodID m,...){va_list a;va_start(a,m);(*e)->CallVoidMethodV(e,p,m,a);va_end(a);}
uint64_t runnable_callback(JNIEnv *e,jobject proxy,jint mode,jboolean interface_method){
 jclass c=interface_method?(*e)->FindClass(e,"java/lang/Runnable"):(*e)->GetObjectClass(e,proxy);
 jmethodID method=(*e)->GetMethodID(e,c,"run","()V");
 struct {uint64_t before;jvalue unused;uint64_t after;}data={UINT64_C(0x1122334455667788),{.j=UINT64_C(0x123456789abcdef0)},UINT64_C(0x8877665544332211)};
 if(mode==0)(*e)->CallVoidMethod(e,proxy,method);
 else if(mode==1)run_v(e,proxy,method);
 else (*e)->CallVoidMethodA(e,proxy,method,&data.unused);
 (*e)->DeleteLocalRef(e,c);
 return data.before==UINT64_C(0x1122334455667788)&&data.unused.j==INT64_C(0x123456789abcdef0)&&data.after==UINT64_C(0x8877665544332211)?UINT64_C(0xfedcba9876543210):0;
}

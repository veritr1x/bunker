#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
uint32_t focus_interface_metadata(JNIEnv *e){
 jclass listener=(*e)->FindClass(e,"android/media/AudioManager$OnAudioFocusChangeListener");if(!listener)return 0;
 uint32_t bits=0;jclass type=(*e)->FindClass(e,"java/lang/Class");jmethodID is_interface=(*e)->GetMethodID(e,type,"isInterface","()Z");
 if((*e)->CallBooleanMethod(e,listener,is_interface))bits|=1;
 if(!(*e)->GetSuperclass(e,listener)&&!(*e)->ExceptionCheck(e))bits|=2;
 jmethodID callback=(*e)->GetMethodID(e,listener,"onAudioFocusChange","(I)V");if(callback)bits|=4;
 if(!(*e)->AllocObject(e,listener)&&(*e)->ExceptionCheck(e))bits|=8;(*e)->ExceptionClear(e);
 if(!(*e)->NewObjectA(e,listener,callback,0)&&(*e)->ExceptionCheck(e))bits|=16;(*e)->ExceptionClear(e);
 (*e)->DeleteLocalRef(e,type);(*e)->DeleteLocalRef(e,listener);return bits;
}
static void callback_v(JNIEnv *e,jobject p,jmethodID m,...){va_list a;va_start(a,m);(*e)->CallVoidMethodV(e,p,m,a);va_end(a);}
uint64_t focus_callback(JNIEnv *e,jobject p,jint value,jint mode){
 jclass c=(*e)->GetObjectClass(e,p);jmethodID m=(*e)->GetMethodID(e,c,"onAudioFocusChange","(I)V");
 struct {uint64_t before;jvalue arg;uint64_t after;}data={UINT64_C(0x1122334455667788),{.j=(jlong)UINT64_C(0xcccccccccccccccc)},UINT64_C(0x8877665544332211)};data.arg.i=value;
 if(mode==0)(*e)->CallVoidMethod(e,p,m,value);else if(mode==1)callback_v(e,p,m,value);else (*e)->CallVoidMethodA(e,p,m,&data.arg);
 (*e)->DeleteLocalRef(e,c);return data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)&&data.arg.i==value?UINT64_C(0xfedcba9876543210):0;
}

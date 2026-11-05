#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
static volatile unsigned counts[8];
__attribute__((constructor,visibility("default"))) void loader_ctor(void){++counts[0];}
__attribute__((destructor,visibility("default"))) void loader_dtor(void){++counts[7];}
__attribute__((visibility("default"))) unsigned loader_count(unsigned i){return i<8?counts[i]:0;}
static jboolean via_v(JNIEnv*e,jobject p,jmethodID m,...){va_list ap;va_start(ap,m);jboolean v=(*e)->CallBooleanMethodV(e,p,m,ap);va_end(ap);return v;}
__attribute__((visibility("default"))) jboolean loader_call(JNIEnv*e,jobject p,jmethodID m,jstring name,unsigned mode){
 if(mode==0)return(*e)->CallBooleanMethod(e,p,m,name);
 if(mode==1)return via_v(e,p,m,name);
 jvalue values[1];values[0].l=name;return(*e)->CallBooleanMethodA(e,p,m,values);
}
#ifndef NO_ONLOAD
static jint env(JavaVM*vm,JNIEnv**e){return(*vm)->GetEnv(vm,(void**)e,JNI_VERSION_1_6);}
__attribute__((visibility("default"))) jint JNI_OnLoad(JavaVM*vm,void*reserved){JNIEnv*e=0;++counts[1];return reserved||env(vm,&e)||!e?JNI_ERR:JNI_VERSION_1_6;}
__attribute__((visibility("default"))) jint loader_bad_onload(JavaVM*vm,void*r){(void)vm;(void)r;++counts[2];return JNI_ERR;}
static jint hook(JavaVM*vm,int which){JNIEnv*e=0;if(env(vm,&e)||!e)return JNI_ERR;jclass c=(*e)->FindClass(e,"test/LoaderHook");jmethodID m=(*e)->GetStaticMethodID(e,c,"onLoad","(I)I");jvalue a[1];a[0].i=which;return(*e)->CallStaticIntMethodA(e,c,m,a)?JNI_VERSION_1_6:JNI_ERR;}
__attribute__((visibility("default"))) jint loader_recursive_onload(JavaVM*vm,void*r){(void)r;++counts[3];return hook(vm,1);}
__attribute__((visibility("default"))) jint loader_parallel_onload(JavaVM*vm,void*r){(void)r;++counts[4];return hook(vm,2);}
__attribute__((visibility("default"))) jint loader_pending_onload(JavaVM*vm,void*r){(void)r;JNIEnv*e=0;++counts[5];if(env(vm,&e)||!e)return JNI_ERR;jclass c=(*e)->FindClass(e,"java/lang/IllegalStateException");(*e)->ThrowNew(e,c,"original OnLoad pending fixture");return JNI_VERSION_1_6;}
__attribute__((visibility("default"))) jint loader_error_onload(JavaVM*vm,void*r){(void)r;JNIEnv*e=0;++counts[6];if(env(vm,&e)||!e)return JNI_ERR;jclass c=(*e)->FindClass(e,"java/lang/OutOfMemoryError");(*e)->ThrowNew(e,c,"original uncaught Error fixture");return JNI_VERSION_1_6;}
#endif

#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
static uint64_t invokes,finalizes,logs,last_handle,last_log,name_ok,last_arguments;
static jobject configured_proxy;static jint configured_mode;static jlong configured_token;
jobject TEST_reflection_invoke(JNIEnv*e,jclass c,jlong handle,jstring name,jobjectArray arguments){
 ++invokes;last_handle=(uint64_t)handle;last_arguments=(uintptr_t)arguments;const char*t=(*e)->GetStringUTFChars(e,name,0);name_ok=t&&t[0]=='r'&&t[1]=='u'&&t[2]=='n'&&!t[3];if(t)(*e)->ReleaseStringUTFChars(e,name,t);
 if(configured_mode){jmethodID m=(*e)->GetStaticMethodID(e,c,"setNativeExceptionOnProxy","(Ljava/lang/Object;JZ)V");(*e)->CallStaticVoidMethod(e,c,m,configured_proxy,configured_token,(int)(configured_mode==2));}
 return 0;
}
void TEST_reflection_finalize(JNIEnv*e,jclass c,jlong handle){(void)e;(void)c;++finalizes;last_handle=(uint64_t)handle;}
void TEST_reflection_log(JNIEnv*e,jclass c,jlong token){(void)e;(void)c;++logs;last_log=(uint64_t)token;}
jint TEST_reflection_register(JNIEnv*e){jclass c=(*e)->FindClass(e,"com/unity3d/player/ReflectionHelper");JNINativeMethod m[]={{"nativeProxyInvoke","(JLjava/lang/String;[Ljava/lang/Object;)Ljava/lang/Object;",(void*)TEST_reflection_invoke},{"nativeProxyFinalize","(J)V",(void*)TEST_reflection_finalize},{"nativeProxyLogJNIInvokeException","(J)V",(void*)TEST_reflection_log}};jint r=(*e)->RegisterNatives(e,c,m,3);(*e)->DeleteLocalRef(e,c);return r;}
uint64_t TEST_reflection_value(int which){return which==0?invokes:which==1?finalizes:which==2?logs:which==3?last_handle:which==4?last_log:which==5?name_ok:last_arguments;}
void TEST_reflection_configure(JNIEnv*e,jobject proxy,jint mode,jlong token){if(configured_proxy)(*e)->DeleteGlobalRef(e,configured_proxy);configured_proxy=proxy?(*e)->NewGlobalRef(e,proxy):0;configured_mode=mode;configured_token=token;}
__attribute__((noinline))static jobject objects_v(JNIEnv*e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jobject o=(*e)->CallStaticObjectMethodV(e,c,m,a);va_end(a);return o;}
jobject helper_two(JNIEnv*e,jclass c,jmethodID m,jobject first,jobject second,int form){jvalue a[2]={{.l=first},{.l=second}};return form==0?(*e)->CallStaticObjectMethod(e,c,m,first,second):form==1?objects_v(e,c,m,first,second):(*e)->CallStaticObjectMethodA(e,c,m,a);}
jobject helper_one(JNIEnv*e,jclass c,jmethodID m,jobject first,int form){jvalue a={.l=first};return form==0?(*e)->CallStaticObjectMethod(e,c,m,first):form==1?objects_v(e,c,m,first):(*e)->CallStaticObjectMethodA(e,c,m,&a);}
jobject proxy_make(JNIEnv*e,jlong handle,jobject interfaces,int array,int form){jclass c=(*e)->FindClass(e,"com/unity3d/player/ReflectionHelper");jmethodID m=(*e)->GetStaticMethodID(e,c,"newProxyInstance",array?"(J[Ljava/lang/Class;)Ljava/lang/Object;":"(JLjava/lang/Class;)Ljava/lang/Object;");jvalue a[2]={{.j=handle},{.l=interfaces}};jobject out=form==0?(*e)->CallStaticObjectMethod(e,c,m,handle,interfaces):form==1?objects_v(e,c,m,handle,interfaces):(*e)->CallStaticObjectMethodA(e,c,m,a);(*e)->DeleteLocalRef(e,c);return out;}
void proxy_run(JNIEnv*e,jobject proxy){jclass c=(*e)->GetObjectClass(e,proxy);jmethodID m=(*e)->GetMethodID(e,c,"run","()V");(*e)->CallVoidMethod(e,proxy,m);(*e)->DeleteLocalRef(e,c);}
void helper_end(JNIEnv*e){jclass c=(*e)->FindClass(e,"com/unity3d/player/ReflectionHelper");jmethodID m=(*e)->GetStaticMethodID(e,c,"endUnityLaunch","()V");(*e)->CallStaticVoidMethod(e,c,m);(*e)->DeleteLocalRef(e,c);}

#include <jni.h>
#include <stdarg.h>
#include <stddef.h>
_Static_assert(offsetof(struct JNINativeInterface,CallStaticVoidMethod)==141*8,"actual NDK static void direct slot");
_Static_assert(offsetof(struct JNINativeInterface,CallStaticVoidMethodV)==142*8,"actual NDK static void V slot");
_Static_assert(offsetof(struct JNINativeInterface,CallStaticVoidMethodA)==143*8,"actual NDK static void A slot");
static void end_v(JNIEnv*env,jclass owner,jmethodID method,...){va_list args;va_start(args,method);(*env)->CallStaticVoidMethodV(env,owner,method,args);va_end(args);}
void reflection_launch_end(JNIEnv*env,jclass owner,jmethodID method,int mode){if(mode==0)(*env)->CallStaticVoidMethod(env,owner,method);else if(mode==1)end_v(env,owner,method);else(*env)->CallStaticVoidMethodA(env,owner,method,NULL);}

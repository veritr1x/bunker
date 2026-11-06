#include <jni.h>
#include <stdarg.h>
static jstring via_v(JNIEnv *env,jclass owner,jmethodID method,...){
  va_list args;va_start(args,method);jstring result=(jstring)(*env)->CallStaticObjectMethodV(env,owner,method,args);va_end(args);return result;
}
jstring log_trace(JNIEnv *env,jthrowable exception,int mode){
  jclass owner=(*env)->FindClass(env,"android/util/Log");
  jmethodID method=(*env)->GetStaticMethodID(env,owner,"getStackTraceString","(Ljava/lang/Throwable;)Ljava/lang/String;");
  jvalue argument;argument.l=exception;
  jstring result=mode==0?(jstring)(*env)->CallStaticObjectMethod(env,owner,method,exception):mode==1?via_v(env,owner,method,exception):(jstring)(*env)->CallStaticObjectMethodA(env,owner,method,&argument);
  (*env)->DeleteLocalRef(env,owner);return result;
}
jstring log_missing_class(JNIEnv *env,int mode){
  (*env)->FindClass(env,"missing/ActualClass");
  jthrowable exception=(*env)->ExceptionOccurred(env);(*env)->ExceptionClear(env);
  jstring result=log_trace(env,exception,mode);(*env)->DeleteLocalRef(env,exception);return result;
}

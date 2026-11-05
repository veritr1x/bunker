#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
_Static_assert(sizeof(jobject)==8&&sizeof(jint)==4&&sizeof(jvalue)==8,"Android LP64 JNI");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallStaticIntMethod)==129*8,"JNI static jint slot");
__attribute__((noinline)) static jint invoke_v(JNIEnv*e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jint r=(*e)->CallStaticIntMethodV(e,c,m,a);va_end(a);return r;}
jint identity_hash(JNIEnv*e,jobject object,int form){
 jclass c=(*e)->FindClass(e,"java/lang/System");if(!c)return 0;
 jmethodID m=(*e)->GetStaticMethodID(e,c,"identityHashCode","(Ljava/lang/Object;)I");jint r=0;
 if(m){if(form==0)r=(*e)->CallStaticIntMethod(e,c,m,object);else if(form==1)r=invoke_v(e,c,m,object);else{jvalue a={.l=object};r=(*e)->CallStaticIntMethodA(e,c,m,&a);}}
 (*e)->DeleteLocalRef(e,c);return r;
}
jint identity_override(JNIEnv*e,jobject o){jclass c=(*e)->GetObjectClass(e,o);jmethodID m=(*e)->GetMethodID(e,c,"hashCode","()I");jint r=(*e)->CallIntMethod(e,o,m);(*e)->DeleteLocalRef(e,c);return r;}

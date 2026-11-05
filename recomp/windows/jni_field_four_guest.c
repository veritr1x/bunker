#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
_Static_assert(sizeof(jvalue)==8&&sizeof(jfieldID)==8,"NDK LP64");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,FromReflectedField)==8*8,"FromReflectedField slot");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,ToReflectedField)==12*8,"ToReflectedField slot");
jobject field_to(JNIEnv*e,jclass c,jfieldID f,jboolean s){return(*e)->ToReflectedField(e,c,f,s);}
jfieldID field_from(JNIEnv*e,jobject f){return(*e)->FromReflectedField(e,f);}
jobject field_get(JNIEnv*e,jobject f,int which){jclass c=(*e)->FindClass(e,"java/lang/reflect/Field");jmethodID m=(*e)->GetMethodID(e,c,which?"getName":"getDeclaringClass",which?"()Ljava/lang/String;":"()Ljava/lang/Class;");jobject r=(*e)->CallObjectMethod(e,f,m);(*e)->DeleteLocalRef(e,c);return r;}
__attribute__((noinline))static jobject four_v(JNIEnv*e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->CallStaticObjectMethodV(e,c,m,a);va_end(a);return r;}
__attribute__((noinline))static jobject four_spill(JNIEnv*e,jclass c,jmethodID m,int p,int q,int r,int last,...){(void)p;(void)q;(void)r;va_list a;va_start(a,last);jobject o=(*e)->CallStaticObjectMethodV(e,c,m,a);va_end(a);return o;}
jobject call_four(JNIEnv*e,jclass c,jmethodID m,jobject a,jstring b,jstring d,jboolean z,int form,uint64_t*guard){
 struct{uint64_t before;jvalue v[4];uint64_t after;} data={UINT64_C(0x1122334455667788),{{.l=a},{.l=b},{.l=d},{.j=(jlong)UINT64_C(0xaabbccddeeff0000)}},UINT64_C(0x8877665544332211)};data.v[3].z=z;jobject o;
 if(form==0)o=(*e)->CallStaticObjectMethod(e,c,m,a,b,d,(int)z);else if(form==1)o=four_v(e,c,m,a,b,d,(int)z);else if(form==2)o=(*e)->CallStaticObjectMethodA(e,c,m,data.v);else o=four_spill(e,c,m,1,2,3,4,a,b,d,(int)z);
 *guard=data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)&&data.v[0].l==a&&data.v[1].l==b&&data.v[2].l==d&&data.v[3].j==(jlong)(UINT64_C(0xaabbccddeeff0000)|z)?UINT64_C(0x123456789abcdef0):0;return o;
}
__attribute__((noinline))static jint three_v(JNIEnv*e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jint r=(*e)->CallStaticIntMethodV(e,c,m,a);va_end(a);return r;}
jint call_three(JNIEnv*e,jclass c,jmethodID m,jobject o,jlong wide,jint n,int form){jvalue a[3]={{.l=o},{.j=wide},{.i=n}};return form==0?(*e)->CallStaticIntMethod(e,c,m,o,wide,n):form==1?three_v(e,c,m,o,wide,n):(*e)->CallStaticIntMethodA(e,c,m,a);}
jint call_wide_four(JNIEnv*e,jclass c,jmethodID m,jlong a,jlong b,jlong d,jlong f,int form){jvalue v[4]={{.j=a},{.j=b},{.j=d},{.j=f}};return form==0?(*e)->CallStaticIntMethod(e,c,m,a,b,d,f):form==1?three_v(e,c,m,a,b,d,f):(*e)->CallStaticIntMethodA(e,c,m,v);}

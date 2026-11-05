#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
static jobject ctor_v(JNIEnv*e,jclass c,jmethodID m,...){va_list v;va_start(v,m);jobject r=(*e)->NewObjectV(e,c,m,v);va_end(v);return r;}
static jobject call_v(JNIEnv*e,jobject o,jmethodID m,...){va_list v;va_start(v,m);jobject r=(*e)->CallObjectMethodV(e,o,m,v);va_end(v);return r;}
jclass sb_find(JNIEnv*e,const char*n){return(*e)->FindClass(e,n);}
jmethodID sb_method(JNIEnv*e,jclass c,const char*n,const char*s){return(*e)->GetMethodID(e,c,n,s);}
jobject sb_ctor(JNIEnv*e,jclass c,jmethodID m,jbyteArray a,jstring n,int form){if(form==0)return(*e)->NewObject(e,c,m,a,n);if(form==1)return ctor_v(e,c,m,a,n);jvalue v[2];v[0].l=a;v[1].l=n;return(*e)->NewObjectA(e,c,m,v);}
jobject sb_encode(JNIEnv*e,jobject o,jmethodID m,jstring n,int form){if(form==0)return(*e)->CallObjectMethod(e,o,m,n);if(form==1)return call_v(e,o,m,n);jvalue v;v.l=n;return(*e)->CallObjectMethodA(e,o,m,&v);}
jbyteArray sb_array(JNIEnv*e,const jbyte*p,jsize n){jbyteArray a=(*e)->NewByteArray(e,n);if(a&&n)(*e)->SetByteArrayRegion(e,a,0,n,p);return a;}
jint sb_read_array(JNIEnv*e,jbyteArray a,jbyte*p,jsize cap){jsize n=(*e)->GetArrayLength(e,a);if(n>cap)return-1;(*e)->GetByteArrayRegion(e,a,0,n,p);return n;}
jint sb_units(JNIEnv*e,jstring s,jchar*p,jsize cap){jsize n=(*e)->GetStringLength(e,s);if(n>cap)return-1;const jchar*v=(*e)->GetStringChars(e,s,0);if(!v)return-1;for(jsize i=0;i<n;++i)p[i]=v[i];(*e)->ReleaseStringChars(e,s,v);return n;}
jint sb_shape(JNIEnv*e,jobject s,jclass c){jclass actual=(*e)->GetObjectClass(e,s);int r=((*e)->IsSameObject(e,actual,c)?1:0)|((*e)->IsInstanceOf(e,s,c)?2:0);(*e)->DeleteLocalRef(e,actual);return r;}
jint sb_push(JNIEnv*e,jint cap){return(*e)->PushLocalFrame(e,cap);}
jobject sb_pop(JNIEnv*e,jobject o){return(*e)->PopLocalFrame(e,o);}
jobject sb_ref(JNIEnv*e,jobject o,int op){if(op==0)return(*e)->NewGlobalRef(e,o);if(op==1){(*e)->DeleteGlobalRef(e,o);return 0;}if(op==2)return(*e)->NewWeakGlobalRef(e,o);if(op==3){(*e)->DeleteWeakGlobalRef(e,o);return 0;}(*e)->DeleteLocalRef(e,o);return 0;}
jint sb_same(JNIEnv*e,jobject a,jobject b){return(*e)->IsSameObject(e,a,b);}
void sb_set(JNIEnv*e,jbyteArray a,const jbyte*p){(*e)->SetByteArrayRegion(e,a,0,1,p);}
jobject sb_empty_ctor(JNIEnv*e,jclass c,jmethodID m){return(*e)->NewObjectA(e,c,m,0);}

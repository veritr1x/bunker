#include <jni.h>
#include <stdarg.h>
static jobject invoke_v(JNIEnv*e,jobject o,jmethodID m,...){va_list v;va_start(v,m);jobject r=(*e)->CallObjectMethodV(e,o,m,v);va_end(v);return r;}
jclass proxy_find(JNIEnv*e,const char*n){return(*e)->FindClass(e,n);}
jmethodID proxy_method(JNIEnv*e,jclass c,const char*n,const char*s){return(*e)->GetMethodID(e,c,n,s);}
jobject proxy_call(JNIEnv*e,jobject o,jmethodID m,jstring url,int form){if(form==0)return(*e)->CallObjectMethod(e,o,m,url);if(form==1)return invoke_v(e,o,m,url);jvalue a;a.l=url;return(*e)->CallObjectMethodA(e,o,m,&a);}
jint proxy_units(JNIEnv*e,jstring s,jchar*p,jsize cap){jsize n=(*e)->GetStringLength(e,s);if(n>cap)return-1;const jchar*v=(*e)->GetStringChars(e,s,0);if(!v)return-1;for(jsize i=0;i<n;++i)p[i]=v[i];(*e)->ReleaseStringChars(e,s,v);return n;}
jint proxy_push(JNIEnv*e,jint cap){return(*e)->PushLocalFrame(e,cap);}
jobject proxy_pop(JNIEnv*e,jobject r){return(*e)->PopLocalFrame(e,r);}
jobject proxy_ref(JNIEnv*e,jobject r,int op){if(op==0)return(*e)->NewGlobalRef(e,r);if(op==1){(*e)->DeleteGlobalRef(e,r);return 0;}if(op==2)return(*e)->NewWeakGlobalRef(e,r);if(op==3){(*e)->DeleteWeakGlobalRef(e,r);return 0;}(*e)->DeleteLocalRef(e,r);return 0;}
jint proxy_same(JNIEnv*e,jobject a,jobject b){return(*e)->IsSameObject(e,a,b);}

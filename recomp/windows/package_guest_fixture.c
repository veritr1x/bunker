#include <jni.h>
#include <stdarg.h>
static jobject ov(JNIEnv *e,jobject o,jmethodID m,...){va_list v;va_start(v,m);jobject r=(*e)->CallObjectMethodV(e,o,m,v);va_end(v);return r;}
static jobject split(JNIEnv *e,jobject o,jmethodID m,int a,int b,int c,int last,...){va_list v;va_start(v,last);jobject r=(*e)->CallObjectMethodV(e,o,m,v);va_end(v);return r;}
static jboolean bv(JNIEnv *e,jobject o,jmethodID m,...){va_list v;va_start(v,m);jboolean r=(*e)->CallBooleanMethodV(e,o,m,v);va_end(v);return r;}
static jobject nv(JNIEnv *e,jclass c,jmethodID m,...){va_list v;va_start(v,m);jobject r=(*e)->NewObjectV(e,c,m,v);va_end(v);return r;}
jobject package_zero(JNIEnv *e,jobject o,jmethodID m,int mode){if(mode==0)return (*e)->CallObjectMethod(e,o,m);if(mode==1)return ov(e,o,m);return (*e)->CallObjectMethodA(e,o,m,0);}
jobject package_two(JNIEnv *e,jobject o,jmethodID m,jstring n,jint f,int mode){if(mode==0)return (*e)->CallObjectMethod(e,o,m,n,f);if(mode==1)return ov(e,o,m,n,f);if(mode==3)return split(e,o,m,1,2,3,4,n,f);jvalue v[2];v[1].j=(jlong)0xccccccccccccccccULL;v[0].l=n;v[1].i=f;return (*e)->CallObjectMethodA(e,o,m,v);}
jobject package_three(JNIEnv *e,jobject o,jmethodID m,jobject a,jint b,jobject c,int mode){if(mode==0)return (*e)->CallObjectMethod(e,o,m,a,b,c);if(mode==1)return ov(e,o,m,a,b,c);if(mode==3)return split(e,o,m,1,2,3,4,a,b,c);jvalue v[3];v[1].j=(jlong)0xccccccccccccccccULL;v[0].l=a;v[1].i=b;v[2].l=c;return (*e)->CallObjectMethodA(e,o,m,v);}
jboolean package_feature(JNIEnv *e,jobject o,jmethodID m,jstring n,int mode){if(mode==0)return (*e)->CallBooleanMethod(e,o,m,n);if(mode==1)return bv(e,o,m,n);jvalue v[1];v[0].l=n;return (*e)->CallBooleanMethodA(e,o,m,v);}
jint package_static_int(JNIEnv *e,jclass c,jfieldID f){return (*e)->GetStaticIntField(e,c,f);}
jobject package_field(JNIEnv *e,jobject o,jfieldID f){return (*e)->GetObjectField(e,o,f);}
jobject package_static_field(JNIEnv *e,jclass c,jfieldID f){return (*e)->GetStaticObjectField(e,c,f);}
jobject package_one(JNIEnv *e,jobject o,jmethodID m,jobject a,int mode){if(mode==0)return (*e)->CallObjectMethod(e,o,m,a);if(mode==1)return ov(e,o,m,a);jvalue v[1];v[0].l=a;return (*e)->CallObjectMethodA(e,o,m,v);}
jobject package_integer(JNIEnv *e,jobject o,jmethodID m,jint a,int mode){if(mode==0)return (*e)->CallObjectMethod(e,o,m,a);if(mode==1)return ov(e,o,m,a);jvalue v[1];v[0].j=(jlong)0xccccccccccccccccULL;v[0].i=a;return (*e)->CallObjectMethodA(e,o,m,v);}
jobject package_construct(JNIEnv *e,jclass c,jmethodID m,jobject a,int mode){if(mode==0)return (*e)->NewObject(e,c,m,a);if(mode==1)return nv(e,c,m,a);jvalue v[1];v[0].l=a;return (*e)->NewObjectA(e,c,m,v);}
jboolean package_empty(JNIEnv *e,jobject o,jmethodID m,int mode){if(mode==0)return (*e)->CallBooleanMethod(e,o,m);if(mode==1)return bv(e,o,m);return (*e)->CallBooleanMethodA(e,o,m,0);}

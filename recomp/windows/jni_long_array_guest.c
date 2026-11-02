#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
_Static_assert(sizeof(jlong)==8 && sizeof(jvalue)==8,"Android LP64 JNI argument slots");
static jobject via_v(JNIEnv *e,jclass owner,jmethodID method,...){va_list v;va_start(v,method);jobject result=(*e)->CallStaticObjectMethodV(e,owner,method,v);va_end(v);return result;}
static jobject split_v(JNIEnv *e,jclass owner,jmethodID method,int a,int b,int c,int last,...){va_list v;va_start(v,last);jobject result=(*e)->CallStaticObjectMethodV(e,owner,method,v);va_end(v);return result;}
static jobject stack_v(JNIEnv *e,jclass owner,jmethodID method,int a,int b,int c,int d,int last,...){va_list v;va_start(v,last);jobject result=(*e)->CallStaticObjectMethodV(e,owner,method,v);va_end(v);return result;}
jobject long_array_static(JNIEnv *e,jclass owner,jmethodID method,jlong value,jobjectArray refs,int mode,uint64_t *guard){
  struct {uint64_t before;jvalue args[2];uint64_t after;} data={UINT64_C(0x123456789abcdef0),{{0},{0}},UINT64_C(0xfedcba9876543210)};
  data.args[0].j=value;data.args[1].l=refs;jobject result;
  if(mode==0)result=(*e)->CallStaticObjectMethod(e,owner,method,value,refs);
  else if(mode==1)result=via_v(e,owner,method,value,refs);
  else if(mode==2)result=(*e)->CallStaticObjectMethodA(e,owner,method,data.args);
  else if(mode==3)result=split_v(e,owner,method,1,2,3,4,value,refs);
  else result=stack_v(e,owner,method,1,2,3,4,5,value,refs);
  *guard=(data.before==UINT64_C(0x123456789abcdef0)&&data.after==UINT64_C(0xfedcba9876543210)&&data.args[0].j==value&&data.args[1].l==refs)?UINT64_C(0x9876543210abcdef):0;return result;
}
jobject long_array_three(JNIEnv *e,jclass owner,jmethodID method,jobject object,jlong value,jobjectArray refs,int mode,uint64_t *guard){
  struct {uint64_t before;jvalue args[3];uint64_t after;} data={UINT64_C(0x1122334455667788),{{0},{0},{0}},UINT64_C(0x8877665544332211)};
  data.args[0].l=object;data.args[1].j=value;data.args[2].l=refs;jobject result;
  if(mode==0)result=(*e)->CallStaticObjectMethod(e,owner,method,object,value,refs);
  else if(mode==1)result=via_v(e,owner,method,object,value,refs);
  else if(mode==2)result=(*e)->CallStaticObjectMethodA(e,owner,method,data.args);
  else if(mode==3)result=split_v(e,owner,method,1,2,3,4,object,value,refs);
  else result=stack_v(e,owner,method,1,2,3,4,5,object,value,refs);
  *guard=(data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)&&data.args[0].l==object&&data.args[1].j==value&&data.args[2].l==refs)?UINT64_C(0x9876543210abcdef):0;return result;
}

_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallStaticVoidMethod)==141*8,"actual Android static void JNI slots");
static void void_v(JNIEnv *e,jclass owner,jmethodID method,...){va_list v;va_start(v,method);(*e)->CallStaticVoidMethodV(e,owner,method,v);va_end(v);}
static void void_stack_v(JNIEnv *e,jclass owner,jmethodID method,int a,int b,int c,int d,int last,...){va_list v;va_start(v,last);(*e)->CallStaticVoidMethodV(e,owner,method,v);va_end(v);}
void long_array_void(JNIEnv *e,jclass owner,jmethodID method,jobject value,int mode,uint64_t *guard){
 struct {uint64_t before;jvalue arg;uint64_t after;} data={UINT64_C(0x123456789abcdef0),{0},UINT64_C(0xfedcba9876543210)};data.arg.l=value;
 if(mode==0)(*e)->CallStaticVoidMethod(e,owner,method,value);
 else if(mode==1)void_v(e,owner,method,value);
 else if(mode==2)(*e)->CallStaticVoidMethodA(e,owner,method,&data.arg);
 else void_stack_v(e,owner,method,1,2,3,4,5,value);
 *guard=(data.before==UINT64_C(0x123456789abcdef0)&&data.after==UINT64_C(0xfedcba9876543210)&&data.arg.l==value)?UINT64_C(0x9876543210abcdef):0;
}

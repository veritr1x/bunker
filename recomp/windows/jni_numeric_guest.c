#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
#define NOINLINE __attribute__((noinline))
_Static_assert(sizeof(jfloat)==4&&sizeof(jdouble)==8&&sizeof(jvalue)==8,"Android scalar widths");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallIntMethod)==49*8,"actual JNI int slots");
_Static_assert(__builtin_offsetof(struct JNINativeInterface,CallFloatMethod)==55*8,"actual JNI float slots");
static uint32_t bits(float value){uint32_t result;__builtin_memcpy(&result,&value,4);return result;}
static float value(uint32_t raw){float result;__builtin_memcpy(&result,&raw,4);return result;}
static uint64_t invoke_v(JNIEnv *e,jobject o,jmethodID m,int stat,int kind,va_list v){
 if(kind==0)return (uint32_t)(stat?(*e)->CallStaticIntMethodV(e,(jclass)o,m,v):(*e)->CallIntMethodV(e,o,m,v));
 if(kind==1)return bits(stat?(*e)->CallStaticFloatMethodV(e,(jclass)o,m,v):(*e)->CallFloatMethodV(e,o,m,v));
 if(kind==2)return (uintptr_t)(stat?(*e)->CallStaticObjectMethodV(e,(jclass)o,m,v):(*e)->CallObjectMethodV(e,o,m,v));
 return (uintptr_t)(*e)->NewObjectV(e,(jclass)o,m,v);
}
#define V_BODY(last) va_list v;va_start(v,last);struct {uint64_t a,b,c;int32_t d,f;} before,after;__builtin_memcpy(&before,&v,32);uint64_t r=invoke_v(e,o,m,stat,kind,v);__builtin_memcpy(&after,&v,32);va_end(v);return before.a==after.a&&before.b==after.b&&before.c==after.c&&before.d==after.d&&before.f==after.f?r:UINT64_MAX
NOINLINE uint64_t numeric_v(JNIEnv *e,jobject o,jmethodID m,int stat,int kind,...){V_BODY(kind);}
NOINLINE uint64_t numeric_v_gp(JNIEnv *e,jobject o,jmethodID m,int stat,int kind,int a,int b,int last,...){V_BODY(last);}
NOINLINE uint64_t numeric_v_fp(JNIEnv *e,jobject o,jmethodID m,int stat,int kind,double a,double b,double c,double d,double f,double g,double h,double last,...){V_BODY(last);}
NOINLINE uint64_t numeric_v_both(JNIEnv *e,jobject o,jmethodID m,int stat,int kind,int a,int b,int last,double f0,double f1,double f2,double f3,double f4,double f5,double f6,double flast,...){V_BODY(flast);}
#define DIRECT(...) do{if(kind==0)result=(uint32_t)(stat?(*e)->CallStaticIntMethod(e,(jclass)o,m,##__VA_ARGS__):(*e)->CallIntMethod(e,o,m,##__VA_ARGS__));else if(kind==1)result=bits(stat?(*e)->CallStaticFloatMethod(e,(jclass)o,m,##__VA_ARGS__):(*e)->CallFloatMethod(e,o,m,##__VA_ARGS__));else if(kind==2)result=(uintptr_t)(stat?(*e)->CallStaticObjectMethod(e,(jclass)o,m,##__VA_ARGS__):(*e)->CallObjectMethod(e,o,m,##__VA_ARGS__));else result=(uintptr_t)(*e)->NewObject(e,(jclass)o,m,##__VA_ARGS__);}while(0)
#define ARRAY() do{if(kind==0)result=(uint32_t)(stat?(*e)->CallStaticIntMethodA(e,(jclass)o,m,data.args):(*e)->CallIntMethodA(e,o,m,data.args));else if(kind==1)result=bits(stat?(*e)->CallStaticFloatMethodA(e,(jclass)o,m,data.args):(*e)->CallFloatMethodA(e,o,m,data.args));else if(kind==2)result=(uintptr_t)(stat?(*e)->CallStaticObjectMethodA(e,(jclass)o,m,data.args):(*e)->CallObjectMethodA(e,o,m,data.args));else result=(uintptr_t)(*e)->NewObjectA(e,(jclass)o,m,data.args);}while(0)
#define VARIANTS(...) do{if(form==0){DIRECT(__VA_ARGS__);}else if(form==1)result=numeric_v(e,o,m,stat,kind,__VA_ARGS__);else if(form==2){ARRAY();}else if(form==3)result=numeric_v_gp(e,o,m,stat,kind,1,2,3,__VA_ARGS__);else if(form==4)result=numeric_v_fp(e,o,m,stat,kind,1,2,3,4,5,6,7,8,__VA_ARGS__);else result=numeric_v_both(e,o,m,stat,kind,1,2,3,1,2,3,4,5,6,7,8,__VA_ARGS__);}while(0)
// mode low4=form, bit4=static, bits5..=int/float/object/constructor result.
uint64_t numeric_mixed(JNIEnv *e,jobject o,jmethodID m,jobject ref,uint64_t packed,int mode,uint64_t *guard){
 struct {uint64_t before;jvalue args[3];uint64_t after;} data={UINT64_C(0x1122334455667788),{{0},{.j=(jlong)UINT64_C(0xabcdef0100000000)},{.j=(jlong)UINT64_C(0xaabbccdd00000000)}},UINT64_C(0x8877665544332211)};
 const uint32_t f=(uint32_t)packed;const int32_t i=(int32_t)(packed>>32);data.args[0].l=ref;data.args[1].f=value(f);data.args[2].i=i;
 int form=mode&15,stat=(mode>>4)&1,kind=mode>>5;uint64_t result;VARIANTS(ref,value(f),i);
 *guard=data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)&&data.args[0].l==ref&&bits(data.args[1].f)==f&&((uint64_t)data.args[1].j>>32)==UINT64_C(0xabcdef01)&&data.args[2].i==i?UINT64_C(0x123456789abcdef0):0;return result;
}
uint64_t numeric_pair(JNIEnv *e,jobject o,jmethodID m,uint64_t packed,jlong wide,int mode,uint64_t *guard){
 struct {uint64_t before;jvalue args[3];uint64_t after;} data={UINT64_C(0x1122334455667788),{{0},{0},{0}},UINT64_C(0x8877665544332211)};
 uint32_t f0=packed,f1=packed>>32;data.args[0].f=value(f0);data.args[1].j=wide;data.args[2].f=value(f1);
 int form=mode&15,stat=(mode>>4)&1,kind=mode>>5;uint64_t result;VARIANTS(value(f0),wide,value(f1));
 *guard=data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)&&bits(data.args[0].f)==f0&&data.args[1].j==wide&&bits(data.args[2].f)==f1?UINT64_C(0x123456789abcdef0):0;return result;
}
uint64_t numeric_zero(JNIEnv *e,jobject o,jmethodID m,int mode,uint64_t *guard){
 int form=mode&15,stat=(mode>>4)&1,kind=mode>>5;uint64_t result;struct {uint64_t before;jvalue args[1];uint64_t after;} data={UINT64_C(0x1122334455667788),{{0}},UINT64_C(0x8877665544332211)};
 if(form==0){DIRECT();}else if(form==1)result=numeric_v(e,o,m,stat,kind);else{ARRAY();}
 *guard=data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)?UINT64_C(0x123456789abcdef0):0;return result;
}
NOINLINE uint32_t numeric_promoted_v(int last,...){va_list v;va_start(v,last);float f=(float)va_arg(v,double);va_end(v);return bits(f);}
uint32_t numeric_promotion(uint32_t raw){return numeric_promoted_v(0,value(raw));}

#include "priority_fixture.h"
#include <jni.h>
#include <errno.h>
#include <pthread.h>
#include <stdarg.h>
#include <sys/resource.h>
#include <unistd.h>
extern void priority_stage(PriorityWorker*,int);
extern int priority_raw(uint64_t,uint64_t);
void priority_poison(uint64_t which,uint64_t who,PriorityRecord *out){out->before=UINT64_C(0x1122334455667788);errno=731;out->value=priority_raw(which,who);out->error=errno;out->after=UINT64_C(0x8877665544332211);}
void priority_native(JNIEnv *env,jclass owner,jint who,jint nice){(void)env;(void)owner;(void)who;(void)nice;}
__attribute__((noinline)) void priority_probe(int which,uint32_t who,int indirect,PriorityRecord *out){
 out->before=UINT64_C(0x1122334455667788);errno=731;
 int (*volatile call)(int,id_t)=getpriority;
 out->value=indirect?call(which,who):getpriority(which,who);
 out->error=errno;out->after=UINT64_C(0x8877665544332211);
}
void *priority_worker(void *pointer){
 PriorityWorker *r=pointer;r->tid=(uint32_t)gettid();r->token=(uintptr_t)pthread_self();
 priority_probe(0,0,0,&r->direct);priority_probe(0,r->tid,1,&r->indirect);
 priority_stage(r,0);return (void*)UINT64_C(0x12345678);
}
static __attribute__((noinline)) void invoke_v(JNIEnv *env,jclass owner,jmethodID method,...){
 va_list args;va_start(args,method);(*env)->CallStaticVoidMethodV(env,owner,method,args);va_end(args);
}
uint64_t priority_jni(JNIEnv *env,jclass owner,jmethodID method,uint32_t tid,int32_t nice,int form){
 struct {uint64_t first;jvalue args[2];uint64_t last;} box={UINT64_C(0x123456789abcdef0),{{.j=(jlong)UINT64_C(0xaabbccdd00000000)},{.j=(jlong)UINT64_C(0x5566778800000000)}},UINT64_C(0xfedcba9876543210)};
 box.args[0].i=(jint)tid;box.args[1].i=nice;
 if(form==0)(*env)->CallStaticVoidMethod(env,owner,method,(jint)tid,nice);
 else if(form==1)invoke_v(env,owner,method,(jint)tid,nice);
 else (*env)->CallStaticVoidMethodA(env,owner,method,box.args);
 return box.first==UINT64_C(0x123456789abcdef0)&&box.last==UINT64_C(0xfedcba9876543210)&&(uint32_t)box.args[0].i==tid&&box.args[1].i==nice&&((uint64_t)box.args[0].j>>32)==UINT64_C(0xaabbccdd)&&((uint64_t)box.args[1].j>>32)==UINT64_C(0x55667788)?UINT64_C(0x7135abcddcba5317):0;
}

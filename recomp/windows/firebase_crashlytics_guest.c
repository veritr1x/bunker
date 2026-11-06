#include "firebase_app_lifetime_guest.c"
static volatile uint64_t *crash_record;
extern void TEST_crash_replay(void);
extern const char *TEST_take_string(void);
#define CE(N) __attribute__((visibility("default"))) void crash_exception##N(const char*s){crash_record[N]++;crash_record[20+N]=hash(s);}
CE(0) CE(1) CE(2) CE(3) CE(4) CE(5) CE(6) CE(7) CE(8) CE(9) CE(10)
#define CA(N) __attribute__((visibility("default"))) void crash_argument##N(const char*s,const char*p){crash_record[11+N]++;crash_record[31+N]=hash(s);crash_record[34+N]=hash(p);}
CA(0) CA(1) CA(2)
__attribute__((visibility("default"))) const char *crash_copy(const char*s){crash_record[15]++;TEST_crash_replay();size_t n=0;while(s[n])++n;char*p=malloc(n+1);for(size_t i=0;i<=n;i++)p[i]=s[i];return p;}
extern void SWIGRegisterExceptionCallbacks_CrashlyticsInternal(Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb);
extern void SWIGRegisterExceptionArgumentCallbacks_CrashlyticsInternal(Acb,Acb,Acb);
extern void SWIGRegisterStringCallback_CrashlyticsInternal(const char*(*)(const char*));
static void(*volatile ce_ptr)(Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb)=SWIGRegisterExceptionCallbacks_CrashlyticsInternal;
static void(*volatile ca_ptr)(Acb,Acb,Acb)=SWIGRegisterExceptionArgumentCallbacks_CrashlyticsInternal;
static void(*volatile cs_ptr)(const char*(*)(const char*))=SWIGRegisterStringCallback_CrashlyticsInternal;
__attribute__((visibility("default"))) void crash_register(uint64_t*r,int form){crash_record=r;
#define EC crash_exception0,crash_exception1,crash_exception2,crash_exception3,crash_exception4,crash_exception5,crash_exception6,crash_exception7,crash_exception8,crash_exception9,crash_exception10
 if(form){ce_ptr(EC);ca_ptr(crash_argument0,crash_argument1,crash_argument2);cs_ptr(crash_copy);}else{SWIGRegisterExceptionCallbacks_CrashlyticsInternal(EC);SWIGRegisterExceptionArgumentCallbacks_CrashlyticsInternal(crash_argument0,crash_argument1,crash_argument2);SWIGRegisterStringCallback_CrashlyticsInternal(crash_copy);}
}
#define PREFIX(N) Firebase_Crashlytics_CSharp_##N
#define DECL0(N) extern void*PREFIX(N)(void);static void*(*volatile p_##N)(void)=PREFIX(N)
#define DECL1(N) extern void PREFIX(N)(void*);static void(*volatile p_##N)(void*)=PREFIX(N)
#define DECLS(N) extern void PREFIX(N)(void*,const char*);static void(*volatile p_##N)(void*,const char*)=PREFIX(N)
DECL0(new_FirebaseCrashlyticsFrame);DECL0(new_StackFrames__SWIG_0);
DECL1(delete_FirebaseCrashlyticsFrame);DECL1(delete_StackFrames);
DECLS(FirebaseCrashlyticsFrame_library_set);DECLS(FirebaseCrashlyticsFrame_symbol_set);DECLS(FirebaseCrashlyticsFrame_fileName_set);DECLS(FirebaseCrashlyticsFrame_lineNumber_set);
DECLS(FirebaseCrashlyticsInternal_Log);DECLS(FirebaseCrashlyticsInternal_SetUserId);
extern void *PREFIX(FirebaseCrashlyticsInternal_GetInstance__SWIG_0)(void*,int32_t*);
static void*(*volatile ci_ptr)(void*,int32_t*)=PREFIX(FirebaseCrashlyticsInternal_GetInstance__SWIG_0);
extern void PREFIX(FirebaseCrashlyticsInternal_SetCustomKey)(void*,const char*,const char*);
static void(*volatile ck_ptr)(void*,const char*,const char*)=PREFIX(FirebaseCrashlyticsInternal_SetCustomKey);
extern void PREFIX(FirebaseCrashlyticsInternal_LogException)(void*,const char*,const char*,void*);
static void(*volatile cx_ptr)(void*,const char*,const char*,void*)=PREFIX(FirebaseCrashlyticsInternal_LogException);
extern void PREFIX(StackFrames_Add)(void*,void*);static void(*volatile add_ptr)(void*,void*)=PREFIX(StackFrames_Add);
extern uint32_t PREFIX(StackFrames_size)(void*);static uint32_t(*volatile size_ptr)(void*)=PREFIX(StackFrames_size);
extern void*PREFIX(StackFrames_getitem)(void*,int32_t);static void*(*volatile item_ptr)(void*,int32_t)=PREFIX(StackFrames_getitem);
__attribute__((visibility("default"))) uintptr_t crash_instance(void*a,int32_t*r,int form){return(uintptr_t)(form?ci_ptr(a,r):PREFIX(FirebaseCrashlyticsInternal_GetInstance__SWIG_0)(a,r));}
__attribute__((visibility("default"))) uintptr_t crash_new(int vector,int form){if(vector)return(uintptr_t)(form?p_new_StackFrames__SWIG_0():PREFIX(new_StackFrames__SWIG_0)());return(uintptr_t)(form?p_new_FirebaseCrashlyticsFrame():PREFIX(new_FirebaseCrashlyticsFrame)());}
__attribute__((visibility("default"))) void crash_delete(void*p,int vector,int form){if(vector){if(form)p_delete_StackFrames(p);else PREFIX(delete_StackFrames)(p);}else{if(form)p_delete_FirebaseCrashlyticsFrame(p);else PREFIX(delete_FirebaseCrashlyticsFrame)(p);}}
__attribute__((visibility("default"))) void crash_set(void*p,const char*s,int field,int form){
#define FIELD(I,N) case I:if(form)p_##N(p,s);else PREFIX(N)(p,s);break
 switch(field){FIELD(0,FirebaseCrashlyticsFrame_library_set);FIELD(1,FirebaseCrashlyticsFrame_symbol_set);FIELD(2,FirebaseCrashlyticsFrame_fileName_set);FIELD(3,FirebaseCrashlyticsFrame_lineNumber_set);}}
__attribute__((visibility("default"))) void crash_add(void*v,void*f,int form){if(form)add_ptr(v,f);else PREFIX(StackFrames_Add)(v,f);}
__attribute__((visibility("default"))) uintptr_t crash_item(void*v,int32_t i,int form){return(uintptr_t)(form?item_ptr(v,i):PREFIX(StackFrames_getitem)(v,i));}
__attribute__((visibility("default"))) uint32_t crash_size(void*v,int form){return form?size_ptr(v):PREFIX(StackFrames_size)(v);}
__attribute__((visibility("default"))) uint64_t crash_probe(void*v,int form){if(form)size_ptr(v);else PREFIX(StackFrames_size)(v);const char*p=TEST_take_string();uint64_t h=hash(p);free((void*)p);return h;}
__attribute__((visibility("default"))) void crash_event(void*i,const char*a,const char*b,void*v,int event,int form){switch(event){
case 0:if(form)p_FirebaseCrashlyticsInternal_Log(i,a);else PREFIX(FirebaseCrashlyticsInternal_Log)(i,a);break;
case 1:if(form)ck_ptr(i,a,b);else PREFIX(FirebaseCrashlyticsInternal_SetCustomKey)(i,a,b);break;
case 2:if(form)p_FirebaseCrashlyticsInternal_SetUserId(i,a);else PREFIX(FirebaseCrashlyticsInternal_SetUserId)(i,a);break;
case 3:if(form)cx_ptr(i,a,b,v);else PREFIX(FirebaseCrashlyticsInternal_LogException)(i,a,b,v);break;}}

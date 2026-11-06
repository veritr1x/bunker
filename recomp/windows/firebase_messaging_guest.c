#include "firebase_crashlytics_guest.c"
static volatile uint64_t *messaging_record;
extern void TEST_messaging_replay(void);
#define ME(N) __attribute__((visibility("default"))) void messaging_exception##N(const char*s){messaging_record[N]++;messaging_record[20+N]=hash(s);}
ME(0) ME(1) ME(2) ME(3) ME(4) ME(5) ME(6) ME(7) ME(8) ME(9) ME(10)
#define MA(N) __attribute__((visibility("default"))) void messaging_argument##N(const char*s,const char*p){messaging_record[11+N]++;messaging_record[31+N]=hash(s);messaging_record[34+N]=hash(p);}
MA(0) MA(1) MA(2)
__attribute__((visibility("default"))) const char*messaging_copy(const char*s){messaging_record[15]++;TEST_messaging_replay();size_t n=0;while(s[n])++n;char*p=malloc(n+1);for(size_t i=0;i<=n;i++)p[i]=s[i];return p;}
extern void SWIGRegisterExceptionCallbacks_FirebaseMessaging(Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb);
extern void SWIGRegisterExceptionArgumentCallbacks_FirebaseMessaging(Acb,Acb,Acb);
extern void SWIGRegisterStringCallback_FirebaseMessaging(const char*(*)(const char*));
static void(*volatile me_ptr)(Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb,Ecb)=SWIGRegisterExceptionCallbacks_FirebaseMessaging;
static void(*volatile ma_ptr)(Acb,Acb,Acb)=SWIGRegisterExceptionArgumentCallbacks_FirebaseMessaging;
static void(*volatile ms_ptr)(const char*(*)(const char*))=SWIGRegisterStringCallback_FirebaseMessaging;
extern void Firebase_Messaging_CSharp_delete_FirebaseMessage(void*);
__attribute__((visibility("default"))) int32_t messaging_message(void*p){messaging_record[16]++;messaging_record[18]=(uintptr_t)p;if(messaging_record[42]>=2)Firebase_Messaging_CSharp_delete_FirebaseMessage(p);return messaging_record[42]==0||messaging_record[42]==3?0:(int32_t)messaging_record[43];}
__attribute__((visibility("default"))) void messaging_token(const char*p){messaging_record[17]++;messaging_record[19]=(uintptr_t)p;messaging_record[41]=hash(p);free((void*)p);}
extern void Firebase_Messaging_CSharp_SetListenerCallbacks(int32_t(*)(void*),void(*)(const char*));
extern void Firebase_Messaging_CSharp_SetListenerCallbacksEnabled(uint32_t,uint32_t);
extern void Firebase_Messaging_CSharp_SendPendingEvents(void);
static void(*volatile ml_ptr)(int32_t(*)(void*),void(*)(const char*))=Firebase_Messaging_CSharp_SetListenerCallbacks;
static void(*volatile en_ptr)(uint32_t,uint32_t)=Firebase_Messaging_CSharp_SetListenerCallbacksEnabled;
static void(*volatile send_ptr)(void)=Firebase_Messaging_CSharp_SendPendingEvents;
static void(*volatile del_ptr)(void*)=Firebase_Messaging_CSharp_delete_FirebaseMessage;
__attribute__((visibility("default"))) void messaging_register(uint64_t*r,int form){messaging_record=r;
#define MEC messaging_exception0,messaging_exception1,messaging_exception2,messaging_exception3,messaging_exception4,messaging_exception5,messaging_exception6,messaging_exception7,messaging_exception8,messaging_exception9,messaging_exception10
if(form){me_ptr(MEC);ma_ptr(messaging_argument0,messaging_argument1,messaging_argument2);ms_ptr(messaging_copy);}else{SWIGRegisterExceptionCallbacks_FirebaseMessaging(MEC);SWIGRegisterExceptionArgumentCallbacks_FirebaseMessaging(messaging_argument0,messaging_argument1,messaging_argument2);SWIGRegisterStringCallback_FirebaseMessaging(messaging_copy);}}
__attribute__((visibility("default"))) void messaging_listener(int mask,int form){int32_t(*m)(void*)=mask&1?messaging_message:0;void(*t)(const char*)=mask&2?messaging_token:0;if(form)ml_ptr(m,t);else Firebase_Messaging_CSharp_SetListenerCallbacks(m,t);}
__attribute__((visibility("default"))) void messaging_enabled(uint32_t m,uint32_t t,int form){if(form)en_ptr(m,t);else Firebase_Messaging_CSharp_SetListenerCallbacksEnabled(m,t);}
__attribute__((visibility("default"))) void messaging_poll(int form){if(form)send_ptr();else Firebase_Messaging_CSharp_SendPendingEvents();}
__attribute__((visibility("default"))) void messaging_delete(void*p,int form){if(form)del_ptr(p);else Firebase_Messaging_CSharp_delete_FirebaseMessage(p);}

#include "socket_transport_cases.h"
#include <signal.h>
extern int64_t guest_socket_operation(int,const uint64_t*,int,int*);
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
static int64_t Invoke(void*context,int op,const uint64_t*arguments,int mode,int*error){(void)context;return guest_socket_operation(op,arguments,mode,error);}
int main(int argc,char**argv){if(argc!=2)return 1;tls_canary=17;signal(SIGPIPE,SIG_IGN);setvbuf(stdout,0,_IONBF,0);uint64_t calls=0,records=0;for(unsigned mode=0;mode<2;++mode){struct NetContext context;memset(&context,0,sizeof(context));context.invoke=Invoke;context.mode=mode;if(!NetScenario(&context,argv[1]))return 2;calls+=context.calls;records+=context.sequence;for(unsigned api=0;api<NET_OPERATION_COUNT;++api)printf("API %u %s %llu\n",mode,net_names[api],(unsigned long long)context.api_calls[api]);}if(tls_canary!=17)return 3;printf("SOCKET-BIONIC-PASS NDK_entry_calls=%llu canonical_records=%llu TLS=%d\n",(unsigned long long)calls,(unsigned long long)records,tls_canary);return 0;}

#include "sensor_service_fixture.h"
extern void port_enter(void*) __attribute__((noreturn));
extern void port_return(void);
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
uint64_t port_native_sp;
static void*test_unavailable_manager(void){++sensor_calls;return NULL;}
static void*real_memset_observed(void*p,int value,size_t bytes){if(p!=(void*)(GLOBAL_BASE+0xe048)||value||bytes!=0x240){die("original actual memset arguments");}++memset_calls;return memset(p,value,bytes);}
void port_fail_fallback(void){die("excluded nonnull-manager continuation");}
void port_emit_native(uint8_t*s){if(case_id==3&&sensor_calls==1){check_effects(1);port_enter((void*)entry_sp);}for(unsigned i=0;i<8;++i){uint32_t type=capability_types[i];if(case_id==2&&type<36){continue;}int result=((int(*)(uint32_t))(uintptr_t)0x704124d8)(type);if(result){die("original capability false with unavailable queue");}++capability_checks;}emit(s,1,0,0);}
static void thunk(uint8_t*p,uintptr_t fn){uint32_t words[]={0x58000050,0xd61f0200};memcpy(p,words,8);put64(p+8,fn);}
int main(int argc,char**argv){native_tls=17;if(native_tls!=17){die("native TLS");}if(argc!=3){die("native arguments");}setup((unsigned)strtoul(argv[2],0,10));port_seeds[30]=(uintptr_t)port_return;
 uint8_t*code=fixed_map(0x70410000,65536);FILE*f=fopen(argv[1],"rb");if(!f||fread(code+0x19f8,1,0x98,f)!=0x98||fread(code+0x24d8,1,0xb4,f)!=0xb4||fgetc(f)!=EOF){die("exact original caller bytes");}fclose(f);
 uint8_t*plt=fixed_map(0x700b0000,65536);memset(plt,0,65536);thunk(plt+0x8440,(uintptr_t)real_memset_observed);thunk(plt+0x8660,(uintptr_t)test_unavailable_manager);
 if(mprotect(code,65536,PROT_READ|PROT_EXEC)||mprotect(plt,65536,PROT_READ|PROT_EXEC)){die("owned code protection");}__builtin___clear_cache((char*)code,(char*)code+65536);__builtin___clear_cache((char*)plt,(char*)plt+65536);port_enter((void*)entry_sp);
}

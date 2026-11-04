#include "unity_fmod_callbacks_fixture.h"
extern void port_enter(void*) __attribute__((noreturn));
extern void port_return(void);
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
uint64_t port_native_sp;
void port_emit_native(uint8_t*s){emit(s,1,0,0);}
int main(int argc,char**argv){native_tls=17;if(native_tls!=17){die("native TLS");}if(argc!=3){die("native arguments");}setup((unsigned)strtoul(argv[2],0,10));port_seeds[30]=(uintptr_t)port_return;uint8_t*code=fixed_map(0x70b30000,65536);FILE*f=fopen(argv[1],"rb");if(!f||fread(code+0xbbfc,1,0x3a4,f)!=0x3a4||fgetc(f)!=EOF){die("exact original callback range");}fclose(f);if(mprotect(code,65536,PROT_READ|PROT_EXEC)){die("code protection");}__builtin___clear_cache((char*)code,(char*)code+65536);port_enter((void*)entry_sp);}

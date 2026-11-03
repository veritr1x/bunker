#include "unity_st2_object_fixture.h"
extern void port_enter(void*) __attribute__((noreturn));
extern void port_return(void);
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
uint64_t port_native_sp;
void port_emit_native(uint8_t*s){emit(s,1,0,0);}
int main(int argc,char**argv){native_tls=17;if(native_tls!=17)die("real native TLS64");if(argc!=4)die("native arguments");FILE*f=fopen(argv[2],"rb");uint64_t global=0;if(!f||fread(&global,1,8,f)!=8)die("original opaque global input");fclose(f);setup((unsigned)strtoul(argv[3],0,10),(uintptr_t)port_return,global);uint8_t*code=fixed_map(0x707b0000,65536);f=fopen(argv[1],"rb");if(!f||fread(code+0xb458,1,0x104,f)!=0x104)die("original complete function bytes");fclose(f);if(mprotect(code,65536,PROT_READ|PROT_EXEC))die("code protection");__builtin___clear_cache((char*)code,(char*)code+65536);port_enter((void*)entry_sp);}

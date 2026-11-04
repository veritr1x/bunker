#include "unity_plane_dispatch_fixture.h"
extern void port_enter(void*) __attribute__((noreturn));
extern void port_return(void);
extern const uint8_t port_fallback_blob[],port_fallback_blob_end[];
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
uint64_t port_native_sp;
void port_emit_native(uint8_t*s){emit(s,1,0,0);}
void port_fail_fallback(void){die("excluded native sqrtf fallback was reached");}
int main(int argc,char**argv){native_tls=17;if(native_tls!=17){die("native TLS");}if(argc!=4){die("native arguments");}setup((unsigned)strtoul(argv[3],0,10),argv[2]);port_seeds[30]=(uintptr_t)port_return;uint8_t*code=fixed_map(0x70ae0000,65536);FILE*f=fopen(argv[1],"rb");if(!f||fread(code+0x31f0,1,0x124c,f)!=0x124c||fgetc(f)!=EOF){die("exact original graph code bytes");}fclose(f);uint8_t*plt=fixed_map(0x700b0000,65536);size_t n=(size_t)(port_fallback_blob_end-port_fallback_blob);if(n>64){die("bounded failure fence");}memcpy(plt+0x9430,port_fallback_blob,n);if(mprotect(code,65536,PROT_READ|PROT_EXEC)||mprotect(plt,65536,PROT_READ|PROT_EXEC)){die("owned code protection");}__builtin___clear_cache((char*)code,(char*)code+65536);__builtin___clear_cache((char*)plt,(char*)plt+65536);port_enter((void*)entry_sp);}

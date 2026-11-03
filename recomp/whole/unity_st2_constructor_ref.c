#include "unity_st2_constructor_fixture.h"
extern void port_enter(void*) __attribute__((noreturn));
extern void port_return(void);
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
uint64_t port_native_sp;
void port_emit_native(uint8_t*s){emit(s,1,0,0);}
int main(int argc,char**argv){
 native_tls=17;if(native_tls!=17)die("real native TLS64");
 if(argc!=6)die("arguments: function PLT global literals case");
 uint64_t global;uint8_t literals[24];load_file(&global,8,argv[3]);load_file(literals,24,argv[4]);
 setup((unsigned)strtoul(argv[5],0,10),(uintptr_t)port_return,global,literals);
 uint8_t*code=fixed_map(0x70750000,65536),*plt=fixed_map(0x700b0000,65536);
 load_file(code+0x20c4,0xf8,argv[1]);load_file(plt+0x8440,16,argv[2]);
 {uint32_t word;memcpy(&word,code+0x2170,4);if(word!=UINT32_C(0x4c008d40))die("actual ST2 word");}
 // Actual original PLT loads this genuine Bionic function pointer. No fabricated return.
 put64(global_page+0xe1e8,(uintptr_t)&memset);protect(global_page,65536,0);
 if(mprotect(code,65536,PROT_READ|PROT_EXEC)||mprotect(plt,65536,PROT_READ|PROT_EXEC))die("original code protection");
 __builtin___clear_cache((char*)code,(char*)code+65536);__builtin___clear_cache((char*)plt,(char*)plt+65536);
 port_enter((void*)entry_sp);
}

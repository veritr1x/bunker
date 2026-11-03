#include "unity_fcvtzu_fixed_fixture.h"
extern void port_enter(void*) __attribute__((noreturn));
extern void port_return(void);
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
uint64_t port_native_sp;
void port_emit_native(uint8_t*s){emit(s,1,0,0);}
int main(int argc,char**argv){
 native_tls=17;if(native_tls!=17){die("real native TLS64");}if(argc!=4){die("arguments:function literal case");}uint8_t literal[4];load_file(literal,4,argv[2]);setup((unsigned)strtoul(argv[3],0,10),(uintptr_t)port_return,literal);
 uint8_t*code=fixed_map(0x70360000,65536);load_file(code+0x2a2c,0x60,argv[1]);uint32_t word;memcpy(&word,code+0x2a44,4);if(word!=0x9e19d809)die("actual FCVTZU fixed word");
 // Only untouched original FDE bytes are executable input; absent zero-branch
 // callee space remains undefined instructions. It cannot return fake success.
 if(mprotect(code,65536,PROT_READ|PROT_EXEC)){die("original code protection");}__builtin___clear_cache((char*)code,(char*)code+65536);port_enter((void*)entry_sp);
}

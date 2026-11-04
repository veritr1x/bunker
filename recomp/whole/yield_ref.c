#include "yield_fixture.h"
extern void port_enter(void*) __attribute__((noreturn));
extern const uint8_t port_capture_blob[],port_capture_blob_end[];
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
uint64_t port_native_sp;
void port_emit_native(uint8_t*s){emit(s,1,0,0);}
int main(int argc,char**argv){
 native_tls=17;if(native_tls!=17){die("real native TLS");}if(argc!=3){die("native arguments");}setup((unsigned)strtoul(argv[2],0,10));
 uint8_t*code=fixed_map(0x70380000,65536);FILE*f=fopen(argv[1],"rb");if(!f||fread(code+0x35e4,1,16,f)!=16||fgetc(f)!=EOF){die("exact original16byte YIELD/branch block");}fclose(f);
 const uint8_t original[16]={0x3f,0x20,0x03,0xd5,0x03,0,0,0x14,0xc4,0,0,0x94,0xe8,0x03,0x1f,0x2a};if(memcmp(code+0x35e4,original,16)){die("original bytes changed");}
 size_t capture=(size_t)(port_capture_blob_end-port_capture_blob);if(capture>0x1000){die("bounded capture seam");}memcpy(code+0x35f4,port_capture_blob,capture);
 if(mprotect(code,65536,PROT_READ|PROT_EXEC)){die("owned code protection");}__builtin___clear_cache((char*)code,(char*)code+65536);port_enter((void*)entry_sp);
}

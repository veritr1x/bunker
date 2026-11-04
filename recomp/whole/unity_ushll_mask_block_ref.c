#include "unity_ushll_mask_block_fixture.h"
extern void port_enter(void*) __attribute__((noreturn));
extern const uint8_t port_capture_blob[],port_capture_blob_end[];
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
uint64_t port_native_sp;
void port_emit_native(uint8_t*s){emit(s,1,0,0);}
int main(int argc,char**argv){native_tls=17;if(native_tls!=17){die("real native TLS");}if(argc!=4){die("native arguments");}setup((unsigned)strtoul(argv[3],0,10),argv[2]);uint8_t*code=fixed_map(0x702b0000,65536);FILE*f=fopen(argv[1],"rb");if(!f||fread(code+0x3e98,1,0xe0,f)!=0xe0||fgetc(f)!=EOF){die("exact original224byte loop");}fclose(f);size_t capture=(size_t)(port_capture_blob_end-port_capture_blob);if(capture>0x1000){die("bounded capture seam");}memcpy(code+0x3f78,port_capture_blob,capture);if(mprotect(code,65536,PROT_READ|PROT_EXEC)){die("owned code protection");}__builtin___clear_cache((char*)code,(char*)code+65536);port_enter((void*)entry_sp);}

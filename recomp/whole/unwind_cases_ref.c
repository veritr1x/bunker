#include "unwind_cases_fixture.h"
static _Thread_local volatile uint64_t native_tls __attribute__((aligned(64)));
extern void port_enter(void*) __attribute__((noreturn));
extern const uint8_t port_capture_blob[],port_capture_blob_end[],port_copy_blob[],port_copy_blob_end[];
uint64_t port_native_sp;
void port_emit_native(uint8_t*s){if(native_tls!=17)die("restored native TLS64");emit(s,1,0,0,expect_abort);}
int main(int argc,char**argv){
 native_tls=17;if(native_tls!=17)die("native TLS64");
 if(argc!=4){die("native arguments");}
 setup((unsigned)strtoul(argv[3],0,10),argv[1],argv[2]);
 uint8_t*ret=fixed_map(FIXTURE_RETURN,65536),*plt=fixed_map(0x820c0000,65536);size_t capture=(size_t)(port_capture_blob_end-port_capture_blob),copy=(size_t)(port_copy_blob_end-port_copy_blob);
 if(capture>4096||copy>512)die("native capture/import bound");memcpy(ret,port_capture_blob,capture);memcpy(plt+0xbb10,port_capture_blob,capture);memcpy(plt+0xb8d0,port_copy_blob,copy);executable(ret,65536);executable(plt,65536);
 ((void(*)(void))(uintptr_t)UINT64_C(0x82624b2c))();
 if(*(const uint8_t*)(uintptr_t)UINT64_C(0x879a8fa0)!=8)die("genuine original size initializer");
 port_enter((void*)(uintptr_t)entry_sp);
}

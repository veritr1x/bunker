#define _GNU_SOURCE
#include <math.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "frinta_function_cases.h"
#include "frinta_function_native.h"
static _Thread_local __attribute__((aligned(64)))volatile unsigned ff_tls_alignment;
static unsigned calls,shape,case_id;static FFModfRecord record;
extern void ff_call(const FFCase*,FFABI*);
static void need(int ok,const char*why){if(!ok){fprintf(stderr,"FRINTA original native case%u: %s\n",case_id,why);exit(91);}}
static float observed_modff(float value,float*integral){calls++;shape+=integral==(float*)(uintptr_t)FF_INTEGRAL;memcpy(&record.input,&value,4);memcpy(&record.before,integral,4);float fraction=modff(value,integral);memcpy(&record.fraction,&fraction,4);memcpy(&record.integral,integral,4);return fraction;}
static void*page(uint64_t address,size_t bytes){void*p=mmap((void*)(uintptr_t)address,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);need(p==(void*)(uintptr_t)address,"owned fixed map");return p;}
int main(int argc,char**argv){
 ff_tls_alignment=17;need(ff_tls_alignment==17,"Bionic real aligned TLS witness");need(argc==2,"owned corpus path");FILE*corpus=fopen(argv[1],"wb");need(corpus!=NULL,"native data corpus");page(FF_BASE,4096);unsigned char*code=page(0x70828000,4096);memcpy(code+0xb78,ff_original_body,sizeof(ff_original_body));unsigned char*plt=page(0x700b8000,4096);uint32_t veneer[]={0x58000050,0xd61f0200};uint64_t callback=(uintptr_t)observed_modff;memcpy(plt+0xf40,veneer,8);memcpy(plt+0xf48,&callback,8);__builtin___clear_cache((char*)code,(char*)code+4096);__builtin___clear_cache((char*)plt,(char*)plt+4096);need(!mprotect(code,4096,PROT_READ|PROT_EXEC)&&!mprotect(plt,4096,PROT_READ|PROT_EXEC),"original code and scoped real-modff PLT veneer RX");
 for(case_id=0;case_id<384;case_id++){
  FFCase sample;ff_setup(&sample,case_id);unsigned char before[64];memcpy(before,(void*)(uintptr_t)FF_BASE,64);calls=shape=0;memset(&record,0,sizeof(record));ff_call(&sample,&sample.after);
  need(calls==1&&shape==1,"exactly one genuine modff invocation and output pointer ABI");need(!memcmp(sample.before.gpr,sample.after.gpr,sizeof(sample.before.gpr))&&!memcmp(sample.before.d,sample.after.d,sizeof(sample.before.d))&&sample.after.LR_good==1,"normal original ABI preserves11GPR/8D/LR");need(sample.after.fpsr==0&&sample.after.fpcr==0,"binary-exact wholefunction has no new exceptions/IXC");need(ff_guards(before),"only the two original output floats written");need(fwrite((void*)(uintptr_t)FF_BASE,1,64,corpus)==64,"native corpus write");ff_print(&sample,calls,shape,&record);
 }
 need(!fclose(corpus),"native corpus close");puts("FRINTA-FUNCTION-BIONIC-PASS cases=384 body=288 genuine_modff=1");return 0;
}

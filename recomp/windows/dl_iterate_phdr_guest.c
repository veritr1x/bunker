#include <link.h>
#include <stddef.h>
#include <stdint.h>
_Static_assert(sizeof(struct dl_phdr_info)==64,"NDK27.2 modern declared info even at target24");
_Static_assert(offsetof(struct dl_phdr_info,dlpi_phdr)==16&&offsetof(struct dl_phdr_info,dlpi_phnum)==24&&offsetof(struct dl_phdr_info,dlpi_adds)==32&&offsetof(struct dl_phdr_info,dlpi_subs)==40&&offsetof(struct dl_phdr_info,dlpi_tls_modid)==48&&offsetof(struct dl_phdr_info,dlpi_tls_data)==56,"actual AArch64 modern info offsets");
_Static_assert(sizeof(Elf64_Phdr)==56,"all original Elf64 program headers");
struct phdr_record {uint64_t addr,phdr,size,adds,subs,tlsid,tlsdata;uint32_t phnum,pad;char name[128];Elf64_Phdr headers[16];};
struct phdr_output {uint64_t before;int32_t count,stop_after,stop_code,action;struct phdr_record records[8];uint64_t after;};
extern void phdr_fixture_control(int);
int phdr_record_callback(struct dl_phdr_info*info,size_t size,void*opaque){
 struct phdr_output*out=opaque;if(size!=64||out->count<0||out->count>=8||info->dlpi_phnum>16)return -99;
 const int index=out->count++;struct phdr_record*r=&out->records[index];r->addr=info->dlpi_addr;r->phdr=(uintptr_t)info->dlpi_phdr;r->size=size;r->adds=info->dlpi_adds;r->subs=info->dlpi_subs;r->tlsid=info->dlpi_tls_modid;r->tlsdata=(uintptr_t)info->dlpi_tls_data;r->phnum=info->dlpi_phnum;
 unsigned n=0;if(info->dlpi_name)while(n+1<sizeof(r->name)&&info->dlpi_name[n]){r->name[n]=info->dlpi_name[n];++n;}r->name[n]=0;
 for(unsigned i=0;i<r->phnum;++i)r->headers[i]=info->dlpi_phdr[i];
 if(index==0&&out->action)phdr_fixture_control(out->action);
 return out->stop_after>0&&out->count>=out->stop_after?out->stop_code:0;
}
int phdr_call(void*opaque,int mode){
 if(mode==0)return dl_iterate_phdr(phdr_record_callback,opaque);
 int(*volatile function)(int(*)(struct dl_phdr_info*,size_t,void*),void*)=dl_iterate_phdr;
 return function(phdr_record_callback,opaque);
}

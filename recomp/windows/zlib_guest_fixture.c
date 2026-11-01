#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#include "zlib_fixture.h"
_Static_assert(sizeof(z_stream)==112 && sizeof(uLong)==8,"NDK z_stream LP64 is required");
static uint32_t allocations,frees,fail_allocate;
static voidpf guest_allocate(voidpf opaque,uInt items,uInt size){
    if((uintptr_t)opaque!=0x12345678)return NULL;
    ++allocations;if(fail_allocate)return NULL;return calloc(items,size);
}
static void guest_free(voidpf opaque,voidpf address){
    if((uintptr_t)opaque!=0x12345678)abort();++frees;free(address);
}
static void capture(struct ZlibFixture *f,z_stream *s,int result,unsigned kind){
    struct ZlibRecord *r=&f->records[f->count++];
    r->result=result;r->kind=kind;r->avail_in=s->avail_in;r->avail_out=s->avail_out;
    r->total_in=s->total_in;r->total_out=s->total_out;r->adler=s->adler;
    r->input_offset=s->next_in?(uintptr_t)s->next_in-f->input:UINT64_MAX;
    r->output_offset=s->next_out?(uintptr_t)s->next_out-f->output:UINT64_MAX;
    r->data_type=s->data_type;r->message=s->msg!=NULL;r->state=s->state!=NULL;r->padding=0;
}
int guest_inflate(struct ZlibFixture *f){
    z_stream s;memset(&s,0,sizeof(s));f->count=0;allocations=frees=0;fail_allocate=(f->options&2)!=0;
    s.next_in=(Bytef*)(uintptr_t)f->input;s.next_out=(Bytef*)(uintptr_t)f->output;
    if(f->options&3){s.zalloc=guest_allocate;s.zfree=guest_free;s.opaque=(void*)0x12345678;}
    int result;
    if(!zlibVersion()||zlibVersion()[0]!='1')return -999;
    if(f->options&16)result=inflateInit_(&s,ZLIB_VERSION,sizeof(s));
    else result=inflateInit2_(&s,f->window_bits,ZLIB_VERSION,sizeof(s));
    capture(f,&s,result,0);
    if(result==Z_OK){
      if(f->options&32){
        unsigned char *memory=s.zalloc(s.opaque,3,7);if(!memory)return -998;
        memset(memory,0x39,21);
        s.zfree(s.opaque,memory);
      }
      if(f->options&8){s.total_in=UINT64_C(1)<<32;s.total_out=UINT64_C(1)<<32;}
      uint64_t supplied=0,produced=0;
      while(f->count<ZLIB_RECORDS-1){
        if(!s.avail_in){uint64_t n=f->input_size-supplied;if(n>f->input_chunk)n=f->input_chunk;s.avail_in=(uInt)n;supplied+=n;}
        uint64_t available=f->output_size-produced;if(available>f->output_chunk)available=f->output_chunk;
        s.avail_out=(uInt)available;
        uint32_t before_in=s.avail_in,before_out=s.avail_out;
        result=inflate(&s,f->flush);produced+=before_out-s.avail_out;capture(f,&s,result,1);
        if(result==Z_STREAM_END||(result!=Z_OK&&result!=Z_BUF_ERROR))break;
        if(before_in==s.avail_in&&before_out==s.avail_out)break;
      }
      int ended=inflateEnd(&s);capture(f,&s,ended,2);if(ended!=Z_OK)return ended;
    }
    f->allocations=allocations;f->frees=frees;return result;
}

#include <stdio.h>
#include <errno.h>
#include <stdint.h>
struct StreamResult {uint64_t stream;int32_t result,error;uint64_t count;uint8_t byte,next;};
void stream_constants(int32_t *out){out[0]=_IOFBF;out[1]=_IOLBF;out[2]=_IONBF;out[3]=sizeof(size_t);out[4]=sizeof(FILE*);out[5]=EOF;}
void stream_open(const char *path,int unbuffered,struct StreamResult *out){
 FILE *stream=fopen(path,"rb");out->stream=(uintptr_t)stream;errno=123;
 out->result=unbuffered?setvbuf(stream,NULL,_IONBF,0):0;out->error=errno;
 out->count=fread(&out->byte,1,1,stream);
}
void stream_read(struct StreamResult *out){out->count=fread(&out->byte,1,2,(FILE*)(uintptr_t)out->stream);out->error=errno;}
uint64_t stream_seek(struct StreamResult *out,int64_t offset){errno=123;int result=fseek((FILE*)(uintptr_t)out->stream,offset,SEEK_SET);return (uint64_t)(uint32_t)result|((uint64_t)(uint32_t)errno<<32);}
uint64_t stream_mode(uint64_t stream,uint64_t buffer,int mode,uint64_t size){errno=123;int result=setvbuf((FILE*)(uintptr_t)stream,(char*)(uintptr_t)buffer,mode,size);return (uint64_t)(uint32_t)result|((uint64_t)(uint32_t)errno<<32);}
uint64_t stream_close(uint64_t stream){errno=123;int result=fclose((FILE*)(uintptr_t)stream);return(uint64_t)(uint32_t)result|((uint64_t)(uint32_t)errno<<32);}

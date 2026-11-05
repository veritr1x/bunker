#include <stdint.h>
#include <stddef.h>
#include <EGL/egl.h>
#include <GLES3/gl32.h>
_Static_assert(sizeof(GLintptr)==8&&sizeof(GLsizeiptr)==8&&sizeof(void*)==8,"Android LP64 mapping ABI");
_Static_assert(sizeof(GLenum)==4&&sizeof(GLbitfield)==4&&sizeof(GLboolean)==1,"GLES scalar widths");
static PFNGLMAPBUFFERRANGEPROC volatile indirect_map=glMapBufferRange;
static PFNGLUNMAPBUFFERPROC volatile indirect_unmap=glUnmapBuffer;
static PFNGLFLUSHMAPPEDBUFFERRANGEPROC volatile indirect_flush=glFlushMappedBufferRange;
void gm_resolve(uint64_t*out){out[0]=(uintptr_t)eglGetProcAddress("glMapBufferRange");out[1]=(uintptr_t)eglGetProcAddress("glUnmapBuffer");out[2]=(uintptr_t)eglGetProcAddress("glFlushMappedBufferRange");}
uint64_t gm_map(unsigned mode,uint64_t procedure,GLenum target,GLintptr offset,GLsizeiptr length,GLbitfield access){
 if(mode==0)return(uintptr_t)glMapBufferRange(target,offset,length,access);
 if(mode==1)return(uintptr_t)indirect_map(target,offset,length,access);
 return(uintptr_t)((PFNGLMAPBUFFERRANGEPROC)(uintptr_t)procedure)(target,offset,length,access);
}
uint64_t gm_unmap(unsigned mode,uint64_t procedure,GLenum target){
 if(mode==0)return glUnmapBuffer(target);
 if(mode==1)return indirect_unmap(target);
 return((PFNGLUNMAPBUFFERPROC)(uintptr_t)procedure)(target);
}
uint64_t gm_flush(unsigned mode,uint64_t procedure,GLenum target,GLintptr offset,GLsizeiptr length){
 if(mode==0)glFlushMappedBufferRange(target,offset,length);
 else if(mode==1)indirect_flush(target,offset,length);
 else((PFNGLFLUSHMAPPEDBUFFERRANGEPROC)(uintptr_t)procedure)(target,offset,length);
 return UINT64_C(0xf123456789abcdef);
}
uint64_t gm_copy(uint64_t mapped,const unsigned char*source,uint64_t count){volatile unsigned char*out=(volatile unsigned char*)(uintptr_t)mapped;for(uint64_t i=0;i<count;i++)out[i]=source[i];return count;}
uint64_t gm_read(uint64_t mapped,unsigned char*out,uint64_t count){const volatile unsigned char*in=(const volatile unsigned char*)(uintptr_t)mapped;for(uint64_t i=0;i<count;i++)out[i]=in[i];return count;}
void gm_draw(void){glDrawArrays(GL_TRIANGLES,0,3);}

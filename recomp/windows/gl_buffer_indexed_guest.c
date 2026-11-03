#include <stdint.h>
#include <EGL/egl.h>
#include <GLES3/gl31.h>
uint64_t gl_buffer_indexed_resolve(void){return (uint64_t)eglGetProcAddress("glBindBufferBase");}
void gl_buffer_indexed_direct(uint32_t target,uint32_t index,uint32_t buffer){glBindBufferBase(target,index,buffer);}
void gl_buffer_indexed_procedure(uint32_t target,uint32_t index,uint32_t buffer){
  PFNGLBINDBUFFERBASEPROC bind=(PFNGLBINDBUFFERBASEPROC)eglGetProcAddress("glBindBufferBase");
  bind(target,index,buffer);
}
void gl_buffer_indexed_pointer(uint64_t procedure,uint32_t target,uint32_t index,uint32_t buffer){
  ((PFNGLBINDBUFFERBASEPROC)procedure)(target,index,buffer);
}
void gl_buffer_indexed_create(uint32_t *buffer,int64_t bytes){
  PFNGLGENBUFFERSPROC gen=(PFNGLGENBUFFERSPROC)eglGetProcAddress("glGenBuffers");
  PFNGLBINDBUFFERPROC bind=(PFNGLBINDBUFFERPROC)eglGetProcAddress("glBindBuffer");
  PFNGLBUFFERDATAPROC data=(PFNGLBUFFERDATAPROC)eglGetProcAddress("glBufferData");
  gen(1,buffer);bind(GL_ARRAY_BUFFER,*buffer);data(GL_ARRAY_BUFFER,bytes,0,GL_DYNAMIC_DRAW);
}
void gl_buffer_indexed_delete(uint32_t buffer){
  PFNGLDELETEBUFFERSPROC remove=(PFNGLDELETEBUFFERSPROC)eglGetProcAddress("glDeleteBuffers");
  remove(1,&buffer);
}

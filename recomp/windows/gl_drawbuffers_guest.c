#include <stdint.h>
#include <stddef.h>
#include <EGL/egl.h>
#include <GLES3/gl32.h>
_Static_assert(sizeof(GLsizei)==4&&sizeof(GLenum)==4&&sizeof(void*)==8,"AndroidLP64 DrawBuffers ABI");
static PFNGLDRAWBUFFERSPROC volatile indirect_draw=glDrawBuffers;
uint64_t db_resolve(void){return(uintptr_t)eglGetProcAddress("glDrawBuffers");}
uint64_t db_call(unsigned mode,uint64_t procedure,GLsizei n,const GLenum*buffers){if(mode==0)glDrawBuffers(n,buffers);else if(mode==1)indirect_draw(n,buffers);else((PFNGLDRAWBUFFERSPROC)(uintptr_t)procedure)(n,buffers);return UINT64_C(0xf123456789abcdef);}

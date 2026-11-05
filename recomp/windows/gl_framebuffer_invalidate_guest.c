#define GL_GLEXT_PROTOTYPES 1
#include <stdint.h>
#include <GLES3/gl32.h>
#include <GLES2/gl2ext.h>
#include <EGL/egl.h>
_Static_assert(sizeof(GLenum)==4&&sizeof(GLsizei)==4&&sizeof(void*)==8,"AndroidLP64 framebuffer hint ABI");
static PFNGLINVALIDATEFRAMEBUFFERPROC volatile invalidate=glInvalidateFramebuffer;
static PFNGLDISCARDFRAMEBUFFEREXTPROC volatile discard=glDiscardFramebufferEXT;
void fi_resolve(uint64_t*out){out[0]=(uintptr_t)eglGetProcAddress("glInvalidateFramebuffer");out[1]=(uintptr_t)eglGetProcAddress("glDiscardFramebufferEXT");}
uint64_t fi_call(unsigned extension,unsigned mode,uint64_t procedure,GLenum target,GLsizei count,const GLenum*attachments){if(extension){if(mode==0)glDiscardFramebufferEXT(target,count,attachments);else if(mode==1)discard(target,count,attachments);else((PFNGLDISCARDFRAMEBUFFEREXTPROC)(uintptr_t)procedure)(target,count,attachments);}else{if(mode==0)glInvalidateFramebuffer(target,count,attachments);else if(mode==1)invalidate(target,count,attachments);else((PFNGLINVALIDATEFRAMEBUFFERPROC)(uintptr_t)procedure)(target,count,attachments);}return UINT64_C(0xf123456789abcdef);}

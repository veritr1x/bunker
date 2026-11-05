#include <stdint.h>
#include <GLES3/gl32.h>
#include <EGL/egl.h>
_Static_assert(sizeof(GLsync)==8&&sizeof(GLuint64)==8&&sizeof(GLenum)==4&&sizeof(GLbitfield)==4,"AndroidLP64 sync ABI");
static PFNGLFENCESYNCPROC volatile fence=glFenceSync;
static PFNGLCLIENTWAITSYNCPROC volatile wait_sync=glClientWaitSync;
static PFNGLDELETESYNCPROC volatile delete_sync=glDeleteSync;
void gs_resolve(uint64_t*out){out[0]=(uintptr_t)eglGetProcAddress("glFenceSync");out[1]=(uintptr_t)eglGetProcAddress("glClientWaitSync");out[2]=(uintptr_t)eglGetProcAddress("glDeleteSync");}
uint64_t gs_fence(unsigned mode,uint64_t procedure,GLenum condition,GLbitfield flags){if(mode==0)return(uintptr_t)glFenceSync(condition,flags);if(mode==1)return(uintptr_t)fence(condition,flags);return(uintptr_t)((PFNGLFENCESYNCPROC)(uintptr_t)procedure)(condition,flags);}
uint64_t gs_wait(unsigned mode,uint64_t procedure,uint64_t handle,GLbitfield flags,GLuint64 timeout){if(mode==0)return glClientWaitSync((GLsync)(uintptr_t)handle,flags,timeout);if(mode==1)return wait_sync((GLsync)(uintptr_t)handle,flags,timeout);return((PFNGLCLIENTWAITSYNCPROC)(uintptr_t)procedure)((GLsync)(uintptr_t)handle,flags,timeout);}
uint64_t gs_delete(unsigned mode,uint64_t procedure,uint64_t handle){if(mode==0)glDeleteSync((GLsync)(uintptr_t)handle);else if(mode==1)delete_sync((GLsync)(uintptr_t)handle);else((PFNGLDELETESYNCPROC)(uintptr_t)procedure)((GLsync)(uintptr_t)handle);return UINT64_C(0xf123456789abcdef);}

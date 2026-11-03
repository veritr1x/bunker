#include <GLES3/gl31.h>
#include <EGL/egl.h>
#include <stdint.h>
void internalformat_direct(GLenum target,GLenum format,GLenum pname,GLsizei capacity,GLint*out){glGetInternalformativ(target,format,pname,capacity,out);}
void internalformat_indirect(GLenum target,GLenum format,GLenum pname,GLsizei capacity,GLint*out){PFNGLGETINTERNALFORMATIVPROC volatile fn=glGetInternalformativ;fn(target,format,pname,capacity,out);}
uintptr_t internalformat_procedure(GLenum target,GLenum format,GLenum pname,GLsizei capacity,GLint*out){PFNGLGETINTERNALFORMATIVPROC fn=(PFNGLGETINTERNALFORMATIVPROC)eglGetProcAddress("glGetInternalformativ");if(fn)fn(target,format,pname,capacity,out);return(uintptr_t)fn;}

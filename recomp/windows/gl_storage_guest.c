#include <GLES3/gl32.h>
#include <EGL/egl.h>
#include <stdint.h>
void st_2d(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h){glTexStorage2D(t,n,f,w,h);}
void st_2d_indirect(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h){PFNGLTEXSTORAGE2DPROC volatile fn=glTexStorage2D;fn(t,n,f,w,h);}
void st_3d(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h,GLsizei d){glTexStorage3D(t,n,f,w,h,d);}
void st_3d_indirect(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h,GLsizei d){PFNGLTEXSTORAGE3DPROC volatile fn=glTexStorage3D;fn(t,n,f,w,h,d);}
void st_2ms(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h,GLboolean fixed){glTexStorage2DMultisample(t,n,f,w,h,fixed);}
void st_2ms_indirect(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h,GLboolean fixed){PFNGLTEXSTORAGE2DMULTISAMPLEPROC volatile fn=glTexStorage2DMultisample;fn(t,n,f,w,h,fixed);}
void st_3ms(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h,GLsizei d,GLboolean fixed){glTexStorage3DMultisample(t,n,f,w,h,d,fixed);}
void st_3ms_indirect(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h,GLsizei d,GLboolean fixed){PFNGLTEXSTORAGE3DMULTISAMPLEPROC volatile fn=glTexStorage3DMultisample;fn(t,n,f,w,h,d,fixed);}
uintptr_t st_procedure(GLenum t,GLsizei n,GLenum f,GLsizei w,GLsizei h){PFNGLTEXSTORAGE2DPROC fn=(PFNGLTEXSTORAGE2DPROC)eglGetProcAddress("glTexStorage2D");if(fn)fn(t,n,f,w,h);return(uintptr_t)fn;}

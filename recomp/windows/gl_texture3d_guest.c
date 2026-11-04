#include <GLES3/gl32.h>
#include <EGL/egl.h>
#include <stdint.h>
void tex3_image(GLenum t,GLint l,GLint i,GLsizei w,GLsizei h,GLsizei d,GLint b,GLenum f,GLenum ty,const void*p){glTexImage3D(t,l,i,w,h,d,b,f,ty,p);}
void tex3_image_indirect(GLenum t,GLint l,GLint i,GLsizei w,GLsizei h,GLsizei d,GLint b,GLenum f,GLenum ty,const void*p){PFNGLTEXIMAGE3DPROC volatile fn=glTexImage3D;fn(t,l,i,w,h,d,b,f,ty,p);}
void tex3_sub(GLenum t,GLint l,GLint x,GLint y,GLint z,GLsizei w,GLsizei h,GLsizei d,GLenum f,GLenum ty,const void*p){glTexSubImage3D(t,l,x,y,z,w,h,d,f,ty,p);}
void tex3_sub_indirect(GLenum t,GLint l,GLint x,GLint y,GLint z,GLsizei w,GLsizei h,GLsizei d,GLenum f,GLenum ty,const void*p){PFNGLTEXSUBIMAGE3DPROC volatile fn=glTexSubImage3D;fn(t,l,x,y,z,w,h,d,f,ty,p);}
void tex3_compressed(GLenum t,GLint l,GLint x,GLint y,GLint z,GLsizei w,GLsizei h,GLsizei d,GLenum f,GLsizei n,const void*p){glCompressedTexSubImage3D(t,l,x,y,z,w,h,d,f,n,p);}
void tex3_compressed_indirect(GLenum t,GLint l,GLint x,GLint y,GLint z,GLsizei w,GLsizei h,GLsizei d,GLenum f,GLsizei n,const void*p){PFNGLCOMPRESSEDTEXSUBIMAGE3DPROC volatile fn=glCompressedTexSubImage3D;fn(t,l,x,y,z,w,h,d,f,n,p);}
uintptr_t tex3_procedure(GLenum t,GLint l,GLint x,GLint y,GLint z,GLsizei w,GLsizei h,GLsizei d,GLenum f,GLenum ty,const void*p){PFNGLTEXSUBIMAGE3DPROC fn=(PFNGLTEXSUBIMAGE3DPROC)eglGetProcAddress("glTexSubImage3D");if(fn)fn(t,l,x,y,z,w,h,d,f,ty,p);return(uintptr_t)fn;}

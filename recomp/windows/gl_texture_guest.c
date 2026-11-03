#include <GLES3/gl31.h>
// These original NDK wrappers exercise AAPCS64, including the ninth GP argument
// on the stack and the independent S0 argument of glTexParameterf.
void tx_bind(GLenum t,GLuint n){glBindTexture(t,n);}
void tx_gen(GLsizei n,GLuint*p){glGenTextures(n,p);}
void tx_delete(GLsizei n,const GLuint*p){glDeleteTextures(n,p);}
void tx_parameterf(GLenum t,GLenum p,GLfloat v){glTexParameterf(t,p,v);}
void tx_parameteri(GLenum t,GLenum p,GLint v){glTexParameteri(t,p,v);}
void tx_parameteriv(GLenum t,GLenum p,const GLint*v){glTexParameteriv(t,p,v);}
void tx_getparameteriv(GLenum t,GLenum p,GLint*v){glGetTexParameteriv(t,p,v);}
void tx_image(GLenum t,GLint l,GLint i,GLsizei w,GLsizei h,GLint b,GLenum f,GLenum ty,const void*p){glTexImage2D(t,l,i,w,h,b,f,ty,p);}
void tx_image_indirect(GLenum t,GLint l,GLint i,GLsizei w,GLsizei h,GLint b,GLenum f,GLenum ty,const void*p){PFNGLTEXIMAGE2DPROC volatile fn=glTexImage2D;fn(t,l,i,w,h,b,f,ty,p);}
void tx_subimage(GLenum t,GLint l,GLint x,GLint y,GLsizei w,GLsizei h,GLenum f,GLenum ty,const void*p){glTexSubImage2D(t,l,x,y,w,h,f,ty,p);}
void tx_subimage_indirect(GLenum t,GLint l,GLint x,GLint y,GLsizei w,GLsizei h,GLenum f,GLenum ty,const void*p){PFNGLTEXSUBIMAGE2DPROC volatile fn=glTexSubImage2D;fn(t,l,x,y,w,h,f,ty,p);}
void tx_compressedimage(GLenum t,GLint l,GLenum f,GLsizei w,GLsizei h,GLint b,GLsizei n,const void*p){glCompressedTexImage2D(t,l,f,w,h,b,n,p);}
void tx_compressedsub(GLenum t,GLint l,GLint x,GLint y,GLsizei w,GLsizei h,GLenum f,GLsizei n,const void*p){glCompressedTexSubImage2D(t,l,x,y,w,h,f,n,p);}
void tx_copyimage(GLenum t,GLint l,GLenum f,GLint x,GLint y,GLsizei w,GLsizei h,GLint b){glCopyTexImage2D(t,l,f,x,y,w,h,b);}
void tx_copysub(GLenum t,GLint l,GLint x,GLint y,GLint sx,GLint sy,GLsizei w,GLsizei h){glCopyTexSubImage2D(t,l,x,y,sx,sy,w,h);}
void tx_mipmap(GLenum t){glGenerateMipmap(t);}

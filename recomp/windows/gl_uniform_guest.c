#include <EGL/egl.h>
#include <GLES3/gl31.h>
#include <stdint.h>
#define PROC(type,name) type f=(type)eglGetProcAddress(#name);if(!f)return UINT64_MAX
uint64_t uniform_active(GLuint p,GLuint i,GLsizei n,GLsizei*l,GLint*s,GLenum*t,GLchar*name){PROC(PFNGLGETACTIVEUNIFORMPROC,glGetActiveUniform);f(p,i,n,l,s,t,name);return 0;}
uint64_t uniform_location(GLuint p,const GLchar*name){PROC(PFNGLGETUNIFORMLOCATIONPROC,glGetUniformLocation);return(uint32_t)f(p,name);}
uint64_t uniform_get(GLuint p,GLint l,GLint*out){PROC(PFNGLGETUNIFORMIVPROC,glGetUniformiv);f(p,l,out);return 0;}
uint64_t uniform_scalar(GLint l,GLint v){PROC(PFNGLUNIFORM1IPROC,glUniform1i);f(l,v);return 0;}
#define VECTOR(n,suffix,type,proc) uint64_t uniform_##n##suffix(GLint l,GLsizei c,const type*v){PROC(proc,glUniform##n##suffix);f(l,c,v);return 0;}
VECTOR(1,fv,GLfloat,PFNGLUNIFORM1FVPROC)
VECTOR(2,fv,GLfloat,PFNGLUNIFORM2FVPROC)
VECTOR(3,fv,GLfloat,PFNGLUNIFORM3FVPROC)
VECTOR(4,fv,GLfloat,PFNGLUNIFORM4FVPROC)
VECTOR(1,iv,GLint,PFNGLUNIFORM1IVPROC)
VECTOR(2,iv,GLint,PFNGLUNIFORM2IVPROC)
VECTOR(3,iv,GLint,PFNGLUNIFORM3IVPROC)
VECTOR(4,iv,GLint,PFNGLUNIFORM4IVPROC)
uint64_t uniform_matrix3(GLint l,GLsizei c,GLboolean transpose,const GLfloat*v){PROC(PFNGLUNIFORMMATRIX3FVPROC,glUniformMatrix3fv);f(l,c,transpose,v);return 0;}
uint64_t uniform_matrix4(GLint l,GLsizei c,GLboolean transpose,const GLfloat*v){PROC(PFNGLUNIFORMMATRIX4FVPROC,glUniformMatrix4fv);f(l,c,transpose,v);return 0;}
uint64_t uniform_error(void){PROC(PFNGLGETERRORPROC,glGetError);return f();}

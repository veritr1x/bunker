#include <stdint.h>
#include <EGL/egl.h>
#include <GLES3/gl31.h>
#define PICK(type,name) type volatile fn=mode==1?(type)(uintptr_t)proc:(type)eglGetProcAddress(#name)
void iu_resolve(uint64_t*out){out[0]=(uint64_t)eglGetProcAddress("glGetUniformiv");out[1]=(uint64_t)eglGetProcAddress("glUniform1i");out[2]=(uint64_t)eglGetProcAddress("glUniform1iv");out[3]=(uint64_t)eglGetProcAddress("glUniform1fv");out[4]=(uint64_t)eglGetProcAddress("glUniform2iv");out[5]=(uint64_t)eglGetProcAddress("glUniformMatrix4fv");}
void iu_get(uint32_t mode,uint64_t proc,GLuint program,GLint location,GLint*out){if(!mode){glGetUniformiv(program,location,out);return;}PICK(PFNGLGETUNIFORMIVPROC,glGetUniformiv);fn(program,location,out);}
void iu_seti(uint32_t mode,uint64_t proc,GLint location,GLint value){if(!mode){glUniform1i(location,value);return;}PICK(PFNGLUNIFORM1IPROC,glUniform1i);fn(location,value);}
void iu_setv(uint32_t mode,uint64_t proc,GLint location,GLsizei count,const GLint*value){if(!mode){glUniform1iv(location,count,value);return;}PICK(PFNGLUNIFORM1IVPROC,glUniform1iv);fn(location,count,value);}
void iu_wrongfv(uint32_t mode,uint64_t proc,GLint location,GLsizei count,const GLfloat*value){if(!mode){glUniform1fv(location,count,value);return;}PICK(PFNGLUNIFORM1FVPROC,glUniform1fv);fn(location,count,value);}
void iu_wrong2iv(uint32_t mode,uint64_t proc,GLint location,GLsizei count,const GLint*value){if(!mode){glUniform2iv(location,count,value);return;}PICK(PFNGLUNIFORM2IVPROC,glUniform2iv);fn(location,count,value);}
void iu_matrix(uint32_t mode,uint64_t proc,GLint location,GLsizei count,GLboolean transpose,const GLfloat*value){if(!mode){glUniformMatrix4fv(location,count,transpose,value);return;}PICK(PFNGLUNIFORMMATRIX4FVPROC,glUniformMatrix4fv);fn(location,count,transpose,value);}
void iu_meta(GLuint p,GLuint index,GLsizei capacity,GLsizei*length,GLint*size,GLenum*type,GLchar*name){glGetActiveUniform(p,index,capacity,length,size,type,name);}

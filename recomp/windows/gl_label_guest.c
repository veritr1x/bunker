#define GL_GLEXT_PROTOTYPES 1
#include <GLES3/gl32.h>
#include <GLES2/gl2ext.h>
#include <EGL/egl.h>
#include <stdint.h>
void label_core(GLenum type,GLuint object,GLsizei length,const GLchar*text){glObjectLabel(type,object,length,text);}
void label_core_indirect(GLenum type,GLuint object,GLsizei length,const GLchar*text){PFNGLOBJECTLABELPROC volatile fn=glObjectLabel;fn(type,object,length,text);}
void label_ext(GLenum type,GLuint object,GLsizei length,const GLchar*text){glLabelObjectEXT(type,object,length,text);}
void label_ext_indirect(GLenum type,GLuint object,GLsizei length,const GLchar*text){PFNGLLABELOBJECTEXTPROC volatile fn=glLabelObjectEXT;fn(type,object,length,text);}
uintptr_t label_core_procedure(GLenum type,GLuint object,GLsizei length,const GLchar*text){PFNGLOBJECTLABELPROC fn=(PFNGLOBJECTLABELPROC)eglGetProcAddress("glObjectLabel");if(fn)fn(type,object,length,text);return(uintptr_t)fn;}
uintptr_t label_ext_procedure(GLenum type,GLuint object,GLsizei length,const GLchar*text){PFNGLLABELOBJECTEXTPROC fn=(PFNGLLABELOBJECTEXTPROC)eglGetProcAddress("glLabelObjectEXT");if(fn)fn(type,object,length,text);return(uintptr_t)fn;}

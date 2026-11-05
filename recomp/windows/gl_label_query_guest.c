#define GL_GLEXT_PROTOTYPES 1
#include <stdint.h>
#include <GLES3/gl32.h>
#include <GLES2/gl2ext.h>
#include <EGL/egl.h>
_Static_assert(sizeof(GLenum)==4&&sizeof(GLuint)==4&&sizeof(GLsizei)==4&&sizeof(void*)==8,"AndroidLP64 label query ABI");
static PFNGLGETOBJECTLABELPROC volatile core_query=glGetObjectLabel;
static PFNGLGETOBJECTLABELEXTPROC volatile ext_query=glGetObjectLabelEXT;
void lq_resolve(uint64_t*out){out[0]=(uintptr_t)eglGetProcAddress("glGetObjectLabel");out[1]=(uintptr_t)eglGetProcAddress("glGetObjectLabelEXT");}
uint64_t lq_query(unsigned extension,unsigned mode,uint64_t procedure,GLenum type,GLuint object,GLsizei capacity,GLsizei*length,GLchar*output){if(extension){if(mode==0)glGetObjectLabelEXT(type,object,capacity,length,output);else if(mode==1)ext_query(type,object,capacity,length,output);else((PFNGLGETOBJECTLABELEXTPROC)(uintptr_t)procedure)(type,object,capacity,length,output);}else{if(mode==0)glGetObjectLabel(type,object,capacity,length,output);else if(mode==1)core_query(type,object,capacity,length,output);else((PFNGLGETOBJECTLABELPROC)(uintptr_t)procedure)(type,object,capacity,length,output);}return UINT64_C(0xf123456789abcdef);}

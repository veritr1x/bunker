#include <stdint.h>
#include <GLES3/gl32.h>
#include <EGL/egl.h>
_Static_assert(sizeof(GLuint)==4&&sizeof(GLenum)==4&&sizeof(GLsizei)==4&&sizeof(GLint)==4&&sizeof(void*)==8,"AndroidLP64 program cache ABI");
static PFNGLPROGRAMPARAMETERIPROC volatile parameter=glProgramParameteri;
static PFNGLGETPROGRAMBINARYPROC volatile get_binary=glGetProgramBinary;
static PFNGLPROGRAMBINARYPROC volatile load_binary=glProgramBinary;
void pb_resolve(uint64_t*out){out[0]=(uintptr_t)eglGetProcAddress("glProgramParameteri");out[1]=(uintptr_t)eglGetProcAddress("glGetProgramBinary");out[2]=(uintptr_t)eglGetProcAddress("glProgramBinary");}
uint64_t pb_parameter(unsigned mode,uint64_t procedure,GLuint program,GLenum pname,GLint value){if(mode==0)glProgramParameteri(program,pname,value);else if(mode==1)parameter(program,pname,value);else((PFNGLPROGRAMPARAMETERIPROC)(uintptr_t)procedure)(program,pname,value);return UINT64_C(0xf123456789abcdef);}
uint64_t pb_get(unsigned mode,uint64_t procedure,GLuint program,GLsizei capacity,GLsizei*length,GLenum*format,void*binary){if(mode==0)glGetProgramBinary(program,capacity,length,format,binary);else if(mode==1)get_binary(program,capacity,length,format,binary);else((PFNGLGETPROGRAMBINARYPROC)(uintptr_t)procedure)(program,capacity,length,format,binary);return UINT64_C(0xf123456789abcdef);}
uint64_t pb_load(unsigned mode,uint64_t procedure,GLuint program,GLenum format,const void*binary,GLsizei length){if(mode==0)glProgramBinary(program,format,binary,length);else if(mode==1)load_binary(program,format,binary,length);else((PFNGLPROGRAMBINARYPROC)(uintptr_t)procedure)(program,format,binary,length);return UINT64_C(0xf123456789abcdef);}

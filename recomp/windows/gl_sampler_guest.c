#include <GLES3/gl31.h>
#include <EGL/egl.h>
#include <stdint.h>
void sampler_gen(GLsizei n,GLuint*out){glGenSamplers(n,out);}
void sampler_gen_indirect(GLsizei n,GLuint*out){PFNGLGENSAMPLERSPROC volatile fn=glGenSamplers;fn(n,out);}
void sampler_delete(GLsizei n,const GLuint*in){glDeleteSamplers(n,in);}
void sampler_bind(GLuint unit,GLuint name){glBindSampler(unit,name);}
void sampler_bind_indirect(GLuint unit,GLuint name){PFNGLBINDSAMPLERPROC volatile fn=glBindSampler;fn(unit,name);}
void sampler_parameter(GLuint name,GLenum pname,GLint value){glSamplerParameteri(name,pname,value);}
uintptr_t sampler_procedure(GLuint unit,GLuint name){PFNGLBINDSAMPLERPROC fn=(PFNGLBINDSAMPLERPROC)eglGetProcAddress("glBindSampler");if(fn)fn(unit,name);return(uintptr_t)fn;}
// Mixed AAPCS64 GP/SIMD arguments cross an observed sampler call. The existing
// typed float command checks that its scalar sources survived that call.
void sampler_mixed(GLuint unit,GLuint name,GLfloat x,GLfloat y,GLfloat z,GLfloat w){glBindSampler(unit,name);glVertexAttrib4f(3,x,y,z,w);}

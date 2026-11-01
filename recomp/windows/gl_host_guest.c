#include <EGL/egl.h>
#include <GLES3/gl31.h>
#include <stdint.h>
int gl_query_guest(const uint32_t *names,unsigned count,unsigned stride,uint8_t *storage,uint64_t *out){
  PFNGLGETSTRINGPROC string=(PFNGLGETSTRINGPROC)eglGetProcAddress("glGetString");
  PFNGLGETSTRINGIPROC stringi=(PFNGLGETSTRINGIPROC)eglGetProcAddress("glGetStringi");
  PFNGLGETINTEGERVPROC integer=(PFNGLGETINTEGERVPROC)eglGetProcAddress("glGetIntegerv");
  PFNGLGETFLOATVPROC floating=(PFNGLGETFLOATVPROC)eglGetProcAddress("glGetFloatv");
  PFNGLGETBOOLEANVPROC boolean=(PFNGLGETBOOLEANVPROC)eglGetProcAddress("glGetBooleanv");
  PFNGLGETERRORPROC error=(PFNGLGETERRORPROC)eglGetProcAddress("glGetError");
  if(!string||!stringi||!integer||!floating||!boolean||!error)return -1;
  out[0]=(uintptr_t)string(GL_VENDOR);out[1]=(uintptr_t)string(GL_RENDERER);out[2]=(uintptr_t)string(GL_VERSION);
  out[3]=(uintptr_t)string(GL_SHADING_LANGUAGE_VERSION);out[4]=(uintptr_t)string(GL_EXTENSIONS);out[5]=(uintptr_t)stringi(GL_EXTENSIONS,0);
  out[6]=error();
  for(unsigned i=0;i<count;++i){
    integer(names[i],(GLint*)(storage+(3*i+0)*stride+16));out[16+3*i+0]=error();
    floating(names[i],(GLfloat*)(storage+(3*i+1)*stride+16));out[16+3*i+1]=error();
    boolean(names[i],(GLboolean*)(storage+(3*i+2)*stride+16));out[16+3*i+2]=error();
  }
  out[7]=(uintptr_t)stringi(GL_EXTENSIONS,0xffffffffu);out[8]=(uintptr_t)string(GL_VENDOR);out[9]=error();out[10]=error();
  out[11]=(uintptr_t)string(0xffffffffu);out[12]=(uintptr_t)string(GL_VERSION);out[13]=error();out[14]=error();
  return count;
}

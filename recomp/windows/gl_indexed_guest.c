#include <stdint.h>
#include <EGL/egl.h>
#include <GLES3/gl31.h>
uint64_t gl_indexed_resolve(void){return (uint64_t)eglGetProcAddress("glGetIntegeri_v");}
void gl_indexed_query(uint32_t target,uint32_t index,int32_t *output){
  PFNGLGETINTEGERI_VPROC query=(PFNGLGETINTEGERI_VPROC)eglGetProcAddress("glGetIntegeri_v");
  query(target,index,output);
}

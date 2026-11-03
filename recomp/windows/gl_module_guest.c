#define _GNU_SOURCE
#include <dlfcn.h>
#include <EGL/egl.h>
#include <GLES3/gl31.h>
#include <stdint.h>
uint64_t loader_gl_queries(const char*path,uint64_t*out,int*maximum){
 void*h=dlopen(path,RTLD_NOW);out[0]=(uintptr_t)h;if(!h)return 1;
 PFNGLGETSTRINGPROC string=(PFNGLGETSTRINGPROC)dlsym(h,"glGetString");
 PFNGLGETINTEGERVPROC integer=(PFNGLGETINTEGERVPROC)dlsym(h,"glGetIntegerv");
 PFNGLGETSTRINGIPROC indexed=(PFNGLGETSTRINGIPROC)dlsym(h,"glGetStringi");
 out[1]=(uintptr_t)string;out[2]=(uintptr_t)integer;out[3]=(uintptr_t)indexed;if(!string||!integer||!indexed)return 2;
 out[4]=(uintptr_t)string(GL_VERSION);integer(GL_MAX_TEXTURE_SIZE,maximum);out[5]=(uintptr_t)indexed(GL_EXTENSIONS,0);return 0;
}
void*loader_open(const char*path,int flags){return dlopen(path,flags);}
void*loader_symbol(void*h,const char*name){return dlsym(h,name);}
int loader_close(void*h){return dlclose(h);}
char*loader_error(void){return dlerror();}
int loader_address(const void*p,Dl_info*out){return dladdr(p,out);}

uint64_t loader_egl_procedures(uint64_t*out){
 out[0]=(uintptr_t)eglGetProcAddress("glGetString");
 out[1]=(uintptr_t)eglGetProcAddress("eglGetError");
 out[2]=(uintptr_t)eglGetProcAddress("glDebugMessageControl");
 out[3]=(uintptr_t)eglGetProcAddress("notARealGLSymbol");
 if(!out[0]||!out[1]||out[2]||out[3])return 1;
 PFNGLGETSTRINGPROC string=(PFNGLGETSTRINGPROC)(uintptr_t)out[0];
 typedef EGLint(EGLAPIENTRYP ErrorProc)(void);
 ErrorProc error=(ErrorProc)(uintptr_t)out[1];
 out[4]=(uintptr_t)string(GL_VERSION);out[5]=(uint32_t)error();out[6]=(uint32_t)error();return 0;
}

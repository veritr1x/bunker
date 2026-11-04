#include <stdint.h>
#include <EGL/egl.h>
#include <GLES3/gl31.h>
#define PICK(type,name) type volatile fn=mode==1?(type)(uintptr_t)proc:(type)eglGetProcAddress(#name)
struct ResourceRequest{uint64_t mode,procedure,program,interface_name,index,count,properties,capacity,length,params;};
void pr_resolve(uint64_t*out){out[0]=(uint64_t)eglGetProcAddress("glGetProgramInterfaceiv");out[1]=(uint64_t)eglGetProcAddress("glGetProgramResourceName");out[2]=(uint64_t)eglGetProcAddress("glGetProgramResourceiv");}
void pr_interface(uint32_t mode,uint64_t proc,GLuint p,GLenum iface,GLenum pname,GLint*out){if(!mode){glGetProgramInterfaceiv(p,iface,pname,out);return;}PICK(PFNGLGETPROGRAMINTERFACEIVPROC,glGetProgramInterfaceiv);fn(p,iface,pname,out);}
void pr_name(uint32_t mode,uint64_t proc,GLuint p,GLenum iface,GLuint index,GLsizei size,GLsizei*length,GLchar*name){if(!mode){glGetProgramResourceName(p,iface,index,size,length,name);return;}PICK(PFNGLGETPROGRAMRESOURCENAMEPROC,glGetProgramResourceName);fn(p,iface,index,size,length,name);}
void pr_values(const struct ResourceRequest*r){const uint32_t mode=(uint32_t)r->mode;const uint64_t proc=r->procedure;const GLuint p=(GLuint)r->program,index=(GLuint)r->index;const GLenum iface=(GLenum)r->interface_name;const GLsizei count=(GLsizei)r->count,size=(GLsizei)r->capacity;const GLenum*props=(const GLenum*)(uintptr_t)r->properties;GLsizei*length=(GLsizei*)(uintptr_t)r->length;GLint*out=(GLint*)(uintptr_t)r->params;if(!mode){glGetProgramResourceiv(p,iface,index,count,props,size,length,out);return;}PICK(PFNGLGETPROGRAMRESOURCEIVPROC,glGetProgramResourceiv);fn(p,iface,index,count,props,size,length,out);}

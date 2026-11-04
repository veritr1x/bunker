#include <stdint.h>
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#define PICK(type,name) type volatile selected=(mode==1?(type)(uintptr_t)proc:(type)eglGetProcAddress(#name))
void ub_resolve(uint64_t*out){out[0]=(uint64_t)eglGetProcAddress("glGetActiveUniformBlockiv");out[1]=(uint64_t)eglGetProcAddress("glGetActiveUniformBlockName");out[2]=(uint64_t)eglGetProcAddress("glUniformBlockBinding");out[3]=(uint64_t)eglGetProcAddress("glGetActiveUniformsiv");out[4]=(uint64_t)eglGetProcAddress("glGetUniformIndices");}
void ub_blockiv(uint32_t mode,uint64_t proc,GLuint p,GLuint index,GLenum pname,GLint*out){if(!mode){glGetActiveUniformBlockiv(p,index,pname,out);return;}PICK(PFNGLGETACTIVEUNIFORMBLOCKIVPROC,glGetActiveUniformBlockiv);selected(p,index,pname,out);}
void ub_blockname(uint32_t mode,uint64_t proc,GLuint p,GLuint index,GLsizei size,GLsizei*length,GLchar*name){if(!mode){glGetActiveUniformBlockName(p,index,size,length,name);return;}PICK(PFNGLGETACTIVEUNIFORMBLOCKNAMEPROC,glGetActiveUniformBlockName);selected(p,index,size,length,name);}
void ub_binding(uint32_t mode,uint64_t proc,GLuint p,GLuint index,GLuint binding){if(!mode){glUniformBlockBinding(p,index,binding);return;}PICK(PFNGLUNIFORMBLOCKBINDINGPROC,glUniformBlockBinding);selected(p,index,binding);}
void ub_uniforms(uint32_t mode,uint64_t proc,GLuint p,GLsizei count,const GLuint*indices,GLenum pname,GLint*out){if(!mode){glGetActiveUniformsiv(p,count,indices,pname,out);return;}PICK(PFNGLGETACTIVEUNIFORMSIVPROC,glGetActiveUniformsiv);selected(p,count,indices,pname,out);}
void ub_indices(uint32_t mode,uint64_t proc,GLuint p,GLsizei count,const GLchar*const*names,GLuint*out){if(!mode){glGetUniformIndices(p,count,names,out);return;}PICK(PFNGLGETUNIFORMINDICESPROC,glGetUniformIndices);selected(p,count,names,out);}

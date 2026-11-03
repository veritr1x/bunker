#include <EGL/egl.h>
#include <GLES3/gl32.h>
#include "gl_framebuffer_fixture.h"
#ifdef GL_FRAMEBUFFER_NATIVE_REFERENCE
#define FRAMEBUFFER_LOAD(name,type) type name=NativeSymbol<type>(#name);(void)name
#else
#define FRAMEBUFFER_LOAD(name,type) type name=(type)eglGetProcAddress(#name);(void)name
void gl_framebuffer_resolve(uint64_t *output){
#define GL_FRAMEBUFFER_COMMAND(name,type) *output++=(uint64_t)eglGetProcAddress(#name);
#include "gl_framebuffer_commands.inc"
#undef GL_FRAMEBUFFER_COMMAND
}
#endif
void gl_framebuffer_create(struct FramebufferObjects *objects){
  FRAMEBUFFER_LOAD(glGenFramebuffers,PFNGLGENFRAMEBUFFERSPROC);
  FRAMEBUFFER_LOAD(glGenRenderbuffers,PFNGLGENRENDERBUFFERSPROC);
  glGenFramebuffers(2,objects->framebuffers);
  glGenRenderbuffers(2,objects->renderbuffers);
}
void gl_framebuffer_setup(const struct FramebufferObjects *objects,struct FramebufferReport *report){
  FRAMEBUFFER_LOAD(glBindFramebuffer,PFNGLBINDFRAMEBUFFERPROC);
  FRAMEBUFFER_LOAD(glBindRenderbuffer,PFNGLBINDRENDERBUFFERPROC);
  FRAMEBUFFER_LOAD(glCheckFramebufferStatus,PFNGLCHECKFRAMEBUFFERSTATUSPROC);
  FRAMEBUFFER_LOAD(glRenderbufferStorage,PFNGLRENDERBUFFERSTORAGEPROC);
  FRAMEBUFFER_LOAD(glFramebufferRenderbuffer,PFNGLFRAMEBUFFERRENDERBUFFERPROC);
  FRAMEBUFFER_LOAD(glGetRenderbufferParameteriv,PFNGLGETRENDERBUFFERPARAMETERIVPROC);
  FRAMEBUFFER_LOAD(glGetFramebufferAttachmentParameteriv,PFNGLGETFRAMEBUFFERATTACHMENTPARAMETERIVPROC);
  const GLenum pnames[9]={GL_RENDERBUFFER_WIDTH,GL_RENDERBUFFER_HEIGHT,GL_RENDERBUFFER_INTERNAL_FORMAT,
    GL_RENDERBUFFER_RED_SIZE,GL_RENDERBUFFER_GREEN_SIZE,GL_RENDERBUFFER_BLUE_SIZE,GL_RENDERBUFFER_ALPHA_SIZE,
    GL_RENDERBUFFER_DEPTH_SIZE,GL_RENDERBUFFER_STENCIL_SIZE};
  glBindFramebuffer(GL_FRAMEBUFFER,objects->framebuffers[0]);
  report->empty_status=glCheckFramebufferStatus(GL_FRAMEBUFFER);
  glBindRenderbuffer(GL_RENDERBUFFER,objects->renderbuffers[0]);
  glRenderbufferStorage(GL_RENDERBUFFER,GL_RGBA4,8,8);
  glFramebufferRenderbuffer(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_RENDERBUFFER,objects->renderbuffers[0]);
  report->complete_status=glCheckFramebufferStatus(GL_FRAMEBUFFER);
  for(unsigned i=0;i<9;++i)glGetRenderbufferParameteriv(GL_RENDERBUFFER,pnames[i],&report->renderbuffer[i]);
  glGetFramebufferAttachmentParameteriv(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE,&report->attachment[0]);
  glGetFramebufferAttachmentParameteriv(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME,&report->attachment[1]);
}
void gl_framebuffer_attach_texture(uint32_t texture,uint32_t textarget,struct FramebufferTextureReport *report){
  FRAMEBUFFER_LOAD(glFramebufferTexture2D,PFNGLFRAMEBUFFERTEXTURE2DPROC);
  FRAMEBUFFER_LOAD(glGetFramebufferAttachmentParameteriv,PFNGLGETFRAMEBUFFERATTACHMENTPARAMETERIVPROC);
  const GLenum pnames[4]={GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME,
    GL_FRAMEBUFFER_ATTACHMENT_TEXTURE_LEVEL,GL_FRAMEBUFFER_ATTACHMENT_TEXTURE_CUBE_MAP_FACE};
  glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,textarget,texture,0);
  for(unsigned i=0;i<4;++i)glGetFramebufferAttachmentParameteriv(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,pnames[i],&report->attachment[i]);
}
void gl_framebuffer_names(uint32_t renderbuffer,int32_t count,uint32_t *output){
  FRAMEBUFFER_LOAD(glGenFramebuffers,PFNGLGENFRAMEBUFFERSPROC);
  FRAMEBUFFER_LOAD(glGenRenderbuffers,PFNGLGENRENDERBUFFERSPROC);
  if(renderbuffer)glGenRenderbuffers(count,output);else glGenFramebuffers(count,output);
}
void gl_framebuffer_delete(uint32_t renderbuffer,int32_t count,const uint32_t *input){
  FRAMEBUFFER_LOAD(glDeleteFramebuffers,PFNGLDELETEFRAMEBUFFERSPROC);
  FRAMEBUFFER_LOAD(glDeleteRenderbuffers,PFNGLDELETERENDERBUFFERSPROC);
  if(renderbuffer)glDeleteRenderbuffers(count,input);else glDeleteFramebuffers(count,input);
}
void gl_framebuffer_renderbuffer_query(uint32_t target,uint32_t pname,int32_t *output){
  FRAMEBUFFER_LOAD(glGetRenderbufferParameteriv,PFNGLGETRENDERBUFFERPARAMETERIVPROC);
  glGetRenderbufferParameteriv(target,pname,output);
}
void gl_framebuffer_attachment_query(uint32_t target,uint32_t attachment,uint32_t pname,int32_t *output){
  FRAMEBUFFER_LOAD(glGetFramebufferAttachmentParameteriv,PFNGLGETFRAMEBUFFERATTACHMENTPARAMETERIVPROC);
  glGetFramebufferAttachmentParameteriv(target,attachment,pname,output);
}
void gl_framebuffer_cleanup(const struct FramebufferObjects *objects){
  FRAMEBUFFER_LOAD(glDeleteFramebuffers,PFNGLDELETEFRAMEBUFFERSPROC);
  FRAMEBUFFER_LOAD(glDeleteRenderbuffers,PFNGLDELETERENDERBUFFERSPROC);
  glDeleteFramebuffers(2,objects->framebuffers);
  glDeleteRenderbuffers(2,objects->renderbuffers);
}
#undef FRAMEBUFFER_LOAD

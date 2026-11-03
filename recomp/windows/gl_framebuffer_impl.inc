// Included inside GlHost::Impl. The central provider owns context selection,
// locking, native symbol loading and the existing per-context error flags.
// Object names and attachment/deletion semantics belong to native ANGLE.
template<class F>void FramebufferParameter(addr_t output,F query){
  // Both object-query APIs return one GLint, unlike general glGet* queries.
  // Never pass a guest output pointer to the driver, or publish after an error.
  Range(output,sizeof(GLint));
  GLint value=0;
  if(Call([&]{query(&value);}))recomp::WriteGuestMemory(output,&value,sizeof(value));
}
void BindFramebufferCommands(){
  Bind<void(GLenum,GLuint)>("glBindFramebuffer",framebuffer_glBindFramebuffer);
  Bind<void(GLenum,GLuint)>("glBindRenderbuffer",framebuffer_glBindRenderbuffer);
  Bind<GLenum(GLenum)>("glCheckFramebufferStatus",framebuffer_glCheckFramebufferStatus);
  Bind<void(GLsizei,addr_t)>("glDeleteFramebuffers",[this](GLsizei n,addr_t input){
    DeleteNames(n,input,framebuffer_glDeleteFramebuffers);
  });
  Bind<void(GLsizei,addr_t)>("glDeleteRenderbuffers",[this](GLsizei n,addr_t input){
    DeleteNames(n,input,framebuffer_glDeleteRenderbuffers);
  });
  Bind<void(GLenum,GLenum,GLenum,GLuint)>("glFramebufferRenderbuffer",framebuffer_glFramebufferRenderbuffer);
  Bind<void(GLenum,GLenum,GLenum,GLuint,GLint)>("glFramebufferTexture2D",framebuffer_glFramebufferTexture2D);
  Bind<void(GLsizei,addr_t)>("glGenFramebuffers",[this](GLsizei n,addr_t output){
    Generate(n,output,framebuffer_glGenFramebuffers);
  });
  Bind<void(GLsizei,addr_t)>("glGenRenderbuffers",[this](GLsizei n,addr_t output){
    Generate(n,output,framebuffer_glGenRenderbuffers);
  });
  Bind<void(GLenum,GLenum,GLenum,addr_t)>("glGetFramebufferAttachmentParameteriv",
    [this](GLenum target,GLenum attachment,GLenum pname,addr_t output){
      FramebufferParameter(output,[&](GLint *value){
        framebuffer_glGetFramebufferAttachmentParameteriv(target,attachment,pname,value);
      });
    });
  Bind<void(GLenum,GLenum,addr_t)>("glGetRenderbufferParameteriv",
    [this](GLenum target,GLenum pname,addr_t output){
      FramebufferParameter(output,[&](GLint *value){framebuffer_glGetRenderbufferParameteriv(target,pname,value);});
    });
  Bind<void(GLenum,GLenum,GLsizei,GLsizei)>("glRenderbufferStorage",framebuffer_glRenderbufferStorage);
}

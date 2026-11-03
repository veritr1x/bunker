// Included inside GlHost::Impl. IDs are actual current-context ANGLE names.
void BindSamplerCommands(){
  Bind<void(GLsizei,addr_t)>("glGenSamplers",[this](auto count,auto output){Generate(count,output,sampler_glGenSamplers);});
  Bind<void(GLsizei,addr_t)>("glDeleteSamplers",[this](auto count,auto input){DeleteNames(count,input,sampler_glDeleteSamplers);});
  Bind<void(GLuint,GLuint)>("glBindSampler",[this](auto unit,auto sampler){sampler_glBindSampler(unit,sampler);});
  Bind<void(GLuint,GLenum,GLint)>("glSamplerParameteri",[this](auto sampler,auto pname,auto value){sampler_glSamplerParameteri(sampler,pname,value);});
}

// Included inside GlHost::Impl. Every query uses the current native program;
// driver names, indices and layouts are never cached or replaced with counts.
void UniformBlockValues(GLuint program,GLuint index,GLenum pname,addr_t output){
  size_t count=1;
  if(pname==GL_UNIFORM_BLOCK_ACTIVE_UNIFORM_INDICES){
    GLint active=-1;
    if(!Call([&]{uniform_block_glGetActiveUniformBlockiv(program,index,GL_UNIFORM_BLOCK_ACTIVE_UNIFORMS,&active);}))return;
    if(active<0||size_t(active)>TransferLimit/sizeof(GLint))throw std::runtime_error("Uniform block active-index count exceeds64MiB scope");
    count=size_t(active);
  }
  // All other GLES uniform-block pnames return one GLint. Unknown enums and
  // invalid program/block indices are validated by the real driver before use.
  std::vector<GLint> values(std::max<size_t>(count,1),0);
  if(Call([&]{uniform_block_glGetActiveUniformBlockiv(program,index,pname,values.data());})&&count){Range(output,count*sizeof(GLint));recomp::WriteGuestMemory(output,values.data(),count*sizeof(GLint));}
}
void UniformBlockName(GLuint program,GLuint index,GLsizei capacity,addr_t length,addr_t output){
  if(capacity>0&&size_t(capacity)>TransferLimit)throw std::runtime_error("Uniform block name output exceeds64MiB scope");
  std::vector<GLchar> bytes(size_t(std::max<GLsizei>(capacity,1)),0);
  GLsizei written=std::numeric_limits<GLsizei>::min();
  if(!Call([&]{uniform_block_glGetActiveUniformBlockName(program,index,capacity,&written,output?bytes.data():nullptr);}))return;
  const bool wrote_length=written!=std::numeric_limits<GLsizei>::min();
  if(capacity>0){
    if(!wrote_length||written<0||written>=capacity||bytes[size_t(written)])throw std::runtime_error("Invalid native uniform block name length");
    Range(output,size_t(written)+1);
  }
  if(length&&wrote_length)Range(length,sizeof(GLsizei));
  // ANGLE writes name bytes before its optional length. Preserve this order
  // for overlapping guest outputs, after all native output is staged safely.
  if(capacity>0)recomp::WriteGuestMemory(output,bytes.data(),size_t(written)+1);
  if(length&&wrote_length)recomp::WriteGuestMemory(length,&written,sizeof(written));
}
void ActiveUniformValues(GLuint program,GLsizei count,addr_t input,GLenum pname,addr_t output){
  GLuint dummy_index=0;GLint dummy_value=0;
  if(count<=0){uniform_block_glGetActiveUniformsiv(program,count,&dummy_index,pname,&dummy_value);return;}
  // The real count-zero call validates program and pname without touching a
  // guest index/output pointer. ANGLE validates count against active uniforms
  // before reading any index, so preserve that error ordering as well.
  if(!Call([&]{uniform_block_glGetActiveUniformsiv(program,0,&dummy_index,pname,&dummy_value);}))return;
  GLint active=-1;if(!Call([&]{draw_glGetProgramiv(program,GL_ACTIVE_UNIFORMS,&active);}))return;
  if(active<0||size_t(active)>TransferLimit/sizeof(GLuint))throw std::runtime_error("Active uniform count exceeds64MiB scope");
  if(count>active){uniform_block_glGetActiveUniformsiv(program,count,&dummy_index,pname,&dummy_value);return;}
  const auto bytes=Snapshot(input,size_t(count)*sizeof(GLuint));std::vector<GLuint> indices(size_t(count),0);std::memcpy(indices.data(),bytes.data(),bytes.size());std::vector<GLint> values(size_t(count),0);
  if(Call([&]{uniform_block_glGetActiveUniformsiv(program,count,indices.data(),pname,values.data());})){Range(output,values.size()*sizeof(GLint));recomp::WriteGuestMemory(output,values.data(),values.size()*sizeof(GLint));}
}
void UniformIndices(GLuint program,GLsizei count,addr_t input,addr_t output){
  if(count<=0){uniform_block_glGetUniformIndices(program,count,nullptr,nullptr);return;}
  if(!Call([&]{uniform_block_glGetUniformIndices(program,0,nullptr,nullptr);}))return;
  if(size_t(count)>TransferLimit/sizeof(addr_t))throw std::runtime_error("Uniform name-pointer array exceeds64MiB scope");
  const auto bytes=Snapshot(input,size_t(count)*sizeof(addr_t));std::vector<addr_t> addresses(size_t(count),0);std::memcpy(addresses.data(),bytes.data(),bytes.size());
  std::vector<std::string> names(size_t(count),std::string{});std::vector<const GLchar*> pointers(size_t(count),nullptr);size_t total=0;
  for(GLsizei i=0;i<count;++i){names[size_t(i)]=UniformName(addresses[size_t(i)]);if(names[size_t(i)].size()>=TransferLimit-total)throw std::runtime_error("Uniform names exceed64MiB scope");total+=names[size_t(i)].size()+1;pointers[size_t(i)]=names[size_t(i)].c_str();}
  std::vector<GLuint> values(size_t(count),GL_INVALID_INDEX);
  if(Call([&]{uniform_block_glGetUniformIndices(program,count,pointers.data(),values.data());})){Range(output,values.size()*sizeof(GLuint));recomp::WriteGuestMemory(output,values.data(),values.size()*sizeof(GLuint));}
}
void BindUniformBlockCommands(){
  Bind<void(GLuint,GLuint,GLenum,addr_t)>("glGetActiveUniformBlockiv",[this](auto p,auto i,auto n,auto out){UniformBlockValues(p,i,n,out);});
  Bind<void(GLuint,GLuint,GLsizei,addr_t,addr_t)>("glGetActiveUniformBlockName",[this](auto p,auto i,auto n,auto length,auto out){UniformBlockName(p,i,n,length,out);});
  using BindingSignature=void(GLuint,GLuint,GLuint);static_assert(std::is_same_v<PFNGLUNIFORMBLOCKBINDINGPROC,BindingSignature*>);
  Bind<BindingSignature>("glUniformBlockBinding",uniform_block_glUniformBlockBinding);
  Bind<void(GLuint,GLsizei,addr_t,GLenum,addr_t)>("glGetActiveUniformsiv",[this](auto p,auto n,auto indices,auto name,auto out){ActiveUniformValues(p,n,indices,name,out);});
  Bind<void(GLuint,GLsizei,addr_t,addr_t)>("glGetUniformIndices",[this](auto p,auto n,auto names,auto out){UniformIndices(p,n,names,out);});
}

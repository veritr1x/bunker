// Included inside GlHost::Impl. The driver defines interfaces, property lists,
// indices and variable-width result streams; none are cached or substituted.
void ProgramInterfaceValues(GLuint program,GLenum interface_name,GLenum pname,addr_t output){
  GLint value=0;
  if(Call([&]{program_resource_glGetProgramInterfaceiv(program,interface_name,pname,&value);})){Range(output,sizeof(value));recomp::WriteGuestMemory(output,&value,sizeof(value));}
}
void ProgramResourceName(GLuint program,GLenum interface_name,GLuint index,GLsizei capacity,addr_t length,addr_t output){
  if(capacity>0&&size_t(capacity)>TransferLimit)throw std::runtime_error("Program resource name output exceeds64MiB scope");
  std::vector<GLchar> bytes(size_t(std::max<GLsizei>(capacity,1)),0);GLsizei written=std::numeric_limits<GLsizei>::min();
  if(!Call([&]{program_resource_glGetProgramResourceName(program,interface_name,index,capacity,&written,bytes.data());}))return;
  const bool wrote_length=written!=std::numeric_limits<GLsizei>::min();
  if(capacity>0){
    if(!wrote_length||written<0||written>=capacity||bytes[size_t(written)])throw std::runtime_error("Invalid native program resource name length");
    Range(output,size_t(written)+1);
  }
  if(length&&wrote_length)Range(length,sizeof(written));
  if(capacity>0)recomp::WriteGuestMemory(output,bytes.data(),size_t(written)+1);
  if(length&&wrote_length)recomp::WriteGuestMemory(length,&written,sizeof(written));
}
void ProgramResourceValues(GLuint program,GLenum interface_name,GLuint index,GLsizei property_count,addr_t input,GLsizei capacity,addr_t length,addr_t output){
  GLenum dummy_property=GL_NAME_LENGTH;GLint dummy_value=0;GLsizei written=std::numeric_limits<GLsizei>::min();
  if(property_count<=0||capacity<0){
    // Native validation rejects these scalar counts before reading props or
    // writing output, including when program/interface is also invalid.
    Call([&]{program_resource_glGetProgramResourceiv(program,interface_name,index,property_count,&dummy_property,capacity,&written,&dummy_value);});return;
  }
  // ACTIVE_RESOURCES validates the same program/interface before any guest
  // property read. With an invalid resource index the original Resourceiv
  // call validates that index before looking at props (pinned ANGLE policy).
  GLint resources=-1;
  if(!Call([&]{program_resource_glGetProgramInterfaceiv(program,interface_name,GL_ACTIVE_RESOURCES,&resources);}))return;
  if(resources<0)throw std::runtime_error("Invalid native program resource count");
  if(index>=GLuint(resources)){
    if(Call([&]{program_resource_glGetProgramResourceiv(program,interface_name,index,property_count,&dummy_property,capacity,&written,&dummy_value);}))throw std::runtime_error("Native program resource index validation disagrees with active count");
    return;
  }
  if(size_t(property_count)>TransferLimit/sizeof(GLenum)||size_t(capacity)>TransferLimit/sizeof(GLint))throw std::runtime_error("Program resource property/output array exceeds64MiB scope");
  const auto bytes=Snapshot(input,size_t(property_count)*sizeof(GLenum));std::vector<GLenum> properties(size_t(property_count),0);std::memcpy(properties.data(),bytes.data(),bytes.size());
  std::vector<GLint> values(size_t(std::max<GLsizei>(capacity,1)),0);
  if(!Call([&]{program_resource_glGetProgramResourceiv(program,interface_name,index,property_count,properties.data(),capacity,&written,values.data());}))return;
  // A failed-link program can retain implementation-dependent resource data;
  // the pinned driver may succeed without writing either output. Preserve it.
  if(written==std::numeric_limits<GLsizei>::min())return;
  if(written<0||written>capacity)throw std::runtime_error("Invalid native program resource result length");
  if(written)Range(output,size_t(written)*sizeof(GLint));
  if(length)Range(length,sizeof(written));
  // Native query writes the result stream then its final length; retain this
  // order for overlapping guest outputs after the complete props snapshot.
  if(written)recomp::WriteGuestMemory(output,values.data(),size_t(written)*sizeof(GLint));
  if(length)recomp::WriteGuestMemory(length,&written,sizeof(written));
}
void BindProgramResourceCommands(){
  Bind<void(GLuint,GLenum,GLenum,addr_t)>("glGetProgramInterfaceiv",[this](auto p,auto i,auto n,auto out){ProgramInterfaceValues(p,i,n,out);});
  Bind<void(GLuint,GLenum,GLuint,GLsizei,addr_t,addr_t)>("glGetProgramResourceName",[this](auto p,auto i,auto n,auto c,auto length,auto out){ProgramResourceName(p,i,n,c,length,out);});
  Bind<void(GLuint,GLenum,GLuint,GLsizei,addr_t,GLsizei,addr_t,addr_t)>("glGetProgramResourceiv",[this](auto p,auto i,auto n,auto c,auto props,auto size,auto length,auto out){ProgramResourceValues(p,i,n,c,props,size,length,out);});
}

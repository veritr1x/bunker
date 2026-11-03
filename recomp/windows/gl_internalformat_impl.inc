// Included inside GlHost::Impl. GLES sample-count queries only.
void InternalFormatQuery(GLenum target,GLenum format,GLenum pname,GLsizei capacity,addr_t output){
  if(pname!=GL_NUM_SAMPLE_COUNTS&&pname!=GL_SAMPLES)
    throw std::runtime_error("Unsupported GL internal-format query output width: "+Hex(pname));
  // Native validation still sees the original target/format and signed capacity.
  // Zero capacity publishes nothing; negative capacity must not become size_t.
  if(capacity<=0){GLint dummy=0;Call([&]{internalformat_glGetInternalformativ(target,format,pname,capacity,&dummy);});return;}
  GLint count=-1;
  if(pname==GL_NUM_SAMPLE_COUNTS){
    if(Call([&]{internalformat_glGetInternalformativ(target,format,pname,capacity,&count);})){
      Range(output,sizeof(count));recomp::WriteGuestMemory(output,&count,sizeof(count));
    }
    return;
  }
  // Capabilities are queried on the same current context under the GL mutex.
  // The native getter writes min(capacity,count), never the entire capacity.
  if(!Call([&]{internalformat_glGetInternalformativ(target,format,GL_NUM_SAMPLE_COUNTS,1,&count);}))return;
  if(count<0)throw std::runtime_error("Invalid native internal-format sample count");
  const auto written=std::min(size_t(capacity),size_t(count));
  if(written>TransferLimit/sizeof(GLint))throw std::runtime_error("GL internal-format output exceeds64MiB scope");
  std::vector<GLint> values(std::max<size_t>(written,1),0);
  if(Call([&]{internalformat_glGetInternalformativ(target,format,pname,capacity,values.data());})&&written){
    Range(output,written*sizeof(GLint));recomp::WriteGuestMemory(output,values.data(),written*sizeof(GLint));
  }
}
void BindInternalFormatCommands(){
  Bind<void(GLenum,GLenum,GLenum,GLsizei,addr_t)>("glGetInternalformativ",[this](auto target,auto format,auto pname,auto capacity,auto output){InternalFormatQuery(target,format,pname,capacity,output);});
}

// Included inside GlHost::Impl. Call drains new native flags even if that enum already
// exists in the pending set; no set-size comparison can hide a probe failure.
template<class Setter,class Getter>
void LabelValue(GLenum type,GLuint object,GLsizei length,addr_t input,bool extension,Setter native,Getter probe){
  if(!input||(extension&&length<0)){native(type,object,length,nullptr);return;}
  // Core validates object/name before length. EXT's negative-length case was
  // delegated above, before any object validation or guest memory access.
  if(!Call([&]{probe(type,object,0,nullptr,nullptr);}))return;
  if(!extension){
    const GLchar empty=0;
    if(length==0){native(type,object,length,&empty);return;}
    GLint maximum=0;if(!Call([&]{getInteger(GL_MAX_LABEL_LENGTH,&maximum);}))return;
    if(maximum<=0||size_t(maximum)>TransferLimit)throw std::runtime_error("Unsupported native GL maximum label length");
    if(length>0&&length>=maximum){native(type,object,length,&empty);return;}
    if(length<0){auto text=recomp::ReadGuestString(input,size_t(maximum));native(type,object,length,text.c_str());return;}
  }else if(length==0){
    auto text=recomp::ReadGuestString(input,TransferLimit);
    if(text.size()==TransferLimit)throw std::runtime_error("GL label NUL string exceeds64MiB scope");
    native(type,object,length,text.c_str());return;
  }
  auto bytes=Snapshot(input,size_t(length));
  native(type,object,length,reinterpret_cast<const GLchar*>(bytes.data()));
}
template<class Getter>
void LabelQuery(GLenum type,GLuint object,GLsizei capacity,addr_t length,addr_t output,Getter native){
  GLsizei written=-1;
  if(capacity<0){Call([&]{native(type,object,capacity,&written,nullptr);});return;}
  std::vector<GLchar> bytes;
  GLchar *buffer=nullptr;
  if(output&&capacity>0){
    if(size_t(capacity)>TransferLimit)throw std::runtime_error("GL label query output exceeds64MiB scope");
    bytes.resize(size_t(capacity));buffer=bytes.data();
  }
  // NULL label or zero capacity is a genuine full-length query in ANGLE.
  // Always retain a private native count, including for guest length=NULL.
  if(!Call([&]{native(type,object,capacity,&written,buffer);}))return;
  if(written<0)throw std::runtime_error("Invalid native GL label query length");
  if(buffer){
    if(written>=capacity||bytes[size_t(written)]!=0)throw std::runtime_error("Invalid native GL label query output");
    Range(output,size_t(written)+1);
  }
  if(length)Range(length,sizeof(written));
  // The pinned native implementation writes characters/NUL, then length.
  // Preserve that order for overlap; publish no untouched output suffix.
  if(buffer)recomp::WriteGuestMemory(output,bytes.data(),size_t(written)+1);
  if(length)recomp::WriteGuestMemory(length,&written,sizeof(written));
}
void BindLabelCommands(){
  const auto core=Symbol<PFNGLOBJECTLABELPROC>(module,"glObjectLabel");
  const auto core_query=Symbol<PFNGLGETOBJECTLABELPROC>(module,"glGetObjectLabel");
  const auto ext=Symbol<PFNGLLABELOBJECTEXTPROC>(module,"glLabelObjectEXT");
  const auto ext_query=Symbol<PFNGLGETOBJECTLABELEXTPROC>(module,"glGetObjectLabelEXT");
  Bind<void(GLenum,GLuint,GLsizei,addr_t)>("glObjectLabel",[this,core,core_query](auto type,auto object,auto length,auto input){LabelValue(type,object,length,input,false,core,core_query);});
  Bind<void(GLenum,GLuint,GLsizei,addr_t)>("glLabelObjectEXT",[this,ext,ext_query](auto type,auto object,auto length,auto input){LabelValue(type,object,length,input,true,ext,ext_query);});
  Bind<void(GLenum,GLuint,GLsizei,addr_t,addr_t)>("glGetObjectLabel",[this,core_query](auto type,auto object,auto capacity,auto length,auto output){LabelQuery(type,object,capacity,length,output,core_query);});
  Bind<void(GLenum,GLuint,GLsizei,addr_t,addr_t)>("glGetObjectLabelEXT",[this,ext_query](auto type,auto object,auto capacity,auto length,auto output){LabelQuery(type,object,capacity,length,output,ext_query);});
}

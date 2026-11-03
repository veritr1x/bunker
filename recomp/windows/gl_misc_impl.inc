  static std::string MiscName(addr_t input){
    std::string name;
    for(size_t n=0;n<65536;++n){
      Range(input,n+1);GLchar value=0;recomp::ReadGuestMemory(&value,input+n,1);
      if(!value)return name;
      name.push_back(value);
    }
    throw std::runtime_error("GL attribute name exceeds64KiB");
  }
  void MiscActiveAttrib(GLuint program,GLuint index,GLsizei capacity,addr_t length,
                        addr_t size,addr_t type,addr_t output){
    if(capacity<0){GLsizei n=0;GLint s=0;GLenum t=0;GLchar c=0;
      Call([&]{misc_glGetActiveAttrib(program,index,capacity,&n,&s,&t,&c);});return;}
    if(size_t(capacity)>TransferLimit)throw std::runtime_error("GL active attribute name exceeds64MiB");
    std::vector<GLchar> bytes(std::max<GLsizei>(capacity,1));GLsizei n=-1;GLint s=0;GLenum t=0;
    if(!Call([&]{misc_glGetActiveAttrib(program,index,capacity,&n,&s,&t,bytes.data());}))return;
    if(capacity?(n<0||n>=capacity):(n!=-1&&n!=0))throw std::runtime_error("Invalid native active attribute length");
    if(capacity){Range(output,size_t(n)+1);recomp::WriteGuestMemory(output,bytes.data(),size_t(n)+1);}
    if(length&&n>=0){Range(length,4);recomp::WriteGuestMemory(length,&n,4);}
    Range(size,4);Range(type,4);recomp::WriteGuestMemory(size,&s,4);recomp::WriteGuestMemory(type,&t,4);
  }
  void MiscPrecision(GLenum shader,GLenum kind,addr_t range,addr_t precision){
    GLint bounds[2]{},bits=0;
    if(!Call([&]{misc_glGetShaderPrecisionFormat(shader,kind,range?bounds:nullptr,precision?&bits:nullptr);}))return;
    if(range){Range(range,8);recomp::WriteGuestMemory(range,bounds,8);}
    if(precision){Range(precision,4);recomp::WriteGuestMemory(precision,&bits,4);}
  }
  void MiscVertexQuery(GLuint index,GLenum pname,addr_t output){
    size_t count=1;
    switch(pname){
      case GL_CURRENT_VERTEX_ATTRIB:count=4;break;
      case GL_VERTEX_ATTRIB_ARRAY_BUFFER_BINDING:case GL_VERTEX_ATTRIB_ARRAY_ENABLED:
      case GL_VERTEX_ATTRIB_ARRAY_SIZE:case GL_VERTEX_ATTRIB_ARRAY_STRIDE:
      case GL_VERTEX_ATTRIB_ARRAY_TYPE:case GL_VERTEX_ATTRIB_ARRAY_NORMALIZED:
      case GL_VERTEX_ATTRIB_ARRAY_INTEGER:case GL_VERTEX_ATTRIB_ARRAY_DIVISOR:
      case GL_VERTEX_ATTRIB_BINDING:case GL_VERTEX_ATTRIB_RELATIVE_OFFSET:break;
      default:throw std::runtime_error("Unsupported GL vertex attribute output width: "+Hex(pname));
    }
    GLint values[4]{};if(!Call([&]{misc_glGetVertexAttribiv(index,pname,values);}))return;
    Range(output,count*4);recomp::WriteGuestMemory(output,values,count*4);
  }
  void BindMiscCommands(){
    Bind<void(GLuint,GLuint,GLsizei,addr_t,addr_t,addr_t,addr_t)>("glGetActiveAttrib",[this](auto p,auto i,auto n,auto l,auto s,auto t,auto out){MiscActiveAttrib(p,i,n,l,s,t,out);});
    Bind<GLint(GLuint,addr_t)>("glGetAttribLocation",[this](auto p,auto name){auto owned=name?MiscName(name):std::string();GLint result=-1;Call([&]{result=misc_glGetAttribLocation(p,name?owned.c_str():nullptr);});return result;});
    Bind<void(GLenum,GLenum,addr_t,addr_t)>("glGetShaderPrecisionFormat",[this](auto s,auto t,auto r,auto p){MiscPrecision(s,t,r,p);});
    Bind<void(GLuint,GLsizei,addr_t,addr_t)>("glGetShaderSource",[this](auto s,auto n,auto l,auto out){InfoLog(s,n,l,out,misc_glGetShaderSource);});
    Bind<void(GLuint,GLenum,addr_t)>("glGetVertexAttribiv",[this](auto i,auto p,auto out){MiscVertexQuery(i,p,out);});
    Bind<void(GLuint,GLuint,addr_t)>("glBindAttribLocation",[this](auto p,auto i,auto name){auto owned=name?MiscName(name):std::string();misc_glBindAttribLocation(p,i,name?owned.c_str():nullptr);});
    Bind<void(GLenum)>("glBlendEquation",misc_glBlendEquation);
    Bind<void(GLuint)>("glStencilMask",misc_glStencilMask);
    Bind<void(GLuint)>("glValidateProgram",misc_glValidateProgram);
    Bind<void(GLuint,GLfloat,GLfloat,GLfloat,GLfloat)>("glVertexAttrib4f",misc_glVertexAttrib4f);
    Bind<void(GLuint,addr_t)>("glVertexAttrib4fv",[this](auto i,auto input){
      if(!input){misc_glVertexAttrib4fv(i,nullptr);return;}
      const GLint maximum=Integer(GL_MAX_VERTEX_ATTRIBS);
      if(maximum<0)throw std::runtime_error("Invalid native vertex attribute maximum");
      GLfloat values[4]{};
      if(i<GLuint(maximum)){auto bytes=Snapshot(input,sizeof(values));std::memcpy(values,bytes.data(),sizeof(values));}
      misc_glVertexAttrib4fv(i,values);
    });
  }

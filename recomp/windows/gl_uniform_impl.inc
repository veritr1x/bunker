// Included inside GlHost::Impl. Native calls use the existing current context
// and error queue; no helper re-enters the non-recursive provider mutex.
struct UniformInfo {GLenum type;size_t components,remaining;bool array;};
static bool UniformImage(GLenum type){
  switch(type){
    case GL_IMAGE_2D:case GL_IMAGE_3D:case GL_IMAGE_CUBE:case GL_IMAGE_2D_ARRAY:
    case GL_INT_IMAGE_2D:case GL_INT_IMAGE_3D:case GL_INT_IMAGE_CUBE:case GL_INT_IMAGE_2D_ARRAY:
    case GL_UNSIGNED_INT_IMAGE_2D:case GL_UNSIGNED_INT_IMAGE_3D:case GL_UNSIGNED_INT_IMAGE_CUBE:case GL_UNSIGNED_INT_IMAGE_2D_ARRAY:return true;
    default:return false;
  }
}
static size_t UniformComponents(GLenum type){
  if(UniformImage(type))return 1; // Getter width only; ES3.1 forbids all Uniform* image loads.
  switch(type){
    case GL_FLOAT:case GL_INT:case GL_BOOL:case GL_SAMPLER_2D:case GL_SAMPLER_CUBE:return 1;
    case GL_FLOAT_VEC2:case GL_INT_VEC2:case GL_BOOL_VEC2:return 2;
    case GL_FLOAT_VEC3:case GL_INT_VEC3:case GL_BOOL_VEC3:return 3;
    case GL_FLOAT_VEC4:case GL_INT_VEC4:case GL_BOOL_VEC4:case GL_FLOAT_MAT2:return 4;
    case GL_FLOAT_MAT3:return 9;case GL_FLOAT_MAT4:return 16;
    default:throw std::runtime_error("Uniform type outside GLES2 transfer scope: "+Hex(type));
  }
}
static bool UniformSampler(GLenum type){return type==GL_SAMPLER_2D||type==GL_SAMPLER_CUBE;}
static bool UniformVectorType(GLenum type,unsigned n,bool integer){
  const GLenum floating[]={GL_FLOAT,GL_FLOAT_VEC2,GL_FLOAT_VEC3,GL_FLOAT_VEC4};
  const GLenum integers[]={GL_INT,GL_INT_VEC2,GL_INT_VEC3,GL_INT_VEC4};
  const GLenum booleans[]={GL_BOOL,GL_BOOL_VEC2,GL_BOOL_VEC3,GL_BOOL_VEC4};
  return type==booleans[n-1]||type==(integer?integers[n-1]:floating[n-1])||(integer&&n==1&&UniformSampler(type));
}
std::string UniformName(addr_t input){
  std::string name;
  for(size_t i=0;i<TransferLimit;++i){Range(input,i+1);char c;recomp::ReadGuestMemory(&c,input+i,1);if(!c)return name;name+=c;}
  throw std::runtime_error("Uniform name exceeds64MiB scope");
}
// Re-query on each call: no stale GLuint/context/link-generation cache.
std::optional<UniformInfo> FindUniform(GLuint program,GLint location,bool &linked){
  linked=false;if(location<0)return std::nullopt;GLint status=0;
  if(!Call([&]{draw_glGetProgramiv(program,GL_LINK_STATUS,&status);})||!status)return std::nullopt;
  linked=true;GLint count=0,capacity=0;
  if(!Call([&]{draw_glGetProgramiv(program,GL_ACTIVE_UNIFORMS,&count);draw_glGetProgramiv(program,GL_ACTIVE_UNIFORM_MAX_LENGTH,&capacity);}))throw std::runtime_error("Cannot inspect active uniforms");
  if(count<0||count>1048576||capacity<0||size_t(capacity)>TransferLimit)throw std::runtime_error("Uniform metadata outside bounded scope");
  if(!count)return std::nullopt;
  if(!capacity)throw std::runtime_error("Active uniforms have no bounded name capacity");
  std::vector<GLchar> name(size_t(capacity),0);size_t locations=0;
  for(GLuint index=0;index<GLuint(count);++index){
    GLsizei length=-1;GLint elements=0;GLenum type=0;
    if(!Call([&]{uniform_glGetActiveUniform(program,index,capacity,&length,&elements,&type,name.data());}))throw std::runtime_error("Cannot inspect active uniform");
    if(length<0||length>=capacity||name[size_t(length)]||elements<=0||elements>1048576)throw std::runtime_error("Invalid native uniform metadata");
    std::string native_name(name.data(),size_t(length));const bool array=native_name.size()>=3&&native_name.compare(native_name.size()-3,3,"[0]")==0;
    if(elements>1&&!array)throw std::runtime_error("Unexpanded native uniform array name outside scope");
    for(GLint element=0;element<elements;++element){
      if(++locations>1048576)throw std::runtime_error("Uniform location metadata exceeds bounded scope");
      const auto candidate=array?native_name.substr(0,native_name.size()-3)+"["+std::to_string(element)+"]":native_name;
      GLint actual=-1;if(!Call([&]{actual=uniform_glGetUniformLocation(program,candidate.c_str());}))throw std::runtime_error("Cannot inspect exact uniform location");
      if(actual==location)return UniformInfo{type,UniformComponents(type),size_t(elements-element),array};
    }
  }
  return std::nullopt;
}
void UniformActive(GLuint program,GLuint index,GLsizei capacity,addr_t length,addr_t size,addr_t type,addr_t output){
  if(capacity<0){GLsizei n=0;GLint s=0;GLenum t=0;GLchar c=0;uniform_glGetActiveUniform(program,index,capacity,&n,&s,&t,&c);return;}
  if(size_t(capacity)>TransferLimit)throw std::runtime_error("Uniform name output exceeds64MiB scope");
  std::vector<GLchar> name(size_t(std::max<GLsizei>(capacity,1)),0);GLsizei written=std::numeric_limits<GLsizei>::min();GLint elements=std::numeric_limits<GLint>::min();GLenum native_type=UINT32_MAX;
  if(!Call([&]{uniform_glGetActiveUniform(program,index,capacity,&written,&elements,&native_type,output?name.data():nullptr);}))return;
  const bool wrote_length=written!=std::numeric_limits<GLsizei>::min(),wrote_size=elements!=std::numeric_limits<GLint>::min(),wrote_type=native_type!=UINT32_MAX;
  if(capacity&&(!wrote_length||written<0||written>=capacity))throw std::runtime_error("Invalid active uniform name length");
  if(length&&wrote_length){Range(length,4);}if(size&&wrote_size){Range(size,4);}if(type&&wrote_type){Range(type,4);}if(capacity){Range(output,size_t(written)+1);}
  if(capacity)recomp::WriteGuestMemory(output,name.data(),size_t(written)+1);
  if(length&&wrote_length){recomp::WriteGuestMemory(length,&written,4);}if(size&&wrote_size){recomp::WriteGuestMemory(size,&elements,4);}if(type&&wrote_type){recomp::WriteGuestMemory(type,&native_type,4);}
}
GLint UniformLocation(GLuint program,addr_t name){
  GLint location=-1;
  if(!name){Call([&]{location=uniform_glGetUniformLocation(program,nullptr);});return location;}
  // Validate program/link without reading a guest name on an error path.
  if(!Call([&]{location=uniform_glGetUniformLocation(program,"");}))return -1;
  const auto owned=UniformName(name);Call([&]{location=uniform_glGetUniformLocation(program,owned.c_str());});return location;
}
void UniformGet(GLuint program,GLint location,addr_t output){
  bool linked=false;auto info=FindUniform(program,location,linked);
  if(!info){GLint dummy[16]{};if(Call([&]{uniform_glGetUniformiv(program,location,dummy);}))throw std::runtime_error("Successful uniform getter location could not be attributed");return;}
  std::vector<GLint> values(info->components,0);
  if(Call([&]{uniform_glGetUniformiv(program,location,values.data());})){Range(output,values.size()*4);recomp::WriteGuestMemory(output,values.data(),values.size()*4);}
}
template<class T,class F>void UniformVector(GLint location,GLsizei count,addr_t input,unsigned components,bool integer,F native){
  T dummy[16]{};auto ignored=[&](GLsizei n){native(location,n,input?dummy:nullptr);};
  // Pinned ANGLE validates NULL first only for fv and iv2/3/4.
  if(!input&&(!integer||components>1)){native(location,count,nullptr);return;}
  if(location<0||count<=0){ignored(count);return;}
  if(size_t(count)>TransferLimit/(components*sizeof(T)))throw std::runtime_error("Uniform requested count exceeds64MiB scope");
  const auto program=GLuint(Integer(GL_CURRENT_PROGRAM));if(!program){ignored(count);return;}
  bool linked=false;auto info=FindUniform(program,location,linked);if(!linked){ignored(count);return;}
  if(!info){if(Call([&]{ignored(0);}))throw std::runtime_error("Unmatched or ignored native uniform location outside transfer scope");return;}
  if(!UniformVectorType(info->type,components,integer)||(!info->array&&count>1)){ignored(count);return;}
  // ANGLE clamps non-sampler uploads before pointer use. Its sampler1iv
  // validator inspects every requested value, including clipped tail values.
  const size_t copied=UniformSampler(info->type)?size_t(count):std::min(size_t(count),info->remaining);
  const size_t elements=copied*components;auto bytes=Snapshot(input,elements*sizeof(T));std::vector<T> values(elements);std::memcpy(values.data(),bytes.data(),bytes.size());native(location,count,values.data());
}
bool UniformAllowsTranspose(){const GLubyte*version=nullptr;if(!Call([&]{version=getString(GL_VERSION);})||!version)throw std::runtime_error("Cannot inspect uniform matrix context version");return std::strstr(reinterpret_cast<const char*>(version),"OpenGL ES 3")!=nullptr;}
template<class F>void UniformMatrix(GLint location,GLsizei count,GLboolean transpose,addr_t input,unsigned dimension,F native){
  GLfloat dummy[16]{};auto ignored=[&](GLsizei n){native(location,n,transpose,input?dummy:nullptr);};
  if(location<0||count<=0){ignored(count);return;}
  if(transpose&&!UniformAllowsTranspose()){ignored(count);return;}
  const size_t components=size_t(dimension)*dimension;if(size_t(count)>TransferLimit/(components*4))throw std::runtime_error("Uniform matrix requested count exceeds64MiB scope");
  const auto program=GLuint(Integer(GL_CURRENT_PROGRAM));if(!program){ignored(count);return;}
  bool linked=false;auto info=FindUniform(program,location,linked);if(!linked){ignored(count);return;}
  const GLenum expected=dimension==3?GL_FLOAT_MAT3:GL_FLOAT_MAT4;
  if(!info){if(Call([&]{ignored(0);}))throw std::runtime_error("Unmatched native matrix location outside transfer scope");return;}
  if(info->type!=expected||(!info->array&&count>1)){ignored(count);return;}
  const size_t elements=std::min(size_t(count),info->remaining)*components;auto bytes=Snapshot(input,elements*4);std::vector<GLfloat> values(elements);std::memcpy(values.data(),bytes.data(),bytes.size());native(location,count,transpose,values.data());
}
void BindUniformCommands(){
  Bind<void(GLuint,GLuint,GLsizei,addr_t,addr_t,addr_t,addr_t)>("glGetActiveUniform",[this](auto p,auto i,auto n,auto l,auto s,auto t,auto name){UniformActive(p,i,n,l,s,t,name);});
  Bind<GLint(GLuint,addr_t)>("glGetUniformLocation",[this](auto p,auto name){return UniformLocation(p,name);});
  Bind<void(GLuint,GLint,addr_t)>("glGetUniformiv",[this](auto p,auto l,auto out){UniformGet(p,l,out);});
  Bind<void(GLint,GLint)>("glUniform1i",uniform_glUniform1i);
#define UNIFORM_VECTOR(n,suffix,type,integer) Bind<void(GLint,GLsizei,addr_t)>("glUniform" #n #suffix,[this](auto l,auto c,auto p){UniformVector<type>(l,c,p,n,integer,uniform_glUniform##n##suffix);});
  UNIFORM_VECTOR(1,fv,GLfloat,false) UNIFORM_VECTOR(2,fv,GLfloat,false) UNIFORM_VECTOR(3,fv,GLfloat,false) UNIFORM_VECTOR(4,fv,GLfloat,false)
  UNIFORM_VECTOR(1,iv,GLint,true) UNIFORM_VECTOR(2,iv,GLint,true) UNIFORM_VECTOR(3,iv,GLint,true) UNIFORM_VECTOR(4,iv,GLint,true)
#undef UNIFORM_VECTOR
  Bind<void(GLint,GLsizei,GLboolean,addr_t)>("glUniformMatrix3fv",[this](auto l,auto n,auto t,auto p){UniformMatrix(l,n,t,p,3,uniform_glUniformMatrix3fv);});
  Bind<void(GLint,GLsizei,GLboolean,addr_t)>("glUniformMatrix4fv",[this](auto l,auto n,auto t,auto p){UniformMatrix(l,n,t,p,4,uniform_glUniformMatrix4fv);});
}

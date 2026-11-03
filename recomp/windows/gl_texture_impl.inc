// Included inside GlHost::Impl. Fields are texture_<native command>.
// ES3.0.6 sections 3.7/3.8: synchronous uploads own their copied client rows;
// unpack-buffer offsets are never interpreted as host/guest client addresses.
  struct TextureUnpackSupport {bool buffer=false;bool rows=false;};
  TextureUnpackSupport TextureUnpackCapabilities() {
    const GLubyte *version=nullptr;
    if(!Call([&]{version=getString(GL_VERSION);})||!version)
      throw std::runtime_error("Cannot inspect texture unpack context version");
    const auto *text=reinterpret_cast<const char*>(version);
    if(std::strstr(text,"OpenGL ES 3."))return {true,true};
    if(std::strstr(text,"OpenGL ES 2.")){
      // ES2 extension enums alias the core3 tokens, but may be queried only
      // when the actual context advertises the corresponding capability.
      const GLubyte *extensions=nullptr;
      if(!Call([&]{extensions=getString(GL_EXTENSIONS);})||!extensions)
        throw std::runtime_error("Cannot inspect ES2 texture unpack extensions");
      TextureUnpackSupport support;std::istringstream words(reinterpret_cast<const char*>(extensions));std::string word;
      while(words>>word){if(word=="GL_NV_pixel_buffer_object")support.buffer=true;if(word=="GL_EXT_unpack_subimage")support.rows=true;}
      return support;
    }
    throw std::runtime_error("Unsupported texture unpack context version");
  }
  static size_t TextureParameterComponents(GLenum pname) {
    switch(pname){
      case GL_TEXTURE_MIN_FILTER:case GL_TEXTURE_MAG_FILTER:
      case GL_TEXTURE_WRAP_S:case GL_TEXTURE_WRAP_T:case GL_TEXTURE_WRAP_R:
      case GL_TEXTURE_MIN_LOD:case GL_TEXTURE_MAX_LOD:
      case GL_TEXTURE_BASE_LEVEL:case GL_TEXTURE_MAX_LEVEL:
      case GL_TEXTURE_COMPARE_MODE:case GL_TEXTURE_COMPARE_FUNC:
      case GL_TEXTURE_SWIZZLE_R:case GL_TEXTURE_SWIZZLE_G:
      case GL_TEXTURE_SWIZZLE_B:case GL_TEXTURE_SWIZZLE_A:
      case GL_TEXTURE_IMMUTABLE_FORMAT:case GL_TEXTURE_IMMUTABLE_LEVELS:
      case 0x84fe: return 1; // TEXTURE_MAX_ANISOTROPY_EXT; native validates support.
      case 0x1004: return 4; // TEXTURE_BORDER_COLOR; native validates version/extension.
      default:throw std::runtime_error("Unsupported GL texture parameter width: "+Hex(pname));
    }
  }
  void TextureGetParameter(GLenum target,GLenum pname,addr_t output) {
    const auto count=TextureParameterComponents(pname);Range(output,count*sizeof(GLint));
    GLint values[4]{};
    if(Call([&]{texture_glGetTexParameteriv(target,pname,values);}))
      recomp::WriteGuestMemory(output,values,count*sizeof(GLint));
  }
  void TextureSetParameter(GLenum target,GLenum pname,addr_t input) {
    const auto count=TextureParameterComponents(pname);
    auto bytes=Snapshot(input,count*sizeof(GLint));GLint values[4]{};
    std::memcpy(values,bytes.data(),bytes.size());texture_glTexParameteriv(target,pname,values);
  }
  static size_t TexturePixelBytes(GLenum format,GLenum type) {
    // Storage widths only; ANGLE still validates format/type/internalformat legality.
    if(type==GL_UNSIGNED_SHORT_5_6_5&&format==GL_RGB)return 2;
    if((type==GL_UNSIGNED_SHORT_4_4_4_4||type==GL_UNSIGNED_SHORT_5_5_5_1)&&format==GL_RGBA)return 2;
    if(type==GL_UNSIGNED_INT_2_10_10_10_REV&&(format==GL_RGBA||format==GL_RGBA_INTEGER))return 4;
    if((type==GL_UNSIGNED_INT_10F_11F_11F_REV||type==GL_UNSIGNED_INT_5_9_9_9_REV)&&format==GL_RGB)return 4;
    if(type==GL_UNSIGNED_INT_24_8&&format==GL_DEPTH_STENCIL)return 4;
    if(type==GL_FLOAT_32_UNSIGNED_INT_24_8_REV&&format==GL_DEPTH_STENCIL)return 8;
    size_t components=0;
    switch(format){
      case GL_ALPHA:case GL_LUMINANCE:case GL_RED:case GL_RED_INTEGER:case GL_DEPTH_COMPONENT:components=1;break;
      case GL_LUMINANCE_ALPHA:case GL_RG:case GL_RG_INTEGER:components=2;break;
      case GL_RGB:case GL_RGB_INTEGER:components=3;break;
      case GL_RGBA:case GL_RGBA_INTEGER:components=4;break;
      default:throw std::runtime_error("Unsupported GL texture pixel format: "+Hex(format));
    }
    switch(type){
      case GL_BYTE:case GL_UNSIGNED_BYTE:return components;
      case GL_SHORT:case GL_UNSIGNED_SHORT:case GL_HALF_FLOAT:case 0x8d61:return components*2; // HALF_FLOAT_OES
      case GL_INT:case GL_UNSIGNED_INT:case GL_FLOAT:return components*4;
      default:throw std::runtime_error("Unsupported GL texture pixel type: "+Hex(type));
    }
  }
  static uint64_t TextureAdd(uint64_t a,uint64_t b) {
    if(a>TransferLimit||b>TransferLimit-a)throw std::runtime_error("GL texture footprint exceeds64MiB scope");
    return a+b;
  }
  static uint64_t TextureMultiply(uint64_t a,uint64_t b) {
    if(a&&b>TransferLimit/a)throw std::runtime_error("GL texture footprint exceeds64MiB scope");
    return a*b;
  }
  std::vector<uint8_t> TextureSnapshot(GLsizei width,GLsizei height,GLenum format,GLenum type,addr_t input,bool extended) {
    const auto pixel=TexturePixelBytes(format,type);
    const GLint alignment=Integer(GL_UNPACK_ALIGNMENT);
    const GLint row_length=extended?Integer(GL_UNPACK_ROW_LENGTH):0;
    const GLint skip_rows=extended?Integer(GL_UNPACK_SKIP_ROWS):0;
    const GLint skip_pixels=extended?Integer(GL_UNPACK_SKIP_PIXELS):0;
    if((alignment!=1&&alignment!=2&&alignment!=4&&alignment!=8)||row_length<0||skip_rows<0||skip_pixels<0)
      throw std::runtime_error("Invalid native GL texture unpack state");
    const auto row_bytes=TextureMultiply(uint64_t(width),pixel);
    const auto unaligned=TextureMultiply(uint64_t(row_length?row_length:width),pixel);
    const auto stride=(unaligned+uint64_t(alignment-1))&~uint64_t(alignment-1);
    if(stride>TransferLimit)throw std::runtime_error("GL texture row exceeds64MiB scope");
    const auto prefix=TextureAdd(TextureMultiply(uint64_t(skip_rows),stride),TextureMultiply(uint64_t(skip_pixels),pixel));
    const auto end=TextureAdd(TextureAdd(prefix,TextureMultiply(uint64_t(height-1),stride)),row_bytes);
    Range(input,size_t(end));std::vector<uint8_t> bytes(size_t(end),0);
    // Only bytes GL actually reads are snapped; skipped/padding memory can be inaccessible.
    // Short rowLength can overlap rows in GLES, so do not impose WebGL restrictions.
    for(GLsizei row=0;row<height;++row){
      const auto offset=prefix+uint64_t(row)*stride;
      recomp::ReadGuestMemory(bytes.data()+offset,input+offset,size_t(row_bytes));
    }
    return bytes;
  }
  template<class F>void TextureUpload(GLsizei width,GLsizei height,GLenum format,GLenum type,addr_t input,bool allocation,F native) {
    const auto support=TextureUnpackCapabilities();
    if(support.buffer&&Integer(GL_PIXEL_UNPACK_BUFFER_BINDING)){
      native(reinterpret_cast<const void*>(input));return; // full64 buffer offset, including zero
    }
    if(width<=0||height<=0||(!input&&allocation)){native(nullptr);return;}
    if(!input)throw std::invalid_argument("Null client GL texture subimage input");
    auto bytes=TextureSnapshot(width,height,format,type,input,support.rows);native(bytes.data());
  }
  template<class F>void TextureCompressedUpload(GLsizei width,GLsizei height,GLsizei image_size,addr_t input,bool allocation,F native) {
    if(TextureUnpackCapabilities().buffer&&Integer(GL_PIXEL_UNPACK_BUFFER_BINDING)){
      native(reinterpret_cast<const void*>(input));return;
    }
    // Compressed data is exactly imageSize bytes; ALL pixel-store modes are ignored.
    if(width<=0||height<=0||image_size<=0||(!input&&allocation)){native(nullptr);return;}
    if(!input)throw std::invalid_argument("Null client compressed GL texture subimage input");
    auto bytes=Snapshot(input,size_t(image_size));native(bytes.data());
  }
  void BindTextureCommands() {
    Bind<void(GLenum,GLuint)>("glBindTexture",texture_glBindTexture);
    Bind<void(GLenum)>("glGenerateMipmap",texture_glGenerateMipmap);
    Bind<void(GLsizei,addr_t)>("glGenTextures",[this](auto n,auto out){Generate(n,out,texture_glGenTextures);});
    Bind<void(GLsizei,addr_t)>("glDeleteTextures",[this](auto n,auto in){DeleteNames(n,in,texture_glDeleteTextures);});
    Bind<void(GLenum,GLenum,GLfloat)>("glTexParameterf",texture_glTexParameterf);
    Bind<void(GLenum,GLenum,GLint)>("glTexParameteri",texture_glTexParameteri);
    Bind<void(GLenum,GLenum,addr_t)>("glTexParameteriv",[this](auto t,auto p,auto in){TextureSetParameter(t,p,in);});
    Bind<void(GLenum,GLenum,addr_t)>("glGetTexParameteriv",[this](auto t,auto p,auto out){TextureGetParameter(t,p,out);});
    Bind<void(GLenum,GLint,GLenum,GLint,GLint,GLsizei,GLsizei,GLint)>("glCopyTexImage2D",texture_glCopyTexImage2D);
    Bind<void(GLenum,GLint,GLint,GLint,GLint,GLint,GLsizei,GLsizei)>("glCopyTexSubImage2D",texture_glCopyTexSubImage2D);
    Bind<void(GLenum,GLint,GLint,GLsizei,GLsizei,GLint,GLenum,GLenum,addr_t)>("glTexImage2D",[this](auto t,auto l,auto i,auto w,auto h,auto b,auto f,auto ty,auto in){
      TextureUpload(w,h,f,ty,in,true,[&](const void *pixels){texture_glTexImage2D(t,l,i,w,h,b,f,ty,pixels);});});
    Bind<void(GLenum,GLint,GLint,GLint,GLsizei,GLsizei,GLenum,GLenum,addr_t)>("glTexSubImage2D",[this](auto t,auto l,auto x,auto y,auto w,auto h,auto f,auto ty,auto in){
      TextureUpload(w,h,f,ty,in,false,[&](const void *pixels){texture_glTexSubImage2D(t,l,x,y,w,h,f,ty,pixels);});});
    Bind<void(GLenum,GLint,GLenum,GLsizei,GLsizei,GLint,GLsizei,addr_t)>("glCompressedTexImage2D",[this](auto t,auto l,auto f,auto w,auto h,auto b,auto n,auto in){
      TextureCompressedUpload(w,h,n,in,true,[&](const void *pixels){texture_glCompressedTexImage2D(t,l,f,w,h,b,n,pixels);});});
    Bind<void(GLenum,GLint,GLint,GLint,GLsizei,GLsizei,GLenum,GLsizei,addr_t)>("glCompressedTexSubImage2D",[this](auto t,auto l,auto x,auto y,auto w,auto h,auto f,auto n,auto in){
      TextureCompressedUpload(w,h,n,in,false,[&](const void *pixels){texture_glCompressedTexSubImage2D(t,l,x,y,w,h,f,n,pixels);});});
  }

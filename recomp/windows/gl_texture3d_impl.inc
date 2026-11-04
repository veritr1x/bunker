// Included inside Impl. These transfers require a real core GLES3 context.
// No old 2D upload implementation or native unpack state is changed.
  bool Texture3DBufferOffset() {
    const GLubyte*version=nullptr;
    if(!Call([&]{version=getString(GL_VERSION);})||!version||
       !std::strstr(reinterpret_cast<const char*>(version),"OpenGL ES 3."))
      throw std::runtime_error("3D texture transfer requires core GLES3 profile");
    return Integer(GL_PIXEL_UNPACK_BUFFER_BINDING)!=0;
  }
  std::vector<uint8_t> Texture3DSnapshot(GLsizei width,GLsizei height,GLsizei depth,GLenum format,GLenum type,addr_t input) {
    const auto pixel=TexturePixelBytes(format,type);
    const GLint alignment=Integer(GL_UNPACK_ALIGNMENT),row_length=Integer(GL_UNPACK_ROW_LENGTH),image_height=Integer(GL_UNPACK_IMAGE_HEIGHT);
    const GLint skip_pixels=Integer(GL_UNPACK_SKIP_PIXELS),skip_rows=Integer(GL_UNPACK_SKIP_ROWS),skip_images=Integer(GL_UNPACK_SKIP_IMAGES);
    if((alignment!=1&&alignment!=2&&alignment!=4&&alignment!=8)||row_length<0||image_height<0||skip_pixels<0||skip_rows<0||skip_images<0)
      throw std::runtime_error("Invalid native3D unpack state");
    const auto row_bytes=TextureMultiply(uint64_t(width),pixel);
    const auto unaligned=TextureMultiply(uint64_t(row_length?row_length:width),pixel);
    const auto stride=(unaligned+uint64_t(alignment-1))&~uint64_t(alignment-1);
    if(stride>TransferLimit)throw std::runtime_error("3D texture row exceeds64MiB scope");
    const auto slice=TextureMultiply(stride,uint64_t(image_height?image_height:height));
    const auto prefix=TextureAdd(TextureAdd(TextureMultiply(uint64_t(skip_images),slice),TextureMultiply(uint64_t(skip_rows),stride)),TextureMultiply(uint64_t(skip_pixels),pixel));
    const auto end=TextureAdd(TextureAdd(TextureAdd(prefix,TextureMultiply(uint64_t(depth-1),slice)),TextureMultiply(uint64_t(height-1),stride)),row_bytes);
    Range(input,size_t(end));std::vector<uint8_t> bytes(size_t(end),0);
    // Short row/image lengths may overlap in GLES. Snapshot exactly the bytes
    // native unpack reads, never inaccessible prefix/padding/slice gaps.
    for(GLsizei z=0;z<depth;++z)for(GLsizei y=0;y<height;++y){
      const auto offset=prefix+uint64_t(z)*slice+uint64_t(y)*stride;
      recomp::ReadGuestMemory(bytes.data()+offset,input+offset,size_t(row_bytes));
    }
    return bytes;
  }
  template<class F>void Texture3DUpload(GLsizei width,GLsizei height,GLsizei depth,GLenum format,GLenum type,addr_t input,F native) {
    if(Texture3DBufferOffset()){native(reinterpret_cast<const void*>(input));return;}
    // NULL allocation/subimage and nonpositive dimensions are native validation
    // cases; no client read is performed and no success/error is fabricated.
    if(width<=0||height<=0||depth<=0){const uint8_t dummy=0;native(input?&dummy:nullptr);return;}
    if(!input){native(nullptr);return;}
    auto bytes=Texture3DSnapshot(width,height,depth,format,type,input);native(bytes.data());
  }
  template<class F>void Texture3DCompressedUpload(GLsizei width,GLsizei height,GLsizei depth,GLsizei image_size,addr_t input,F native) {
    if(Texture3DBufferOffset()){native(reinterpret_cast<const void*>(input));return;}
    // GLES3 compressed decoding ignores pixel-store modes; ANGLE Context uses
    // an empty PixelUnpackState. PBO validation still sees real native state.
    if(width<=0||height<=0||depth<=0||image_size<=0){const uint8_t dummy=0;native(input?&dummy:nullptr);return;}
    if(!input){native(nullptr);return;}
    auto bytes=Snapshot(input,size_t(image_size));native(bytes.data());
  }
  void BindTexture3DCommands() {
    const auto image=Symbol<PFNGLTEXIMAGE3DPROC>(module,"glTexImage3D");
    const auto sub=Symbol<PFNGLTEXSUBIMAGE3DPROC>(module,"glTexSubImage3D");
    const auto compressed=Symbol<PFNGLCOMPRESSEDTEXSUBIMAGE3DPROC>(module,"glCompressedTexSubImage3D");
    Bind<void(GLenum,GLint,GLint,GLsizei,GLsizei,GLsizei,GLint,GLenum,GLenum,addr_t)>("glTexImage3D",[this,image](auto t,auto l,auto i,auto w,auto h,auto d,auto b,auto f,auto ty,auto p){Texture3DUpload(w,h,d,f,ty,p,[&](const void*data){image(t,l,i,w,h,d,b,f,ty,data);});});
    Bind<void(GLenum,GLint,GLint,GLint,GLint,GLsizei,GLsizei,GLsizei,GLenum,GLenum,addr_t)>("glTexSubImage3D",[this,sub](auto t,auto l,auto x,auto y,auto z,auto w,auto h,auto d,auto f,auto ty,auto p){Texture3DUpload(w,h,d,f,ty,p,[&](const void*data){sub(t,l,x,y,z,w,h,d,f,ty,data);});});
    Bind<void(GLenum,GLint,GLint,GLint,GLint,GLsizei,GLsizei,GLsizei,GLenum,GLsizei,addr_t)>("glCompressedTexSubImage3D",[this,compressed](auto t,auto l,auto x,auto y,auto z,auto w,auto h,auto d,auto f,auto n,auto p){Texture3DCompressedUpload(w,h,d,n,p,[&](const void*data){compressed(t,l,x,y,z,w,h,d,f,n,data);});});
  }

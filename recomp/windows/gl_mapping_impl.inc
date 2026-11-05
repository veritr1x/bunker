// Included in GlHost::Impl. Addresses belong to the actual ANGLE mapping;
// this registry stores lifetime metadata only, never a substitute data store.
std::optional<GLenum> BufferBindingQuery(GLenum target){
  switch(target){
    case GL_ARRAY_BUFFER:return GL_ARRAY_BUFFER_BINDING;
    case GL_ELEMENT_ARRAY_BUFFER:return GL_ELEMENT_ARRAY_BUFFER_BINDING;
    case GL_COPY_READ_BUFFER:return GL_COPY_READ_BUFFER_BINDING;
    case GL_COPY_WRITE_BUFFER:return GL_COPY_WRITE_BUFFER_BINDING;
    case GL_PIXEL_PACK_BUFFER:return GL_PIXEL_PACK_BUFFER_BINDING;
    case GL_PIXEL_UNPACK_BUFFER:return GL_PIXEL_UNPACK_BUFFER_BINDING;
    case GL_TRANSFORM_FEEDBACK_BUFFER:return GL_TRANSFORM_FEEDBACK_BUFFER_BINDING;
    case GL_UNIFORM_BUFFER:return GL_UNIFORM_BUFFER_BINDING;
    case GL_ATOMIC_COUNTER_BUFFER:return GL_ATOMIC_COUNTER_BUFFER_BINDING;
    case GL_SHADER_STORAGE_BUFFER:return GL_SHADER_STORAGE_BUFFER_BINDING;
    case GL_DRAW_INDIRECT_BUFFER:return GL_DRAW_INDIRECT_BUFFER_BINDING;
    case GL_DISPATCH_INDIRECT_BUFFER:return GL_DISPATCH_INDIRECT_BUFFER_BINDING;
    case GL_TEXTURE_BUFFER:return GL_TEXTURE_BUFFER_BINDING;
    default:return std::nullopt;
  }
}
std::optional<MappedKey> BoundMappedKey(GLenum target){
  const auto query=BufferBindingQuery(target);if(!query)return std::nullopt;
  GLint name=0;getInteger(*query,&name);
  if(!name)return std::nullopt;
  return MappedKey{current_share_group,static_cast<GLuint>(name)};
}
void RetireMapping(const MappedKey &key){
  const auto at=mapped_ranges.find(key);if(at==mapped_ranges.end())return;
  // Invalidation never reads the address, including after driver retirement.
  recomp::InvalidateGuestMemory(at->second.address,at->second.length);
  mapped_ranges.erase(at);
}
void PruneMappings(){
  for(auto at=mapped_ranges.begin();at!=mapped_ranges.end();){
    if(!egl.ShareGroupAlive(at->first.first)){
      recomp::InvalidateGuestMemory(at->second.address,at->second.length);
      at=mapped_ranges.erase(at);
    }else ++at;
  }
}
void InvalidateMappings(bool prune){
  for(const auto &[key,range]:mapped_ranges){(void)key;recomp::InvalidateGuestMemory(range.address,range.length);}
  if(prune)PruneMappings();
}
addr_t MapBufferRange(GLenum target,int64_t offset,int64_t length,GLbitfield access){
  CollectErrors();void *pointer=mapping_glMapBufferRange(target,offset,length,access);CollectErrors();
  if(!pointer)return 0;
  const auto address=reinterpret_cast<addr_t>(pointer);
  try{
    if(length<=0||uint64_t(length)>std::numeric_limits<size_t>::max())throw std::runtime_error("Invalid successful native GL mapping length");
    Range(address,static_cast<size_t>(length));
    const auto key=BoundMappedKey(target);
    if(!key||CollectErrors())throw std::runtime_error("Successful GL mapping has no supported owned buffer binding");
    RetireMapping(*key);
    mapped_ranges.emplace(*key,MappedRange{address,static_cast<size_t>(length)});
    // Publish native map completion/lifetime to the shared-memory protocol.
    recomp::InvalidateGuestMemory(address,static_cast<size_t>(length));
  }catch(...){mapping_glUnmapBuffer(target);recomp::InvalidateGuestMemory(address,length>0?static_cast<size_t>(length):0);throw;}
  return address;
}
GLboolean UnmapBuffer(GLenum target){
  CollectErrors();const auto key=BoundMappedKey(target);
  // Acquire prior tracked client writes, then release the memory lock before
  // the real driver can wait for GPU work. Valid callers synchronize accesses
  // to mapped storage; concurrent unmap/use is outside the native GL contract.
  recomp::WithGuestMemoryRead([]{});
  const GLboolean result=mapping_glUnmapBuffer(target);const bool error=CollectErrors();
  // GL_FALSE without an API error is genuine corruption and also ends mapping.
  if(!error&&key)RetireMapping(*key);
  return result;
}
void FlushMappedBufferRange(GLenum target,int64_t offset,int64_t length){
  recomp::WithGuestMemoryRead([]{});
  // Offsets are relative to the map start, exactly as the driver specifies.
  mapping_glFlushMappedBufferRange(target,offset,length);
}
void DeleteMappedBuffers(GLsizei count,addr_t input){
  if(count<=0){GLuint dummy=0;draw_glDeleteBuffers(count,&dummy);return;}
  auto bytes=Snapshot(input,size_t(count)*sizeof(GLuint));std::vector<GLuint> names(count);
  std::memcpy(names.data(),bytes.data(),bytes.size());
  if(Call([&]{draw_glDeleteBuffers(count,names.data());}))for(const auto name:names)RetireMapping({current_share_group,name});
}
void BindMappingCommands(){
  Bind<addr_t(GLenum,int64_t,int64_t,GLbitfield)>("glMapBufferRange",[this](auto target,auto offset,auto length,auto access){return MapBufferRange(target,offset,length,access);});
  Bind<GLboolean(GLenum)>("glUnmapBuffer",[this](auto target){return UnmapBuffer(target);});
  Bind<void(GLenum,int64_t,int64_t)>("glFlushMappedBufferRange",[this](auto target,auto offset,auto length){FlushMappedBufferRange(target,offset,length);});
}

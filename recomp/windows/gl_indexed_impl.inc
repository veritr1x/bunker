// Included inside GlHost::Impl. Only these two indexed targets have a qualified
// scalar width here. Other indexed states may have different output widths.
void BindIndexedCommands(){
  static_assert(GL_MAX_COMPUTE_WORK_GROUP_COUNT==0x91be&&GL_MAX_COMPUTE_WORK_GROUP_SIZE==0x91bf);
  Bind<void(GLenum,GLuint,addr_t)>("glGetIntegeri_v",[this](GLenum target,GLuint index,addr_t output){
    if(target!=GL_MAX_COMPUTE_WORK_GROUP_COUNT&&target!=GL_MAX_COMPUTE_WORK_GROUP_SIZE)
      throw std::runtime_error("Unsupported indexed GL query output width: "+Hex(target));
    Range(output,sizeof(GLint));
    GLint value=0;
    // ANGLE validates the index (including out-of-range values). Preserve its
    // actual error and leave guest output untouched if the query fails.
    if(Call([&]{indexed_glGetIntegeri_v(target,index,&value);}))
      recomp::WriteGuestMemory(output,&value,sizeof(value));
  });
}

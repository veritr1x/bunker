// Included inside GlHost::Impl. The current native ANGLE context owns buffer
// names, generic/indexed bindings, full-store size, validation and deletion.
void BindIndexedBufferCommands(){
  Bind<void(GLenum,GLuint,GLuint)>("glBindBufferBase",buffer_indexed_glBindBufferBase);
}

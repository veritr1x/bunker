#include <EGL/egl.h>
#include <GLES3/gl32.h>
#include "gl_draw_fixture.h"
#ifdef GL_NATIVE_REFERENCE
#define LOAD(n,t) t n=NativeSymbol<t>(#n);(void)n
#else
#define LOAD(n,t) t n=(t)eglGetProcAddress(#n);(void)n
#endif
#ifndef GL_NATIVE_REFERENCE
void gl_draw_resolve(uint64_t *out){
#define GL_DRAW(n,t) *out++=(uint64_t)eglGetProcAddress(#n);
#include "gl_draw_commands.inc"
#undef GL_DRAW
}
uint64_t gl_draw_object_resolve(void){return (uint64_t)eglGetProcAddress("glIsVertexArray");}
uint64_t gl_draw_is_vertex_array_direct(uint32_t name){return glIsVertexArray(name);}
uint64_t gl_draw_is_vertex_array_pointer(uint64_t procedure,uint32_t name){
 return ((PFNGLISVERTEXARRAYPROC)procedure)(name);
}
uint64_t gl_draw_is_vertex_array_procedure(uint32_t name){
 PFNGLISVERTEXARRAYPROC query=(PFNGLISVERTEXARRAYPROC)eglGetProcAddress("glIsVertexArray");
 return query(name);
}
#endif
void gl_draw_upload(const struct DrawInput *in,struct DrawObjects *out){
#define GL_DRAW(n,t) LOAD(n,t);
#include "gl_draw_commands.inc"
#undef GL_DRAW
 out->vs=glCreateShader(GL_VERTEX_SHADER);out->fs=glCreateShader(GL_FRAGMENT_SHADER);
 glShaderSource(out->vs,in->vcount,(const GLchar *const*)in->vs,(const GLint*)in->vlengths);
 glShaderSource(out->fs,in->fcount,(const GLchar *const*)in->fs,(const GLint*)in->flengths);
 out->program=glCreateProgram();glGenBuffers(2,out->buffers);glGenVertexArrays(1,&out->vao);
 glBindVertexArray(out->vao);glBindBuffer(GL_ARRAY_BUFFER,out->buffers[0]);
 glBufferData(GL_ARRAY_BUFFER,in->vertex_bytes,0,GL_STATIC_DRAW);
 glBufferSubData(GL_ARRAY_BUFFER,0,in->vertex_bytes,(const void*)in->vertices);
 glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,out->buffers[1]);
 glBufferData(GL_ELEMENT_ARRAY_BUFFER,in->index_bytes,(const void*)in->indices,GL_STATIC_DRAW);
}
void gl_draw_compile(const struct DrawObjects *o,struct DrawStatus *out){
#define GL_DRAW(n,t) LOAD(n,t);
#include "gl_draw_commands.inc"
#undef GL_DRAW
 glCompileShader(o->vs);glCompileShader(o->fs);
 glGetShaderiv(o->vs,GL_COMPILE_STATUS,&out->vertex);glGetShaderiv(o->fs,GL_COMPILE_STATUS,&out->fragment);
 glAttachShader(o->program,o->vs);glAttachShader(o->program,o->fs);glLinkProgram(o->program);
 glGetProgramiv(o->program,GL_LINK_STATUS,&out->linked);
 glGetProgramInfoLog(o->program,0,&out->program_log_length,0);
 glDeleteShader(o->vs);glDeleteShader(o->fs);glGetShaderiv(o->vs,GL_DELETE_STATUS,&out->shader_deleted);
 glDetachShader(o->program,o->vs);glDetachShader(o->program,o->fs);
 glUseProgram(o->program);glBindVertexArray(o->vao);glBindBuffer(GL_ARRAY_BUFFER,o->buffers[0]);
 glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,8,(const void*)16);glEnableVertexAttribArray(0);glDisableVertexAttribArray(1);
}
void gl_draw_render(const struct DrawObjects *o,int indexed,void *out){
#define GL_DRAW(n,t) LOAD(n,t);
#include "gl_draw_commands.inc"
#undef GL_DRAW
 LOAD(glDisable,PFNGLDISABLEPROC);LOAD(glViewport,PFNGLVIEWPORTPROC);LOAD(glClearColor,PFNGLCLEARCOLORPROC);LOAD(glClear,PFNGLCLEARPROC);
 glUseProgram(o->program);glBindVertexArray(o->vao);glDisable(GL_DITHER);glDisable(GL_SCISSOR_TEST);glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);
 glViewport(0,0,8,8);glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);
 if(indexed)glDrawElements(GL_TRIANGLES,3,GL_UNSIGNED_SHORT,(const void*)4);else glDrawArrays(GL_TRIANGLES,0,3);
 glPixelStorei(GL_PACK_ALIGNMENT,4);glPixelStorei(GL_PACK_ROW_LENGTH,0);glPixelStorei(GL_PACK_SKIP_ROWS,0);glPixelStorei(GL_PACK_SKIP_PIXELS,0);
 glReadPixels(0,0,8,8,GL_RGBA,GL_UNSIGNED_BYTE,out);
}
void gl_draw_read(const struct DrawRead *r,void *out){
 LOAD(glPixelStorei,PFNGLPIXELSTOREIPROC);LOAD(glReadPixels,PFNGLREADPIXELSPROC);
 glPixelStorei(GL_PACK_ALIGNMENT,r->alignment);glPixelStorei(GL_PACK_ROW_LENGTH,r->row_length);
 glPixelStorei(GL_PACK_SKIP_ROWS,r->skip_rows);glPixelStorei(GL_PACK_SKIP_PIXELS,r->skip_pixels);
 glReadPixels(r->x,r->y,r->width,r->height,GL_RGBA,GL_UNSIGNED_BYTE,out);
}
uint32_t gl_draw_bad_shader(const char *const *strings,const int *lengths,int capacity,int *status,int *written,char *log){
 LOAD(glCreateShader,PFNGLCREATESHADERPROC);LOAD(glShaderSource,PFNGLSHADERSOURCEPROC);LOAD(glCompileShader,PFNGLCOMPILESHADERPROC);
 LOAD(glGetShaderiv,PFNGLGETSHADERIVPROC);LOAD(glGetShaderInfoLog,PFNGLGETSHADERINFOLOGPROC);LOAD(glDeleteShader,PFNGLDELETESHADERPROC);
 uint32_t shader=glCreateShader(GL_VERTEX_SHADER);glShaderSource(shader,1,strings,lengths);glCompileShader(shader);
 glGetShaderiv(shader,GL_COMPILE_STATUS,status);glGetShaderInfoLog(shader,capacity,written,log);glDeleteShader(shader);return shader;
}
void gl_draw_query(uint32_t program,uint32_t pname,int *out){LOAD(glGetProgramiv,PFNGLGETPROGRAMIVPROC);glGetProgramiv(program,pname,out);}
void gl_draw_delete_program(uint32_t program){LOAD(glDeleteProgram,PFNGLDELETEPROGRAMPROC);glDeleteProgram(program);}
void gl_draw_cleanup(const struct DrawObjects *o){
 LOAD(glUseProgram,PFNGLUSEPROGRAMPROC);LOAD(glDeleteProgram,PFNGLDELETEPROGRAMPROC);LOAD(glDeleteBuffers,PFNGLDELETEBUFFERSPROC);LOAD(glDeleteVertexArrays,PFNGLDELETEVERTEXARRAYSPROC);
 glUseProgram(0);glDeleteProgram(o->program);glDeleteBuffers(2,o->buffers);glDeleteVertexArrays(1,&o->vao);
}
#undef LOAD

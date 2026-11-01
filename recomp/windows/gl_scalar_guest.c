#include <EGL/egl.h>
#include <GLES3/gl32.h>
#include <stdint.h>

int gl_scalar_guest(uint32_t *out) {
#ifdef GL_NATIVE_REFERENCE
#define GL_SCALAR(name, native_type, signature) native_type name=NativeSymbol<native_type>(#name);
#else
#define GL_SCALAR(name, native_type, signature) native_type name=(native_type)eglGetProcAddress(#name);if(!name)return -1;
#endif
#include "gl_scalar_commands.inc"
#undef GL_SCALAR
#ifdef GL_NATIVE_REFERENCE
  PFNGLGETERRORPROC error=NativeSymbol<PFNGLGETERRORPROC>("glGetError");
#else
  PFNGLGETERRORPROC error=(PFNGLGETERRORPROC)eglGetProcAddress("glGetError");
#endif
  if(!error)return -2;
  glDisable(GL_SCISSOR_TEST);glDisable(GL_DITHER);glColorMask(1,1,1,1);
  glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);
  glViewport(1,2,5,4);glScissor(2,1,3,5);glEnable(GL_SCISSOR_TEST);
  glClearColor(.125f,.25f,.5f,1);glClear(GL_COLOR_BUFFER_BIT);
  glColorMask(0,1,0,1);glClearColor(1,.75f,1,.5f);glClear(GL_COLOR_BUFFER_BIT);
  glClearDepthf(.375f);glClearStencil(-5);glClear(GL_DEPTH_BUFFER_BIT|GL_STENCIL_BUFFER_BIT);
  glActiveTexture(GL_TEXTURE3);glEnable(GL_BLEND);glEnable(GL_DEPTH_TEST);glDisable(GL_CULL_FACE);
  out[0]=glIsEnabled(GL_BLEND);out[1]=glIsEnabled(GL_CULL_FACE);
  glDepthMask(0x80);glDepthFunc(GL_GEQUAL);glDepthRangef(.25f,.75f);
  glStencilMaskSeparate(GL_FRONT,0xabcdef01U);glStencilMaskSeparate(GL_BACK,0x12345678U);
  glStencilFuncSeparate(GL_FRONT,GL_LESS,-3,0x87654321U);glStencilFuncSeparate(GL_BACK,GL_ALWAYS,19,0xfedcba98U);
  glStencilOpSeparate(GL_FRONT,GL_REPLACE,GL_INCR,GL_DECR);glStencilOpSeparate(GL_BACK,GL_ZERO,GL_INVERT,GL_KEEP);
  glBlendColor(.3f,.4f,.6f,.8f);glBlendEquationSeparate(GL_FUNC_SUBTRACT,GL_FUNC_ADD);
  glBlendFuncSeparate(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA,GL_ONE,GL_ZERO);
  glCullFace(GL_FRONT);glFrontFace(GL_CW);glPolygonOffset(1.25f,-2.5f);
  glSampleCoverage(.625f,0x80);glLineWidth(1);glHint(GL_GENERATE_MIPMAP_HINT,GL_NICEST);
  glFlush();glFinish();out[2]=error();
  glViewport(0,0,-1,2);glEnable(0xffffffffU);glClear(0x80000000U);
  glEnable(GL_BLEND);out[3]=error();out[4]=error();out[5]=error();
  return 28;
}

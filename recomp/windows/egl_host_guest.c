#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <android/native_window_jni.h>
#include <stdint.h>
extern int host_egl_draw_check(int width,int height);
// Actual Android headers establish handle widths and all19 import signatures.
int egl_guest(JNIEnv *env,jobject java_surface,uint64_t *out){
  unsigned n=0;
#define PUT(expression) out[n++]=(expression)?1:0
  ANativeWindow *window=ANativeWindow_fromSurface(env,java_surface);
  PUT(window!=0);
  EGLDisplay d=eglGetDisplay(EGL_DEFAULT_DISPLAY);PUT(d!=EGL_NO_DISPLAY);
  PUT(eglInitialize(d,0,0));
  struct Guard {uint32_t before;EGLint value;uint32_t after;} major={0x13572468,0,0x24681357},minor=major,visual=major,width=major;
  PUT(eglInitialize(d,&major.value,&minor.value));
  PUT(major.value==1&&minor.value>=4&&major.before==0x13572468&&major.after==0x24681357&&minor.before==0x13572468&&minor.after==0x24681357);
  PUT(eglQueryString(d,EGL_VENDOR)!=0&&eglQueryString(d,EGL_EXTENSIONS)!=0);
  const EGLint config_attributes[]={EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,
    EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT_KHR,EGL_SURFACE_TYPE,EGL_WINDOW_BIT|EGL_PBUFFER_BIT,EGL_NONE};
  EGLint count=0;EGLConfig config=0;
  PUT(eglChooseConfig(d,config_attributes,0,0,&count)&&count>0);
  PUT(eglChooseConfig(d,config_attributes,&config,1,&count)&&count==1&&config);
  PUT(eglGetConfigAttrib(d,config,EGL_NATIVE_VISUAL_ID,&visual.value)&&visual.value==WINDOW_FORMAT_RGBA_8888&&visual.before==0x13572468&&visual.after==0x24681357);
  PUT(ANativeWindow_setBuffersGeometry(window,0,0,visual.value)==0);
  const EGLint context_attributes[]={EGL_CONTEXT_MAJOR_VERSION_KHR,3,EGL_CONTEXT_MINOR_VERSION_KHR,1,EGL_NONE};
  EGLContext context=eglCreateContext(d,config,EGL_NO_CONTEXT,context_attributes);PUT(context!=EGL_NO_CONTEXT);
  EGLSurface surface=eglCreateWindowSurface(d,config,window,0);PUT(surface!=EGL_NO_SURFACE);
  // The EGL bridge holds its own reference after the Android caller releases.
  ANativeWindow_release(window);
  PUT(eglMakeCurrent(d,surface,surface,context));
  PUT(eglGetCurrentContext()==context&&eglGetCurrentSurface(EGL_DRAW)==surface&&eglGetCurrentSurface(EGL_READ)==surface);
  PUT(eglQuerySurface(d,surface,EGL_WIDTH,&width.value)&&width.value==640&&width.before==0x13572468&&width.after==0x24681357);
  PUT(eglSwapInterval(d,0));PUT(host_egl_draw_check(640,360));PUT(eglSwapBuffers(d,surface));
  const EGLint pbuffer_attributes[]={EGL_WIDTH,16,EGL_HEIGHT,16,EGL_NONE};
  EGLSurface pbuffer=eglCreatePbufferSurface(d,config,pbuffer_attributes);PUT(pbuffer!=EGL_NO_SURFACE);
  PUT(eglMakeCurrent(d,pbuffer,pbuffer,context));PUT(host_egl_draw_check(16,16));
  PUT(eglDestroySurface(d,pbuffer));PUT(eglGetCurrentSurface(EGL_DRAW)==pbuffer);
  PUT(eglMakeCurrent(d,surface,surface,context));
  typedef EGLint (*ErrorProc)(void);
  ErrorProc error=(ErrorProc)eglGetProcAddress("eglGetError");PUT(error&&error()==EGL_SUCCESS);
  PUT(eglDestroyContext(d,context));PUT(eglGetCurrentContext()==context);
  PUT(eglDestroySurface(d,surface));PUT(eglGetCurrentSurface(EGL_DRAW)==surface);
  PUT(eglMakeCurrent(d,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT));
  PUT(eglGetCurrentContext()==EGL_NO_CONTEXT&&eglGetCurrentSurface(EGL_DRAW)==EGL_NO_SURFACE);
  PUT(eglTerminate(d));PUT(eglGetError()==EGL_SUCCESS);
  return n;
}

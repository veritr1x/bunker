#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <android/native_window_jni.h>
#include <stdint.h>
extern int host_egl_format_draw(int format);
int egl_format_guest(JNIEnv *env,jobject java_surface,int format,uint64_t *out){
  unsigned n=0;
#define PUT(value) out[n++]=(value)?1:0
  ANativeWindow *window=ANativeWindow_fromSurface(env,java_surface);PUT(window!=0);
  EGLDisplay display=eglGetDisplay(EGL_DEFAULT_DISPLAY);PUT(display!=EGL_NO_DISPLAY&&eglInitialize(display,0,0));
  const EGLint attributes[]={EGL_NATIVE_VISUAL_ID,format,EGL_SURFACE_TYPE,EGL_WINDOW_BIT,
    EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT_KHR,EGL_SAMPLES,0,EGL_NONE};
  EGLConfig config=0;EGLint count=0,alpha=-1;
  PUT(eglChooseConfig(display,attributes,&config,1,&count)&&count==1&&config);
  PUT(eglGetConfigAttrib(display,config,EGL_ALPHA_SIZE,&alpha)&&alpha==(format==1?8:0));
  PUT(ANativeWindow_setBuffersGeometry(window,0,0,format)==0);
  PUT(ANativeWindow_getWidth(window)==640&&ANativeWindow_getHeight(window)==360);
  const EGLint context_attributes[]={EGL_CONTEXT_MAJOR_VERSION_KHR,3,EGL_CONTEXT_MINOR_VERSION_KHR,1,EGL_NONE};
  EGLContext context=eglCreateContext(display,config,EGL_NO_CONTEXT,context_attributes);PUT(context!=EGL_NO_CONTEXT);
  EGLSurface surface=eglCreateWindowSurface(display,config,window,0);PUT(surface!=EGL_NO_SURFACE);
  PUT(eglMakeCurrent(display,surface,surface,context));PUT(host_egl_format_draw(format));PUT(eglSwapBuffers(display,surface));
  PUT(ANativeWindow_setBuffersGeometry(window,0,0,format==1?2:1)==-16);
  PUT(ANativeWindow_setBuffersGeometry(window,640,360,format)==-38);
  PUT(ANativeWindow_setBuffersGeometry(window,320,180,format)==-38);
  PUT(eglDestroySurface(display,surface));PUT(eglGetCurrentSurface(EGL_DRAW)==surface);
  PUT(ANativeWindow_setBuffersGeometry(window,0,0,format==1?2:1)==-16);
  PUT(host_egl_format_draw(format));
  PUT(eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT));PUT(eglDestroyContext(display,context));
  PUT(ANativeWindow_setBuffersGeometry(window,0,0,format==1?2:1)==0);
  PUT(eglCreateWindowSurface(display,config,window,0)==EGL_NO_SURFACE&&eglGetError()==EGL_BAD_MATCH);
  PUT(ANativeWindow_setBuffersGeometry(window,0,0,0)==0);
  PUT(eglTerminate(display));PUT(eglGetError()==EGL_SUCCESS);
  ANativeWindow_release(window);return n;
}

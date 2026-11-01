#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <android/native_window_jni.h>
#include <stdint.h>
extern int host_window_resize(int width,int height);
extern int host_buffer_draw(int width,int height);
int egl_scaling_guest(JNIEnv *env,jobject java_surface,uint64_t *out){
  unsigned n=0;
#define PUT(value) out[n++]=(value)?1:0
  ANativeWindow *window=ANativeWindow_fromSurface(env,java_surface);PUT(window!=0);
  PUT(ANativeWindow_setBuffersGeometry(window,640,360,1)==-38);
  EGLDisplay display=eglGetDisplay(EGL_DEFAULT_DISPLAY);PUT(display!=EGL_NO_DISPLAY&&eglInitialize(display,0,0));
  const EGLint config_attributes[]={EGL_NATIVE_VISUAL_ID,1,EGL_SURFACE_TYPE,EGL_WINDOW_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT_KHR,EGL_NONE};EGLConfig config=0;EGLint count=0,value=0;
  PUT(eglChooseConfig(display,config_attributes,&config,1,&count)&&count==1&&config);
  PUT(!eglGetConfigAttrib(display,config,0x7fffffff,&value));
  PUT(ANativeWindow_setBuffersGeometry(window,640,360,1)==0);
  PUT(eglGetError()==EGL_BAD_ATTRIBUTE&&eglGetError()==EGL_SUCCESS);
  PUT(host_window_resize(800,450));PUT(ANativeWindow_getWidth(window)==640&&ANativeWindow_getHeight(window)==360);
  const EGLint context_attributes[]={EGL_CONTEXT_MAJOR_VERSION_KHR,3,EGL_CONTEXT_MINOR_VERSION_KHR,1,EGL_NONE};EGLContext context=eglCreateContext(display,config,EGL_NO_CONTEXT,context_attributes);PUT(context!=EGL_NO_CONTEXT);
  const EGLint conflicting[]={EGL_WIDTH,320,EGL_NONE};PUT(eglCreateWindowSurface(display,config,window,conflicting)==EGL_NO_SURFACE&&eglGetError()==EGL_BAD_MATCH);
  EGLSurface surface=eglCreateWindowSurface(display,config,window,0);PUT(surface!=EGL_NO_SURFACE);PUT(eglMakeCurrent(display,surface,surface,context));
  PUT(eglQuerySurface(display,surface,EGL_WIDTH,&value)&&value==640);PUT(host_buffer_draw(640,360));PUT(eglSwapBuffers(display,surface));
  PUT(!eglGetConfigAttrib(display,config,0x7fffffff,&value));PUT(ANativeWindow_setBuffersGeometry(window,160,90,1)==0);
  PUT(eglGetError()==EGL_BAD_ATTRIBUTE&&eglGetError()==EGL_SUCCESS);
  PUT(ANativeWindow_getWidth(window)==160&&ANativeWindow_getHeight(window)==90);
  PUT(eglSwapBuffers(display,surface));PUT(eglQuerySurface(display,surface,EGL_WIDTH,&value)&&value==160);
  PUT(host_buffer_draw(160,90));PUT(eglSwapBuffers(display,surface));
  PUT(host_window_resize(960,540));PUT(ANativeWindow_getWidth(window)==160&&ANativeWindow_getHeight(window)==90);
  PUT(host_buffer_draw(160,90));PUT(eglSwapBuffers(display,surface));
  PUT(ANativeWindow_setBuffersGeometry(window,0,0,1)==-16);
  PUT(ANativeWindow_setBuffersGeometry(window,-1,-1,1)==-22);
  PUT(ANativeWindow_setBuffersGeometry(window,0,1,1)==-22);
  PUT(ANativeWindow_setBuffersGeometry(window,32768,90,1)==-22);
  PUT(ANativeWindow_setBuffersGeometry(window,160,90,4)==-38);
  PUT(ANativeWindow_getWidth(window)==160&&ANativeWindow_getHeight(window)==90);
  PUT(eglQuerySurface(display,surface,EGL_WIDTH,&value)&&value==160);
  PUT(eglDestroySurface(display,surface));PUT(ANativeWindow_setBuffersGeometry(window,128,72,1)==-16);
  PUT(eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT));
  PUT(ANativeWindow_setBuffersGeometry(window,128,72,1)==0);
  PUT(ANativeWindow_setBuffersGeometry(window,0,0,0)==0);
  PUT(ANativeWindow_getWidth(window)==960&&ANativeWindow_getHeight(window)==540);
  surface=eglCreateWindowSurface(display,config,window,0);PUT(surface!=EGL_NO_SURFACE);PUT(eglMakeCurrent(display,surface,surface,context));
  PUT(host_buffer_draw(960,540));PUT(eglSwapBuffers(display,surface));
  PUT(ANativeWindow_setBuffersGeometry(window,960,540,1)==-16);
  PUT(eglDestroySurface(display,surface));PUT(eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT));PUT(eglDestroyContext(display,context));
  PUT(eglTerminate(display));PUT(ANativeWindow_setBuffersGeometry(window,160,90,1)==-38);
  PUT(eglGetError()==EGL_SUCCESS);ANativeWindow_release(window);return n;
}

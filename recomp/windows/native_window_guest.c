#include <android/native_window.h>
#include <android/native_window_jni.h>
#include <stdint.h>
int window_guest(JNIEnv *env,jobject surface,int64_t *out){
  ANativeWindow *window=ANativeWindow_fromSurface(env,surface);
  if(!window)return -1;
  unsigned n=0;out[n++]=(int64_t)window;
  out[n++]=ANativeWindow_getWidth(window);out[n++]=ANativeWindow_getHeight(window);
  ANativeWindow_acquire(window);
  out[n++]=ANativeWindow_setBuffersGeometry(window,0,0,WINDOW_FORMAT_RGBA_8888);
  out[n++]=ANativeWindow_setBuffersGeometry(window,256,256,WINDOW_FORMAT_RGBA_8888);
  out[n++]=ANativeWindow_setBuffersGeometry(window,640,360,WINDOW_FORMAT_RGBA_8888);
  out[n++]=ANativeWindow_setBuffersGeometry(window,0,1,0);
  out[n++]=ANativeWindow_setBuffersGeometry(window,-1,-1,0);
  out[n++]=ANativeWindow_setBuffersGeometry(window,0,0,123456);
  out[n++]=ANativeWindow_getWidth(window);out[n++]=ANativeWindow_getHeight(window);
  ANativeWindow_release(window);ANativeWindow_release(window);
  out[n++]=ANativeWindow_fromSurface(env,0)==0;
  return n;
}

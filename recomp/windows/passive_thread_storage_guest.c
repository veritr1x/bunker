#include <pthread.h>
#include <EGL/egl.h>
#include <stdint.h>
struct observed {uint64_t token,destructors;int32_t initial,error,cleared,key_result;};
void storage_guest_destructor(void *p){++*(uint64_t*)p;}
uint64_t storage_guest_tick(void){return 0x123456789abcdef0ULL;}
uint64_t storage_guest_probe(struct observed *out,pthread_key_t key){
 out->token=(uint64_t)pthread_self();out->key_result=pthread_setspecific(key,&out->destructors);
 out->initial=eglGetError();eglSwapBuffers((EGLDisplay)(uintptr_t)0x1234,(EGLSurface)0);
 out->error=eglGetError();out->cleared=eglGetError();return out->token;
}

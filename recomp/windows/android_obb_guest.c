#include <jni.h>
#include <stdarg.h>
static jobject invoke_v(JNIEnv *e,jobject o,jmethodID m,...){va_list v;va_start(v,m);jobject r=(*e)->CallObjectMethodV(e,o,m,v);va_end(v);return r;}
jobject obb_get(JNIEnv *e,jobject context,jint single,jint mode){
  jclass c=(*e)->GetObjectClass(e,context);if(!c)return 0;
  jmethodID m=(*e)->GetMethodID(e,c,single?"getObbDir":"getObbDirs",single?"()Ljava/io/File;":"()[Ljava/io/File;");(*e)->DeleteLocalRef(e,c);if(!m)return 0;
  if(mode==0)return (*e)->CallObjectMethod(e,context,m);if(mode==1)return invoke_v(e,context,m);return (*e)->CallObjectMethodA(e,context,m,0);
}
jstring obb_path(JNIEnv *e,jobject file,jint mode){jclass c=(*e)->GetObjectClass(e,file);if(!c)return 0;jmethodID m=(*e)->GetMethodID(e,c,"getAbsolutePath","()Ljava/lang/String;");(*e)->DeleteLocalRef(e,c);if(!m)return 0;if(mode==0)return (*e)->CallObjectMethod(e,file,m);if(mode==1)return invoke_v(e,file,m);return (*e)->CallObjectMethodA(e,file,m,0);}
jint obb_array_length(JNIEnv *e,jobjectArray array){jclass actual=(*e)->GetObjectClass(e,array),expected=(*e)->FindClass(e,"[Ljava/io/File;");jboolean same=(*e)->IsSameObject(e,actual,expected);(*e)->DeleteLocalRef(e,actual);(*e)->DeleteLocalRef(e,expected);return same?(*e)->GetArrayLength(e,array):-1;}
jobject obb_element(JNIEnv *e,jobjectArray array,jint index){return (*e)->GetObjectArrayElement(e,array,index);}
void obb_replace(JNIEnv *e,jobjectArray array,jint index,jobject value){(*e)->SetObjectArrayElement(e,array,index,value);}

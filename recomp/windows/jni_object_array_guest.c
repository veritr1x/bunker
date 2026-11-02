#include <jni.h>
#include <stdint.h>
jobjectArray array_new(JNIEnv *e,jint length,jclass component,jobject initial){return (*e)->NewObjectArray(e,length,component,initial);}
jint array_length(JNIEnv *e,jarray array){return (*e)->GetArrayLength(e,array);}
jobject array_get(JNIEnv *e,jobjectArray array,jint index){return (*e)->GetObjectArrayElement(e,array,index);}
void array_set(JNIEnv *e,jobjectArray array,jint index,jobject value){(*e)->SetObjectArrayElement(e,array,index,value);}
jclass array_find(JNIEnv *e,const char *name){return (*e)->FindClass(e,name);}
jobject array_frame(JNIEnv *e,jclass component,jobject initial){
  if((*e)->PushLocalFrame(e,8))return 0;
  jobject array=(*e)->NewObjectArray(e,3,component,initial);
  return (*e)->PopLocalFrame(e,array);
}
uint32_t array_shape(JNIEnv *e,jobject array,const char *descriptor){
  uint32_t bits=0;jclass actual=(*e)->GetObjectClass(e,array),expected=(*e)->FindClass(e,descriptor);
  if((*e)->IsSameObject(e,actual,expected))bits|=1;
  jclass object=(*e)->FindClass(e,"java/lang/Object"),parent=(*e)->GetSuperclass(e,actual);
  if((*e)->IsSameObject(e,parent,object))bits|=2;
  if((*e)->IsInstanceOf(e,array,object))bits|=4;
  jclass cloneable=(*e)->FindClass(e,"java/lang/Cloneable"),serializable=(*e)->FindClass(e,"java/io/Serializable");
  if((*e)->IsInstanceOf(e,array,cloneable)&&(*e)->IsInstanceOf(e,array,serializable))bits|=8;
  (*e)->DeleteLocalRef(e,actual);(*e)->DeleteLocalRef(e,expected);(*e)->DeleteLocalRef(e,object);
  (*e)->DeleteLocalRef(e,parent);(*e)->DeleteLocalRef(e,cloneable);(*e)->DeleteLocalRef(e,serializable);return bits;
}

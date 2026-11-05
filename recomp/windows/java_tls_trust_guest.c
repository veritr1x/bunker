#include <jni.h>
#include <stdarg.h>
static jobject tls_object_v(JNIEnv*e,jobject receiver,jmethodID method,int is_static,...){va_list values;va_start(values,is_static);jobject value=is_static?(*e)->CallStaticObjectMethodV(e,(jclass)receiver,method,values):(*e)->CallObjectMethodV(e,receiver,method,values);va_end(values);return value;}
static void tls_void_v(JNIEnv*e,jobject receiver,jmethodID method,...){va_list values;va_start(values,method);(*e)->CallVoidMethodV(e,receiver,method,values);va_end(values);}
jclass tls_find(JNIEnv*e,const char*name){return(*e)->FindClass(e,name);}
jint tls_assignable(JNIEnv*e,jclass from,jclass to){return(*e)->IsAssignableFrom(e,from,to);}
jmethodID tls_method(JNIEnv*e,jclass owner,const char*name,const char*signature,int is_static){return is_static?(*e)->GetStaticMethodID(e,owner,name,signature):(*e)->GetMethodID(e,owner,name,signature);}
jobject tls_object(JNIEnv*e,jobject receiver,jmethodID method,jobject argument,int has_argument,int is_static,int form){
 if(form==0){if(is_static)return has_argument?(*e)->CallStaticObjectMethod(e,(jclass)receiver,method,argument):(*e)->CallStaticObjectMethod(e,(jclass)receiver,method);return has_argument?(*e)->CallObjectMethod(e,receiver,method,argument):(*e)->CallObjectMethod(e,receiver,method);}
 if(form==1)return has_argument?tls_object_v(e,receiver,method,is_static,argument):tls_object_v(e,receiver,method,is_static);
 jvalue value;value.l=argument;if(is_static)return(*e)->CallStaticObjectMethodA(e,(jclass)receiver,method,has_argument?&value:0);return(*e)->CallObjectMethodA(e,receiver,method,has_argument?&value:0);
}
void tls_void(JNIEnv*e,jobject receiver,jmethodID method,jobject argument,int form){if(form==0)(*e)->CallVoidMethod(e,receiver,method,argument);else if(form==1)tls_void_v(e,receiver,method,argument);else{jvalue value;value.l=argument;(*e)->CallVoidMethodA(e,receiver,method,&value);}}
jsize tls_length(JNIEnv*e,jarray array){return(*e)->GetArrayLength(e,array);}
jobject tls_element(JNIEnv*e,jobjectArray array,jsize index){return(*e)->GetObjectArrayElement(e,array,index);}
void tls_set_element(JNIEnv*e,jobjectArray array,jsize index,jobject value){(*e)->SetObjectArrayElement(e,array,index,value);}
void tls_byte_region(JNIEnv*e,jbyteArray array,jsize start,jsize length,jbyte*output){(*e)->GetByteArrayRegion(e,array,start,length,output);}
void tls_set_byte(JNIEnv*e,jbyteArray array,jsize index,jbyte value){(*e)->SetByteArrayRegion(e,array,index,1,&value);}
jbyte*tls_byte_elements(JNIEnv*e,jbyteArray array,jboolean*copy){return(*e)->GetByteArrayElements(e,array,copy);}
void tls_release_bytes(JNIEnv*e,jbyteArray array,jbyte*bytes,jint mode){(*e)->ReleaseByteArrayElements(e,array,bytes,mode);}
jint tls_shape(JNIEnv*e,jobject object,jclass clazz){jclass actual=(*e)->GetObjectClass(e,object);jint result=((*e)->IsInstanceOf(e,object,clazz)?1:0)|((*e)->IsSameObject(e,actual,clazz)?2:0);(*e)->DeleteLocalRef(e,actual);return result;}
jthrowable tls_exception(JNIEnv*e){return(*e)->ExceptionOccurred(e);}
void tls_clear(JNIEnv*e){(*e)->ExceptionClear(e);}
jint tls_same(JNIEnv*e,jobject first,jobject second){return(*e)->IsSameObject(e,first,second);}
jint tls_push(JNIEnv*e,jint capacity){return(*e)->PushLocalFrame(e,capacity);}
jobject tls_pop(JNIEnv*e,jobject result){return(*e)->PopLocalFrame(e,result);}
jobject tls_reference(JNIEnv*e,jobject object,jint operation){if(operation==0)return(*e)->NewGlobalRef(e,object);if(operation==1){(*e)->DeleteGlobalRef(e,object);return 0;}if(operation==2)return(*e)->NewWeakGlobalRef(e,object);if(operation==3){(*e)->DeleteWeakGlobalRef(e,object);return 0;}(*e)->DeleteLocalRef(e,object);return 0;}

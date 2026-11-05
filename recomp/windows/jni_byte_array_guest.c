#include <jni.h>
#include <stdint.h>
#include <stddef.h>
_Static_assert(sizeof(jbyte)==1&&(jbyte)-1<0&&sizeof(jboolean)==1&&sizeof(jsize)==4,"JNI byte/size ABI");
_Static_assert(offsetof(struct JNINativeInterface,NewByteArray)==176*8&&offsetof(struct JNINativeInterface,GetByteArrayElements)==184*8&&offsetof(struct JNINativeInterface,ReleaseByteArrayElements)==192*8&&offsetof(struct JNINativeInterface,GetByteArrayRegion)==200*8&&offsetof(struct JNINativeInterface,SetByteArrayRegion)==208*8&&offsetof(struct JNINativeInterface,GetArrayLength)==171*8,"exact NDK JNI table slots");
uintptr_t byte_dispatch(JNIEnv*e,unsigned op,uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t d){
 switch(op){
 case 0:return(uintptr_t)(*e)->NewByteArray(e,(jsize)a);
 case 1:return(uintptr_t)(*e)->GetArrayLength(e,(jarray)a);
 case 2:return(uintptr_t)(*e)->GetByteArrayElements(e,(jbyteArray)a,(jboolean*)b);
 case 3:(*e)->ReleaseByteArrayElements(e,(jbyteArray)a,(jbyte*)b,(jint)c);return 0;
 case 4:(*e)->GetByteArrayRegion(e,(jbyteArray)a,(jsize)b,(jsize)c,(jbyte*)d);return 0;
 case 5:(*e)->SetByteArrayRegion(e,(jbyteArray)a,(jsize)b,(jsize)c,(const jbyte*)d);return 0;
 case 6:return(uintptr_t)(*e)->FindClass(e,(const char*)a);
 case 7:return(uintptr_t)(*e)->NewGlobalRef(e,(jobject)a);
 case 8:(*e)->DeleteGlobalRef(e,(jobject)a);return 0;
 case 9:return(uintptr_t)(*e)->NewLocalRef(e,(jobject)a);
 case 10:(*e)->DeleteLocalRef(e,(jobject)a);return 0;
 case 11:return(uintptr_t)(*e)->NewWeakGlobalRef(e,(jobject)a);
 case 12:(*e)->DeleteWeakGlobalRef(e,(jweak)a);return 0;
 case 13:return(uintptr_t)(*e)->IsSameObject(e,(jobject)a,(jobject)b);
 case 14:return(uintptr_t)(*e)->GetObjectRefType(e,(jobject)a);
 case 15:return(uintptr_t)(*e)->NewObjectArray(e,(jsize)a,(jclass)b,(jobject)c);
 case 16:return(uintptr_t)(*e)->GetObjectArrayElement(e,(jobjectArray)a,(jsize)b);
 case 17:(*e)->SetObjectArrayElement(e,(jobjectArray)a,(jsize)b,(jobject)c);return 0;
 case 18:return(uintptr_t)(*e)->GetMethodID(e,(jclass)a,(const char*)b,(const char*)c);
 case 19:{jvalue arg;arg.l=(jobject)c;return(uintptr_t)(*e)->CallObjectMethodA(e,(jobject)a,(jmethodID)b,&arg);}
 case 20:return(uintptr_t)(*e)->GetFieldID(e,(jclass)a,(const char*)b,(const char*)c);
 case 21:(*e)->SetObjectField(e,(jobject)a,(jfieldID)b,(jobject)c);return 0;
 case 22:return(uintptr_t)(*e)->GetObjectField(e,(jobject)a,(jfieldID)b);
 case 23:return(uintptr_t)(*e)->PushLocalFrame(e,(jint)a);
 case 24:return(uintptr_t)(*e)->PopLocalFrame(e,(jobject)a);
 case 25:return(uintptr_t)(*e)->IsInstanceOf(e,(jobject)a,(jclass)b);
 default:return UINTPTR_MAX;
 }
}
uint32_t byte_shape(JNIEnv*e,jobject array){
 jclass actual=(*e)->GetObjectClass(e,array),bytes=(*e)->FindClass(e,"[B"),object=(*e)->FindClass(e,"java/lang/Object"),clone=(*e)->FindClass(e,"java/lang/Cloneable"),serial=(*e)->FindClass(e,"java/io/Serializable"),objects=(*e)->FindClass(e,"[Ljava/lang/Object;");
 uint32_t bits=(*e)->IsSameObject(e,actual,bytes)?1:0;
 if((*e)->IsInstanceOf(e,array,object))bits|=2;if((*e)->IsInstanceOf(e,array,clone))bits|=4;if((*e)->IsInstanceOf(e,array,serial))bits|=8;if(!(*e)->IsInstanceOf(e,array,objects))bits|=16;
 return bits;
}

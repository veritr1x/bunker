#include <jni.h>
#include <stdarg.h>
JNIEXPORT jobject JNICALL Java_FieldFourContract_nativeField(JNIEnv*e,jclass self,jclass owner,jboolean stat){
 (void)self;jfieldID id=stat?(*e)->GetStaticFieldID(e,owner,"staticText","Ljava/lang/String;"):(*e)->GetFieldID(e,owner,"integer","I");
 if(!id)return 0;
 jobject field=(*e)->ToReflectedField(e,owner,id,stat);
 if(field&&(*e)->FromReflectedField(e,field)!=id){jclass error=(*e)->FindClass(e,"java/lang/AssertionError");(*e)->ThrowNew(e,error,"Field ID roundtrip");return 0;}
 return field;
}
static jobject four_v(JNIEnv*e,jclass self,jmethodID method,...){va_list a;va_start(a,method);jobject out=(*e)->CallStaticObjectMethodV(e,self,method,a);va_end(a);return out;}
JNIEXPORT jobject JNICALL Java_FieldFourContract_nativeFour(JNIEnv*e,jclass self,jint form,jboolean flag){
 jclass owner=(*e)->FindClass(e,"FieldFourContract$Base");jstring name=(*e)->NewStringUTF(e,"integer"),signature=(*e)->NewStringUTF(e,"I");jmethodID method=(*e)->GetStaticMethodID(e,self,"four","(Ljava/lang/Class;Ljava/lang/String;Ljava/lang/String;Z)Ljava/lang/Object;");
 jvalue a[4]={{.l=owner},{.l=name},{.l=signature},{.j=(jlong)0xaabbccddeeff0000ULL}};a[3].z=flag;
 return form==0?(*e)->CallStaticObjectMethod(e,self,method,owner,name,signature,(int)flag):form==1?four_v(e,self,method,owner,name,signature,(int)flag):(*e)->CallStaticObjectMethodA(e,self,method,a);
}

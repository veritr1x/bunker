#include <jni.h>
#include <stdint.h>
jfieldID display_service_field(JNIEnv *e,jclass owner,const char *signature){return (*e)->GetStaticFieldID(e,owner,"DISPLAY_SERVICE",signature);}
jstring display_service_get(JNIEnv *e,jclass owner,jfieldID field){return(jstring)(*e)->GetStaticObjectField(e,owner,field);}
jstring display_service_lookup(JNIEnv *e,const char *name){jclass owner=(*e)->FindClass(e,name);jfieldID field=(*e)->GetStaticFieldID(e,owner,"DISPLAY_SERVICE","Ljava/lang/String;");jstring value=(jstring)(*e)->GetStaticObjectField(e,owner,field);(*e)->DeleteLocalRef(e,owner);return value;}
void display_service_store(JNIEnv *e,jclass owner,jfieldID field,jobject value){(*e)->SetStaticObjectField(e,owner,field,value);}

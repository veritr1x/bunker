#include <jni.h>
#include <stdint.h>
jfieldID location_service_field(JNIEnv *e,jclass owner,const char *signature){return (*e)->GetStaticFieldID(e,owner,"LOCATION_SERVICE",signature);}
jstring location_service_get(JNIEnv *e,jclass owner,jfieldID field){return(jstring)(*e)->GetStaticObjectField(e,owner,field);}
jstring location_service_lookup(JNIEnv *e,const char *name){jclass owner=(*e)->FindClass(e,name);jfieldID field=(*e)->GetStaticFieldID(e,owner,"LOCATION_SERVICE","Ljava/lang/String;");jstring value=(jstring)(*e)->GetStaticObjectField(e,owner,field);(*e)->DeleteLocalRef(e,owner);return value;}
void location_service_store(JNIEnv *e,jclass owner,jfieldID field,jobject value){(*e)->SetStaticObjectField(e,owner,field,value);}

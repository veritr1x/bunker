#include <jni.h>
jfieldID manufacturer_field(JNIEnv *e,jclass c,const char *s){return (*e)->GetStaticFieldID(e,c,"MANUFACTURER",s);}
jstring manufacturer_get(JNIEnv *e,jclass c,jfieldID f){return(jstring)(*e)->GetStaticObjectField(e,c,f);}
jstring manufacturer_lookup(JNIEnv *e){jclass c=(*e)->FindClass(e,"android/os/Build");jfieldID f=(*e)->GetStaticFieldID(e,c,"MANUFACTURER","Ljava/lang/String;");jstring v=(jstring)(*e)->GetStaticObjectField(e,c,f);(*e)->DeleteLocalRef(e,c);return v;}
int manufacturer_utf8(JNIEnv *e,jstring value){const char*p=(*e)->GetStringUTFChars(e,value,0);if(!p)return -1;int match=p[0]=='u'&&p[1]=='n'&&p[2]=='k'&&p[3]=='n'&&p[4]=='o'&&p[5]=='w'&&p[6]=='n'&&p[7]==0;(*e)->ReleaseStringUTFChars(e,value,p);return match;}

#include <jni.h>
jfieldID model_field(JNIEnv *e,jclass c,const char *s){return (*e)->GetStaticFieldID(e,c,"MODEL",s);}
jstring model_get(JNIEnv *e,jclass c,jfieldID f){return(jstring)(*e)->GetStaticObjectField(e,c,f);}
jstring model_lookup(JNIEnv *e){jclass c=(*e)->FindClass(e,"android/os/Build");jfieldID f=(*e)->GetStaticFieldID(e,c,"MODEL","Ljava/lang/String;");jstring v=(jstring)(*e)->GetStaticObjectField(e,c,f);(*e)->DeleteLocalRef(e,c);return v;}
int model_utf8(JNIEnv *e,jstring value){const char*p=(*e)->GetStringUTFChars(e,value,0);if(!p)return -1;int match=p[0]=='u'&&p[1]=='n'&&p[2]=='k'&&p[3]=='n'&&p[4]=='o'&&p[5]=='w'&&p[6]=='n'&&p[7]==0;(*e)->ReleaseStringUTFChars(e,value,p);return match;}

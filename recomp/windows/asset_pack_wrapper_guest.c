#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
static uint32_t TEST_callbacks,TEST_deletes;
JNIEXPORT void JNICALL asset_TEST_callback(JNIEnv *e,jclass c){(void)e;(void)c;++TEST_callbacks;}
JNIEXPORT void JNICALL asset_TEST_delete(JNIEnv *e,jclass c){(void)e;(void)c;++TEST_deletes;}
uint64_t asset_TEST_counts(void){return((uint64_t)TEST_deletes<<32)|TEST_callbacks;}
jint asset_TEST_register(JNIEnv *e){jclass c=(*e)->FindClass(e,"TEST/AssetPackProbe");JNINativeMethod m[]={{"callback","()V",(void*)asset_TEST_callback},{"delete","()V",(void*)asset_TEST_delete}};jint r=(*e)->RegisterNatives(e,c,m,2);(*e)->DeleteLocalRef(e,c);return r;}
static jobject object_v(JNIEnv *e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jobject r=(*e)->CallStaticObjectMethodV(e,c,m,a);va_end(a);return r;}
jobject asset_init(JNIEnv *e,jobject context,jint mode){
 jclass c=(*e)->FindClass(e,"com/unity3d/player/AssetPackManagerWrapper");jmethodID m=(*e)->GetStaticMethodID(e,c,"init","(Landroid/content/Context;)Lcom/unity3d/player/AssetPackManagerWrapper;");jobject r;
 if(mode==0)r=(*e)->CallStaticObjectMethod(e,c,m,context);else if(mode==1)r=object_v(e,c,m,context);else{jvalue a[1];a[0].l=context;r=(*e)->CallStaticObjectMethodA(e,c,m,a);}(*e)->DeleteLocalRef(e,c);return r;
}
static jboolean boolean_v(JNIEnv *e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jboolean r=(*e)->CallBooleanMethodV(e,o,m,a);va_end(a);return r;}
jboolean asset_missing(JNIEnv *e,jobject o,jint mode){jclass c=(*e)->GetObjectClass(e,o);jmethodID m=(*e)->GetMethodID(e,c,"playCoreApiMissing","()Z");jboolean r;if(mode==0)r=(*e)->CallBooleanMethod(e,o,m);else if(mode==1)r=boolean_v(e,o,m);else r=(*e)->CallBooleanMethodA(e,o,m,0);(*e)->DeleteLocalRef(e,c);return r;}
jobject asset_static(JNIEnv *e){jclass c=(*e)->FindClass(e,"com/unity3d/player/AssetPackManagerWrapper");jfieldID f=(*e)->GetStaticFieldID(e,c,"a","Lcom/unity3d/player/AssetPackManagerWrapper;");jobject r=(*e)->GetStaticObjectField(e,c,f);(*e)->DeleteLocalRef(e,c);return r;}
jobject asset_field(JNIEnv *e,jobject o,jint which){const char *name=which==0?"b":which==1?"c":"d",*sig=which==0?"Lcom/google/android/play/core/assetpacks/AssetPackManager;":which==1?"Ljava/util/HashSet;":"Ljava/lang/Object;";jclass c=(*e)->GetObjectClass(e,o);jfieldID f=(*e)->GetFieldID(e,c,name,sig);jobject r=(*e)->GetObjectField(e,o,f);(*e)->DeleteLocalRef(e,c);return r;}
jobject asset_take_exception(JNIEnv *e){jthrowable t=(*e)->ExceptionOccurred(e);(*e)->ExceptionClear(e);return t;}
jobject asset_path(JNIEnv *e,jobject o){jclass c=(*e)->GetObjectClass(e,o);jmethodID m=(*e)->GetMethodID(e,c,"getAssetPackPath","(Ljava/lang/String;)Ljava/lang/String;");return(*e)->CallObjectMethod(e,o,m,0);}
jobject asset_get_instance(JNIEnv *e){jclass c=(*e)->FindClass(e,"com/unity3d/player/AssetPackManagerWrapper");jmethodID m=(*e)->GetStaticMethodID(e,c,"getInstance","()Lcom/unity3d/player/AssetPackManagerWrapper;");return(*e)->CallStaticObjectMethod(e,c,m);}

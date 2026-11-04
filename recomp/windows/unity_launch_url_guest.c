#include <jni.h>
#include <stdarg.h>
#include <stddef.h>
_Static_assert(offsetof(struct JNINativeInterface,CallObjectMethodV)==35*8,"actual NDK object V slot");
static jobject url_v(JNIEnv*e,jobject o,jmethodID m,...){va_list v;va_start(v,m);jobject r=(*e)->CallObjectMethodV(e,o,m,v);va_end(v);return r;}
jobject launch_url(JNIEnv*e,jobject o,jmethodID m,int mode){if(mode==0)return(*e)->CallObjectMethod(e,o,m);if(mode==1)return url_v(e,o,m);return(*e)->CallObjectMethodA(e,o,m,NULL);}
jobject launch_uri_field(JNIEnv*e,jobject player){jclass c=(*e)->FindClass(e,"com/unity3d/player/UnityPlayer");jfieldID f=(*e)->GetFieldID(e,c,"m_launchUri","Landroid/net/Uri;");(*e)->DeleteLocalRef(e,c);return(*e)->GetObjectField(e,player,f);}
void launch_set_uri(JNIEnv*e,jobject player,jobject uri){jclass c=(*e)->FindClass(e,"com/unity3d/player/UnityPlayer");jfieldID f=(*e)->GetFieldID(e,c,"m_launchUri","Landroid/net/Uri;");(*e)->DeleteLocalRef(e,c);(*e)->SetObjectField(e,player,f,uri);}

// TEST-only strict NDK callers. No original Unity addresses or native callbacks.
#include <jni.h>
#include <stdarg.h>
#include <stdint.h>
static jmethodID mid(JNIEnv*e,const char*c,const char*n,const char*s){jclass k=(*e)->FindClass(e,c);jmethodID m=(*e)->GetMethodID(e,k,n,s);(*e)->DeleteLocalRef(e,k);return m;}
static jobject ov(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jobject v=(*e)->CallObjectMethodV(e,o,m,a);va_end(a);return v;}
static jint iv(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jint v=(*e)->CallIntMethodV(e,o,m,a);va_end(a);return v;}
static jfloat fv(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jfloat v=(*e)->CallFloatMethodV(e,o,m,a);va_end(a);return v;}
static jboolean bv(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);jboolean v=(*e)->CallBooleanMethodV(e,o,m,a);va_end(a);return v;}
static void vv(JNIEnv*e,jobject o,jmethodID m,...){va_list a;va_start(a,m);(*e)->CallVoidMethodV(e,o,m,a);va_end(a);}
static jobject sv(JNIEnv*e,jclass c,jmethodID m,...){va_list a;va_start(a,m);jobject v=(*e)->CallStaticObjectMethodV(e,c,m,a);va_end(a);return v;}
jobject prefs_open(JNIEnv*e,jobject context,jstring name,jint form){jmethodID m=mid(e,"android/content/Context","getSharedPreferences","(Ljava/lang/String;I)Landroid/content/SharedPreferences;");jvalue a[2];a[0].l=name;a[1].i=0;return form==0?(*e)->CallObjectMethod(e,context,m,name,0):form==1?ov(e,context,m,name,0):(*e)->CallObjectMethodA(e,context,m,a);}
jobject prefs_open_mode(JNIEnv*e,jobject context,jstring name,jint mode){return (*e)->CallObjectMethod(e,context,mid(e,"android/content/Context","getSharedPreferences","(Ljava/lang/String;I)Landroid/content/SharedPreferences;"),name,mode);}
jobject prefs_edit(JNIEnv*e,jobject p,jint form){jmethodID m=mid(e,"android/content/SharedPreferences","edit","()Landroid/content/SharedPreferences$Editor;");return form==0?(*e)->CallObjectMethod(e,p,m):form==1?ov(e,p,m):(*e)->CallObjectMethodA(e,p,m,0);}
jint prefs_getint(JNIEnv*e,jobject p,jstring key,jint def,jint form){jmethodID m=mid(e,"android/content/SharedPreferences","getInt","(Ljava/lang/String;I)I");jvalue a[2];a[0].l=key;a[1].i=def;return form==0?(*e)->CallIntMethod(e,p,m,key,def):form==1?iv(e,p,m,key,def):(*e)->CallIntMethodA(e,p,m,a);}
jobject prefs_put(JNIEnv*e,jobject p,jstring key,uint64_t value,jint kind,jint form){jvalue a[2];a[0].l=key;const char*n=kind==1?"putString":kind==2?"putInt":"putFloat";const char*s=kind==1?"(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;":kind==2?"(Ljava/lang/String;I)Landroid/content/SharedPreferences$Editor;":"(Ljava/lang/String;F)Landroid/content/SharedPreferences$Editor;";jmethodID m=mid(e,"android/content/SharedPreferences$Editor",n,s);if(kind==1){a[1].l=(jobject)value;return form==0?(*e)->CallObjectMethod(e,p,m,key,(jobject)value):form==1?ov(e,p,m,key,(jobject)value):(*e)->CallObjectMethodA(e,p,m,a);}if(kind==2){a[1].i=(jint)value;return form==0?(*e)->CallObjectMethod(e,p,m,key,(jint)value):form==1?ov(e,p,m,key,(jint)value):(*e)->CallObjectMethodA(e,p,m,a);}union{uint32_t i;float f;}v;v.i=(uint32_t)value;a[1].f=v.f;return form==0?(*e)->CallObjectMethod(e,p,m,key,v.f):form==1?ov(e,p,m,key,v.f):(*e)->CallObjectMethodA(e,p,m,a);}
void prefs_apply(JNIEnv*e,jobject p,jint form){jmethodID m=mid(e,"android/content/SharedPreferences$Editor","apply","()V");if(form==0)(*e)->CallVoidMethod(e,p,m);else if(form==1)vv(e,p,m);else(*e)->CallVoidMethodA(e,p,m,0);}
jobject prefs_all(JNIEnv*e,jobject p,jint form){jmethodID m=mid(e,"android/content/SharedPreferences","getAll","()Ljava/util/Map;");return form==0?(*e)->CallObjectMethod(e,p,m):form==1?ov(e,p,m):(*e)->CallObjectMethodA(e,p,m,0);}
jobject prefs_entries(JNIEnv*e,jobject p){return (*e)->CallObjectMethod(e,p,mid(e,"java/util/Map","entrySet","()Ljava/util/Set;"));}
jobject prefs_iterator(JNIEnv*e,jobject p){return (*e)->CallObjectMethod(e,p,mid(e,"java/util/Set","iterator","()Ljava/util/Iterator;"));}
jint prefs_hasnext(JNIEnv*e,jobject p,jint form){jmethodID m=mid(e,"java/util/Iterator","hasNext","()Z");return form==0?(*e)->CallBooleanMethod(e,p,m):form==1?bv(e,p,m):(*e)->CallBooleanMethodA(e,p,m,0);}
jobject prefs_next(JNIEnv*e,jobject p,jint form){jmethodID m=mid(e,"java/util/Iterator","next","()Ljava/lang/Object;");return form==0?(*e)->CallObjectMethod(e,p,m):form==1?ov(e,p,m):(*e)->CallObjectMethodA(e,p,m,0);}
jobject prefs_entry(JNIEnv*e,jobject p,jint value){return (*e)->CallObjectMethod(e,p,mid(e,"java/util/Map$Entry",value?"getValue":"getKey","()Ljava/lang/Object;"));}
uint64_t prefs_numeric(JNIEnv*e,jobject p,jint kind,jint form){if(kind==2){jmethodID m=mid(e,"java/lang/Number","intValue","()I");jint n=form==0?(*e)->CallIntMethod(e,p,m):form==1?iv(e,p,m):(*e)->CallIntMethodA(e,p,m,0);return(uint32_t)n;}jmethodID m=mid(e,"java/lang/Number","floatValue","()F");union{uint32_t i;float f;}v;v.f=form==0?(*e)->CallFloatMethod(e,p,m):form==1?fv(e,p,m):(*e)->CallFloatMethodA(e,p,m,0);return v.i;}
jobject prefs_encode(JNIEnv*e,jstring s,jint form){jclass c=(*e)->FindClass(e,"android/net/Uri");jmethodID m=(*e)->GetStaticMethodID(e,c,"encode","(Ljava/lang/String;)Ljava/lang/String;");jvalue a;a.l=s;jobject v=form==0?(*e)->CallStaticObjectMethod(e,c,m,s):form==1?sv(e,c,m,s):(*e)->CallStaticObjectMethodA(e,c,m,&a);(*e)->DeleteLocalRef(e,c);return v;}
// TEST implementation of the independently decoded migration's API sequence.
// This qualifies the provider data flow, never substitutes for the original
// Unity routine in a game frame or claims to execute that original routine.
void prefs_TEST_migrate(JNIEnv*e,jobject context,jstring legacy,jstring modern){
 jobject p=prefs_open(e,context,modern,0),editor=prefs_edit(e,p,0);jstring marker=(*e)->NewStringUTF(e,"__UNITY_PLAYERPREFS_VERSION__");
 if(!prefs_getint(e,p,marker,0,0)){jobject old=prefs_open(e,context,legacy,0),map=prefs_all(e,old,0),set=prefs_entries(e,map),it=prefs_iterator(e,set);jclass str=(*e)->FindClass(e,"java/lang/String"),integer=(*e)->FindClass(e,"java/lang/Integer"),floating=(*e)->FindClass(e,"java/lang/Float");
  while(prefs_hasnext(e,it,0)){jobject entry=prefs_next(e,it,0),key=prefs_entry(e,entry,0),value=prefs_entry(e,entry,1),encoded=0,out=0;
   if((*e)->IsInstanceOf(e,value,str)){encoded=prefs_encode(e,(jstring)key,0);jobject text=prefs_encode(e,(jstring)value,0);out=prefs_put(e,editor,(jstring)encoded,(uint64_t)text,1,0);(*e)->DeleteLocalRef(e,text);}else if((*e)->IsInstanceOf(e,value,integer)){encoded=prefs_encode(e,(jstring)key,0);out=prefs_put(e,editor,(jstring)encoded,prefs_numeric(e,value,2,0),2,0);}else if((*e)->IsInstanceOf(e,value,floating)){encoded=prefs_encode(e,(jstring)key,0);out=prefs_put(e,editor,(jstring)encoded,prefs_numeric(e,value,3,0),3,0);}
   if(out)(*e)->DeleteLocalRef(e,out);if(encoded)(*e)->DeleteLocalRef(e,encoded);(*e)->DeleteLocalRef(e,value);(*e)->DeleteLocalRef(e,key);(*e)->DeleteLocalRef(e,entry);
  }(*e)->DeleteLocalRef(e,str);(*e)->DeleteLocalRef(e,integer);(*e)->DeleteLocalRef(e,floating);(*e)->DeleteLocalRef(e,it);(*e)->DeleteLocalRef(e,set);(*e)->DeleteLocalRef(e,map);(*e)->DeleteLocalRef(e,old);
 }jobject out=prefs_put(e,editor,marker,1,2,0);(*e)->DeleteLocalRef(e,out);prefs_apply(e,editor,0);(*e)->DeleteLocalRef(e,marker);(*e)->DeleteLocalRef(e,editor);(*e)->DeleteLocalRef(e,p);
}

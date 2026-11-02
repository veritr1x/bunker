#include <jni.h>
#include <stdint.h>
#include <stdarg.h>
static const char *names[]={"onLocationChanged","onLocationChanged","onFlushComplete","onStatusChanged","onProviderEnabled","onProviderDisabled"};
static const char *signatures[]={"(Landroid/location/Location;)V","(Ljava/util/List;)V","(I)V","(Ljava/lang/String;ILandroid/os/Bundle;)V","(Ljava/lang/String;)V","(Ljava/lang/String;)V"};
uint32_t location_interface_metadata(JNIEnv *e){
 jclass listener=(*e)->FindClass(e,"android/location/LocationListener"),location=(*e)->FindClass(e,"android/location/Location");if(!listener||!location)return 0;
 jclass type=(*e)->FindClass(e,"java/lang/Class"),object=(*e)->FindClass(e,"java/lang/Object");jmethodID is_interface=(*e)->GetMethodID(e,type,"isInterface","()Z");uint32_t bits=0;
 if((*e)->CallBooleanMethod(e,listener,is_interface))bits|=1;
 if(!(*e)->GetSuperclass(e,listener)&&!(*e)->ExceptionCheck(e))bits|=2;
 unsigned methods=0;for(unsigned i=0;i<6;++i)methods+=(*e)->GetMethodID(e,listener,names[i],signatures[i])!=0;if(methods==6)bits|=4;
 if(!(*e)->AllocObject(e,listener)&&(*e)->ExceptionCheck(e))bits|=8;(*e)->ExceptionClear(e);
 if(!(*e)->NewObjectA(e,listener,0,0)&&(*e)->ExceptionCheck(e))bits|=16;(*e)->ExceptionClear(e);
 jclass parent=(*e)->GetSuperclass(e,location);if((*e)->IsSameObject(e,parent,object)&&!(*e)->CallBooleanMethod(e,location,is_interface))bits|=32;
 (*e)->DeleteLocalRef(e,parent);(*e)->DeleteLocalRef(e,object);(*e)->DeleteLocalRef(e,type);(*e)->DeleteLocalRef(e,location);(*e)->DeleteLocalRef(e,listener);return bits;
}
static void callback_v(JNIEnv *e,jobject p,jmethodID m,...){va_list a;va_start(a,m);(*e)->CallVoidMethodV(e,p,m,a);va_end(a);}
uint64_t location_callback(JNIEnv *e,jobject p,jint which,jobject first,jint value,jobject second,jint mode){
 if(which<0||which>=6)return 0;jclass c=(*e)->GetObjectClass(e,p);jmethodID m=(*e)->GetMethodID(e,c,names[which],signatures[which]);
 struct {uint64_t before;jvalue args[3];uint64_t after;}data={UINT64_C(0x1122334455667788),{{.j=0},{.j=0},{.j=0}},UINT64_C(0x8877665544332211)};
 if(which==2)data.args[0].i=value;else data.args[0].l=first;
 if(which==3){data.args[1].i=value;data.args[2].l=second;}
 uint64_t snapshot[3]={data.args[0].j,data.args[1].j,data.args[2].j};
 if(mode==2)(*e)->CallVoidMethodA(e,p,m,data.args);
 else if(which==2){if(mode==0)(*e)->CallVoidMethod(e,p,m,value);else callback_v(e,p,m,value);}
 else if(which==3){if(mode==0)(*e)->CallVoidMethod(e,p,m,first,value,second);else callback_v(e,p,m,first,value,second);}
 else{if(mode==0)(*e)->CallVoidMethod(e,p,m,first);else callback_v(e,p,m,first);}
 (*e)->DeleteLocalRef(e,c);return data.before==UINT64_C(0x1122334455667788)&&data.after==UINT64_C(0x8877665544332211)&&data.args[0].j==(jlong)snapshot[0]&&data.args[1].j==(jlong)snapshot[1]&&data.args[2].j==(jlong)snapshot[2]?UINT64_C(0xfedcba9876543210):0;
}

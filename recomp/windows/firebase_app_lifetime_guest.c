#include "firebase_app_guest.c"
extern void Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath(const char*);
extern void *Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0(void);
extern const char *Firebase_App_CSharp_FirebaseApp_NameInternal_get(void*);
extern void Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal(void*);
static void(*volatile config_pointer)(const char*)=Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath;
static void*(*volatile create_pointer)(void)=Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0;
static const char*(*volatile name_pointer)(void*)=Firebase_App_CSharp_FirebaseApp_NameInternal_get;
static void(*volatile release_pointer)(void*)=Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal;
__attribute__((visibility("default"))) void app_config(const char *path,int form){if(form)config_pointer(path);else Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath(path);}
__attribute__((visibility("default"))) uintptr_t app_create(int form){return(uintptr_t)(form?create_pointer():Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0());}
__attribute__((visibility("default"))) uint64_t app_name(void *app,int form){const char*p=form?name_pointer(app):Firebase_App_CSharp_FirebaseApp_NameInternal_get(app);uint64_t h=hash(p);free((void*)p);record[17]++;return h;}
__attribute__((visibility("default"))) void app_release(void *app,int form){if(form)release_pointer(app);else Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal(app);}

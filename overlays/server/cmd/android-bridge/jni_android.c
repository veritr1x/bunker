#include <jni.h>
#include <stdlib.h>
#include <string.h>
#include "_cgo_export.h"

static jstring result(JNIEnv *env, char *s) {
    const char *text = s ? s : "Native call failed";
    jsize length = (jsize)strlen(text);
    jbyteArray bytes = (*env)->NewByteArray(env, length);
    if (!bytes) { free(s); return NULL; }
    (*env)->SetByteArrayRegion(env, bytes, 0, length, (const jbyte *)text);
    jclass cls = (*env)->FindClass(env, "java/lang/String");
    jmethodID constructor = (*env)->GetMethodID(env, cls, "<init>", "([BLjava/lang/String;)V");
    jstring encoding = (*env)->NewStringUTF(env, "UTF-8");
    jstring value = (jstring)(*env)->NewObject(env, cls, constructor, bytes, encoding);
    (*env)->DeleteLocalRef(env, bytes);
    (*env)->DeleteLocalRef(env, cls);
    (*env)->DeleteLocalRef(env, encoding);
    free(s);
    return value;
}
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_texture(JNIEnv *env, jclass type, jstring bundle, jstring target, jint maxSide) {
    const char *b = (*env)->GetStringUTFChars(env, bundle, NULL);
    const char *t = (*env)->GetStringUTFChars(env, target, NULL);
    if (!b || !t) { if (b) (*env)->ReleaseStringUTFChars(env, bundle, b); if (t) (*env)->ReleaseStringUTFChars(env, target, t); return NULL; }
    char *error = LunarTexture((char *)b, (char *)t, (int)maxSide);
    (*env)->ReleaseStringUTFChars(env, bundle, b);
    (*env)->ReleaseStringUTFChars(env, target, t);
    return result(env, error);
}
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_start(JNIEnv *env, jclass type, jstring data, jstring assets) {
    const char *d = (*env)->GetStringUTFChars(env, data, NULL);
    const char *a = (*env)->GetStringUTFChars(env, assets, NULL);
    if (!d || !a) { if (d) (*env)->ReleaseStringUTFChars(env, data, d); if (a) (*env)->ReleaseStringUTFChars(env, assets, a); return NULL; }
    char *error = LunarStart((char *)d, (char *)a);
    (*env)->ReleaseStringUTFChars(env, data, d);
    (*env)->ReleaseStringUTFChars(env, assets, a);
    return result(env, error);
}
JNIEXPORT void JNICALL Java_org_veritr1x_bunker_NativeBridge_stop(JNIEnv *env, jclass type) { LunarStop(); }
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_status(JNIEnv *env, jclass type) { return result(env, LunarStatus()); }
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_checkDatabase(JNIEnv *env, jclass type, jstring root) {
    const char *r = (*env)->GetStringUTFChars(env, root, NULL);
    if (!r) return NULL;
    char *error = LunarCheck((char *)r);
    (*env)->ReleaseStringUTFChars(env, root, r);
    return result(env, error);
}
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_prepareBackup(JNIEnv *env, jclass type, jstring root) {
    const char *r = (*env)->GetStringUTFChars(env, root, NULL);
    if (!r) return NULL;
    char *error = LunarPrepareBackup((char *)r);
    (*env)->ReleaseStringUTFChars(env, root, r);
    return result(env, error);
}
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_edit(JNIEnv *env, jclass type, jstring data, jstring assets, jstring request) {
    const char *d = (*env)->GetStringUTFChars(env, data, NULL);
    const char *a = (*env)->GetStringUTFChars(env, assets, NULL);
    const char *r = (*env)->GetStringUTFChars(env, request, NULL);
    char *value = d && a && r ? LunarEdit((char *)d, (char *)a, (char *)r) : NULL;
    if (d) (*env)->ReleaseStringUTFChars(env, data, d);
    if (a) (*env)->ReleaseStringUTFChars(env, assets, a);
    if (r) (*env)->ReleaseStringUTFChars(env, request, r);
    return result(env, value);
}
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_importSaves(JNIEnv *env, jclass type, jstring data, jstring source) {
    const char *d = (*env)->GetStringUTFChars(env, data, NULL);
    const char *s = (*env)->GetStringUTFChars(env, source, NULL);
    char *error = d && s ? LunarImportSaves((char *)d, (char *)s) : NULL;
    if (d) (*env)->ReleaseStringUTFChars(env, data, d);
    if (s) (*env)->ReleaseStringUTFChars(env, source, s);
    return result(env, error);
}
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_importArchive(JNIEnv *env, jclass type, jint fd, jstring stage) {
    const char *d = (*env)->GetStringUTFChars(env, stage, NULL);
    char *error = d ? LunarImportArchiveFd((int)fd, (char *)d) : NULL;
    if (d) (*env)->ReleaseStringUTFChars(env, stage, d);
    return result(env, error);
}
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_setPortOffset(JNIEnv *env, jclass type, jint offset) { return result(env, LunarSetPortOffset((int)offset)); }
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_ports(JNIEnv *env, jclass type) { return result(env, LunarPorts()); }
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_selfTest(JNIEnv *env, jclass type) { return result(env, LunarSelfTest()); }
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_importProgress(JNIEnv *env, jclass type) { return result(env, LunarImportProgress()); }
JNIEXPORT void JNICALL Java_org_veritr1x_bunker_NativeBridge_cancelImport(JNIEnv *env, jclass type) { LunarCancelImport(); }
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_setLogDir(JNIEnv *env, jclass type, jstring dir) {
    const char *d = (*env)->GetStringUTFChars(env, dir, NULL);
    char *error = d ? LunarSetLogDir((char *)d) : NULL;
    if (d) (*env)->ReleaseStringUTFChars(env, dir, d);
    return result(env, error);
}
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_NativeBridge_exportLogs(JNIEnv *env, jclass type, jstring dir, jint fd, jstring info) {
    const char *d = (*env)->GetStringUTFChars(env, dir, NULL);
    const char *i = (*env)->GetStringUTFChars(env, info, NULL);
    char *error = d && i ? LunarExportLogsFd((char *)d, (int)fd, (char *)i) : NULL;
    if (d) (*env)->ReleaseStringUTFChars(env, dir, d);
    if (i) (*env)->ReleaseStringUTFChars(env, info, i);
    return result(env, error);
}

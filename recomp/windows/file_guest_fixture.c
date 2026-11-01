// Compiled with the actual Android AArch64 NDK headers. These callers validate
// that Windows imports consume the guest layouts/long/off_t ABI, not host ones.
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <jni.h>
// Legacy Unity was built against pre-23 Bionic FILE globals. Stride is checked
// independently against the NDK's bits/struct_file.h in prepare_files.py.
extern unsigned char __sF[];
uint64_t guest_legacy_stdio(void) {
    static const char message[] = "standard-stream-check\n";
    FILE *out = (FILE *)(__sF + 152);
    if (fwrite(message, 1, sizeof(message)-1, out) != sizeof(message)-1 || fflush(out)) return UINT64_MAX;
    return sizeof(message)-1;
}

static uint32_t crc_byte(uint32_t value, uint8_t byte) {
    value ^= byte;
    for (unsigned bit = 0; bit < 8; ++bit) value = (value >> 1) ^ (0xedb88320U & (0U - (value & 1)));
    return value;
}
uint64_t guest_fd_checksum(const char *path, uint64_t offset, uint64_t length, uint64_t file_size) {
    int fd = open(path, O_RDONLY);
    struct stat info;
    if (fd < 0 || fstat(fd, &info) || (uint64_t)info.st_size != file_size || lseek64(fd, offset, SEEK_SET) != (off64_t)offset) return UINT64_MAX;
    uint32_t crc = 0xffffffff;
    uint8_t buffer[256];
    while (length) {
        size_t count = length < sizeof(buffer) ? length : sizeof(buffer);
        ssize_t got = read(fd, buffer, count);
        if (got <= 0) return UINT64_MAX;
        for (ssize_t i = 0; i < got; ++i) crc = crc_byte(crc, buffer[i]);
        length -= got;
    }
    if (close(fd)) return UINT64_MAX;
    return ~crc;
}
uint64_t guest_stdio_checksum(const char *path, uint64_t offset, uint64_t length) {
    FILE *file = fopen(path, "rb");
    if (!file || fseek(file, (long)offset, SEEK_SET) || ftell(file) != (long)offset) return UINT64_MAX;
    uint32_t crc = 0xffffffff;
    uint8_t buffer[256];
    while (length) {
        size_t count = length < sizeof(buffer) ? length : sizeof(buffer);
        size_t got = fread(buffer, 1, count, file);
        if (!got) return UINT64_MAX;
        for (size_t i = 0; i < got; ++i) crc = crc_byte(crc, buffer[i]);
        length -= got;
    }
    if (fclose(file)) return UINT64_MAX;
    return ~crc;
}
uint64_t guest_mmap_checksum(const char *path, uint64_t offset, uint64_t length) {
    int fd = open(path, O_RDONLY);
    uint64_t page = offset & ~4095ULL, delta = offset - page;
    uint8_t *mapping = mmap(0, delta + length, PROT_READ, MAP_PRIVATE, fd, (off_t)page);
    if (fd < 0 || mapping == MAP_FAILED) return UINT64_MAX;
    uint32_t crc = 0xffffffff;
    for (uint64_t i = 0; i < length; ++i) crc = crc_byte(crc, mapping[delta + i]);
    if (munmap(mapping, delta + length) || close(fd)) return UINT64_MAX;
    return ~crc;
}
uint64_t guest_large_stdio(const char *path) {
    struct stat info;
    if (stat(path, &info) || info.st_size != 0x100000010LL) return UINT64_MAX;
    FILE *file = fopen(path, "rb");
    if (!file || fseeko(file, 0x100000005LL, SEEK_SET) || ftello(file) != 0x100000005LL) return UINT64_MAX;
    uint8_t byte = 0;
    if (fread(&byte, 1, 1, file) != 1 || fclose(file)) return UINT64_MAX;
    return byte;
}
uint64_t guest_missing_errno(const char *path) {
    if (open(path, O_RDONLY) >= 0) return UINT64_MAX;
    return errno;
}
uint64_t guest_madvise(void *address, uint64_t length, int advice) {
    _Static_assert(MADV_NORMAL == 0, "actual NDK normal advice");
    _Static_assert(MADV_DONTNEED == 4, "actual NDK discard advice");
    errno = 123;
    int result = madvise(address, length, advice);
    return ((uint64_t)(uint32_t)result << 32) | (uint32_t)errno;
}
uint64_t guest_context_checksum(JavaVM *vm, jobject activity, uint64_t offset, uint64_t length, uint64_t file_size, uint32_t target_sdk) {
    JNIEnv *env = 0;
    if ((*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_6) || !env) return UINT64_MAX;
    jclass activity_class = (*env)->GetObjectClass(env, activity);
    jmethodID info_method = (*env)->GetMethodID(env, activity_class, "getApplicationInfo", "()Landroid/content/pm/ApplicationInfo;");
    jobject info = (*env)->CallObjectMethodA(env, activity, info_method, 0);
    jclass info_class = (*env)->GetObjectClass(env, info);
    jfieldID sdk_field = (*env)->GetFieldID(env, info_class, "targetSdkVersion", "I");
    if ((uint32_t)(*env)->GetIntField(env, info, sdk_field) != target_sdk) return UINT64_MAX;
    jmethodID assets_method = (*env)->GetMethodID(env, activity_class, "getAssets", "()Landroid/content/res/AssetManager;");
    jobject assets = (*env)->CallObjectMethodA(env, activity, assets_method, 0);
    jclass assets_class = (*env)->FindClass(env, "android/content/res/AssetManager");
    if (!assets || !(*env)->IsInstanceOf(env, assets, assets_class)) return UINT64_MAX;
    jfieldID source_field = (*env)->GetFieldID(env, info_class, "sourceDir", "Ljava/lang/String;");
    jstring source = (*env)->GetObjectField(env, info, source_field);
    const char *path = (*env)->GetStringUTFChars(env, source, 0);
    if (!path) return UINT64_MAX;
    uint64_t result = guest_fd_checksum(path, offset, length, file_size);
    (*env)->ReleaseStringUTFChars(env, source, path);
    (*env)->DeleteLocalRef(env, source);
    (*env)->DeleteLocalRef(env, assets_class);
    (*env)->DeleteLocalRef(env, assets);
    (*env)->DeleteLocalRef(env, info_class);
    (*env)->DeleteLocalRef(env, info);
    (*env)->DeleteLocalRef(env, activity_class);
    return result;
}

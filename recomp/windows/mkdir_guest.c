#include <errno.h>
#include <stdint.h>
#include <sys/stat.h>

_Static_assert(sizeof(mode_t) == 4, "Android AArch64 mode_t width");
_Static_assert(sizeof(struct stat) == 128, "Android AArch64 stat wire width");

uint64_t guest_mkdir(const char *path, mode_t mode) {
  errno = 123;
  int value = mkdir(path, mode);
  return ((uint64_t)(uint32_t)errno << 32) | (uint32_t)value;
}

uint64_t guest_mkdir_stat(const char *path, struct stat *value) {
  errno = 123;
  int result = stat(path, value);
  return ((uint64_t)(uint32_t)errno << 32) | (uint32_t)result;
}

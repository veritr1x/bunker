#include <errno.h>
#include <stdint.h>
#include <sys/mman.h>
#include <unistd.h>

struct dup_observation {
  uint64_t before;
  int32_t errno_before, result, errno_after;
  uint32_t padding;
  uint64_t after;
};
int32_t dup_guest_direct(int32_t source, struct dup_observation *out) {
  out->errno_before = errno;
  int32_t result = dup(source);
  out->result = result;
  out->errno_after = errno;
  return result;
}
int32_t dup_guest_indirect(int32_t source, struct dup_observation *out) {
  int (*volatile call)(int) = dup;
  out->errno_before = errno;
  int32_t result = call(source);
  out->result = result;
  out->errno_after = errno;
  return result;
}
int64_t dup_guest_read(int32_t source, void *out, uint64_t size) { return read(source, out, size); }
int64_t dup_guest_write(int32_t source, const void *data, uint64_t size) { return write(source, data, size); }
int64_t dup_guest_seek(int32_t source, int64_t offset, int32_t whence) { return lseek64(source, offset, whence); }
int32_t dup_guest_close(int32_t source) { return close(source); }
void *dup_guest_map(int32_t source, uint64_t size, int64_t offset) { return mmap(0, size, PROT_READ, MAP_PRIVATE, source, offset); }
int32_t dup_guest_unmap(void *address, uint64_t size) { return munmap(address, size); }
uint64_t dup_guest_hash(const uint8_t *data, uint64_t size) {
  uint64_t result = 5381;
  for (uint64_t n = 0; n < size; ++n) result = result * 33 + data[n];
  return result;
}

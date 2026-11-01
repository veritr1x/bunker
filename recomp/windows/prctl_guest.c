#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <sys/prctl.h>

static uint64_t result(int value) {
  return ((uint64_t)(uint32_t)errno << 32) | (uint32_t)value;
}

uint64_t guest_prctl(int option, const char *name,
                     unsigned long third, unsigned long fourth,
                     unsigned long fifth) {
  errno = 123;
  return result(prctl(option, name, third, fourth, fifth));
}

uint64_t guest_prctl_two(const char *name) {
  errno = 123;
  return result(prctl(PR_SET_NAME, name));
}

uint64_t guest_pthread_name(const char *name) {
  errno = 123;
  return result(pthread_setname_np(pthread_self(), name));
}

extern uint64_t observe_native_name(void);
void *guest_name_worker(void *name) {
  if (guest_prctl(PR_SET_NAME, name, 0, 0, 0) != ((uint64_t)123 << 32))
    return (void *)1;
  return (void *)(uintptr_t)observe_native_name();
}

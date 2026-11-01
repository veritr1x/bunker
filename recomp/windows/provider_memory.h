#pragma once
#include "../whole/guest_memory.h"
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <malloc.h>
#include <vector>

namespace bunker::windows::provider_memory {
inline addr_t Address(const void *p) { return reinterpret_cast<addr_t>(p); }
template <typename T> T Read(const T *p) {
  T value; recomp::ReadGuestMemory(&value, Address(p), sizeof(value)); return value;
}
template <typename T> void Write(T *p, const T &value) {
  recomp::WriteGuestMemory(Address(p), &value, sizeof(value));
}
inline std::string String(const char *p, size_t maximum=SIZE_MAX) {
  return recomp::ReadGuestString(Address(p), maximum);
}
inline std::vector<unsigned char> Bytes(const void *p, size_t size) {
  std::vector<unsigned char> bytes(size);
  recomp::ReadGuestMemory(bytes.data(), Address(p), size); return bytes;
}
inline void *Copy(void *destination, const void *source, size_t size) {
  auto bytes=Bytes(source,size);
  recomp::WriteGuestMemory(Address(destination),bytes.data(),size);return destination;
}
inline void *Fill(void *destination, int value, size_t size) {
  if(!size)return destination;
  recomp::WithGuestMemoryWrite(Address(destination),size,[&]{std::memset(destination,value,size);});
  return destination;
}
inline size_t NativeSize(void *p) {
#ifdef _WIN32
  return ::_msize(p);
#else
  return ::malloc_usable_size(p);
#endif
}
// Newly allocated blocks are private until publication. Invalidate their full
// usable lifetime range before returning a pointer, including reused addresses.
inline void *Allocate(size_t size) {
  void *p=std::malloc(size?size:1);
  if(p)recomp::InvalidateGuestMemory(Address(p),NativeSize(p));return p;
}
inline void Free(void *p) {
  if(!p)return;size_t size=NativeSize(p);
  recomp::WithGuestMemoryWrite(Address(p),size,[&]{std::free(p);});
}
inline void *Reallocate(void *p,size_t size) {
  void *next=nullptr;
  recomp::WithGuestMemoryWrite(Address(p),NativeSize(p),[&]{next=std::realloc(p,size);});
  if(next)recomp::InvalidateGuestMemory(Address(next),NativeSize(next));return next;
}
inline const char *Locate(const char *original,const std::string &snapshot,const char *found) {
  return found?original+(found-snapshot.c_str()):nullptr;
}
}  // namespace bunker::windows::provider_memory

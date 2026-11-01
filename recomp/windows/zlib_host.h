#pragma once
#include <cstddef>
#include <functional>
#include <memory>
#include <string>
#include <vector>
#include "../whole/runtime.h"

namespace bunker::windows {
// Independently checked against the real Android NDK zlib.h. Do not substitute
// native Windows z_stream: Android uLong is 64 bits; Windows uLong is 32 bits.
struct AndroidZStream {
  addr_t next_in; uint32_t avail_in, pad_in; uint64_t total_in;
  addr_t next_out; uint32_t avail_out, pad_out; uint64_t total_out;
  addr_t message, state, zalloc, zfree, opaque;
  int32_t data_type; uint32_t pad_type;
  uint64_t adler, reserved;
};
static_assert(sizeof(AndroidZStream)==112 && offsetof(AndroidZStream,total_in)==16 &&
              offsetof(AndroidZStream,total_out)==40 && offsetof(AndroidZStream,adler)==96);

class Zlib {
 public:
  using Runner=std::function<uint64_t(addr_t,const std::vector<addr_t>&)>;
  explicit Zlib(Runner runner={},addr_t marker_base=0x7ffd00000000ULL);
  ~Zlib();
  Zlib(const Zlib&)=delete;
  Zlib&operator=(const Zlib&)=delete;
  addr_t Marker(const std::string&)const;
  void Install(recomp::Runtime&);
  int Init(AndroidZStream*,int window_bits,const char *version,int stream_size)noexcept;
  int Inflate(AndroidZStream*,int flush)noexcept;
  int End(AndroidZStream*)noexcept;
  const char *Version()const;
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows

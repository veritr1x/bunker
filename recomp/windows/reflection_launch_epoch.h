#pragma once
#include "jni_host.h"
#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>

namespace bunker::windows {
namespace reflection_launch_detail {
constexpr uint64_t NextBits(uint64_t current) { return current + uint64_t{1}; }
}

// ReflectionHelper.b's zero-initialized launch epoch, owned until Host teardown.
// Only endUnityLaunch is supplied. ReflectionHelper's proxy factory/accessor
// remain unsupported and must use this same owner if they are later ported.
// This does not initialize the independent 4096-entry reflection cache or mark
// ReflectionHelper's full <clinit> implemented, and does not affect JNIBridge.
class ReflectionLaunchEpoch {
 public:
  explicit ReflectionLaunchEpoch(jni::Host &host) : bits_(std::make_shared<std::atomic<uint64_t>>(0)) {
    host.BindStaticVoidMethod("com/unity3d/player/ReflectionHelper", "endUnityLaunch", "()V",
      [bits=bits_](addr_t,const jni::Host::MethodArguments&) {
        // The Java read/add/write is unsynchronized, not an atomic increment.
        // Separate relaxed operations avoid a C++ data race while preserving
        // its possible lost updates. Unsigned addition preserves Java wrapping.
        const auto current=bits->load(std::memory_order_relaxed);
        bits->store(reflection_launch_detail::NextBits(current),std::memory_order_relaxed);
      });
  }
  ReflectionLaunchEpoch(const ReflectionLaunchEpoch&)=delete;
  ReflectionLaunchEpoch& operator=(const ReflectionLaunchEpoch&)=delete;
  uint64_t Inspect() const { return bits_->load(std::memory_order_relaxed); }
  // Retained by ReflectionHelper proxy handlers; shares endUnityLaunch's owner.
  std::function<uint64_t()> Reader() const {
    return [bits=bits_] { return bits->load(std::memory_order_relaxed); };
  }
 private:
  std::shared_ptr<std::atomic<uint64_t>> bits_;
};
}

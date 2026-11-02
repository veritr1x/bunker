#pragma once
#include <cstdint>
#include <mutex>
#include "../whole/runtime.h"

namespace bunker::windows {
// Native Windows demand-commit ownership. Called by FileSystem with its mutex
// held; the VEH never calls FileSystem, C++ TLS, guest code or memory tracking.
class GrowdownMemory {
 public:
  struct Control;
  struct Region {addr_t reservation;uint64_t reservation_size;addr_t low,high,initial,committed;uint64_t generation;};
  enum class Collision {None,Committed,Reserved};
  // Normal/provider path only. Serializes fixed-no-replace classification and
  // native allocation against new growdown reservation publication, including
  // reservations owned by another FileSystem. Never acquired by the VEH.
  class AllocationGuard {public:AllocationGuard();private:std::unique_lock<std::mutex> lock_;};
  static constexpr uint64_t kAdditional=8*1024*1024,kGap=1024*1024;
  static constexpr uint32_t kActiveLimit=128,kLifetimeLimit=4096;
  static void Enable();
  // Returns an unpublished closed control, or nullptr with captured Win32 error
  // in native_error (preserved across normal-path mutex destruction).
  // Budget/profile violations throw before allocation. Failed native creation
  // does not consume a lifetime record. All published records are retained.
  static Control *Reserve(uint64_t initial_size,uint64_t generation,uint32_t &native_error);
  static Region Inspect(const Control *) noexcept;
  static void Publish(Control *) noexcept;
  static bool HasFaultReaders(const Control *) noexcept;
  // CAS closes only an open owner with zero fault readers. No wait or callback.
  static void Close(Control *);
  static void Reopen(Control *) noexcept;
  static bool ProtectClosed(Control *,int protection) noexcept;
  // On native failure remains closed/live; caller may reopen. On success its
  // immutable record is tombstoned and its real active budget is returned.
  static bool ReleaseClosed(Control *,uint32_t *native_error=nullptr) noexcept;
  static Collision FixedCollision(addr_t address,uint64_t size) noexcept;
};
}

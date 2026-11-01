// Typed bridges from the Android AAPCS64 scalar ABI to the host compiler's ABI.
// Scalar allocation follows AAPCS64 section 6.8.2 (C.1, C.5-C.6, C.9, C.13-C.17):
// https://github.com/ARM-software/abi-aa/blob/main/aapcs64/aapcs64.rst
//
// Use explicit guest-width types in signatures. Android long/size_t are 64-bit;
// Windows long is 32-bit, so APIs with differing data models require a typed
// adapter (for example int64_t -> _strtoi64), not direct binding to strtol.
// Pointers address shared guest/host data; guest function pointers need a
// callback trampoline and are deliberately rejected as typed scalar arguments.
#pragma once

#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>
#include <stdexcept>
#include <tuple>
#include <type_traits>
#include <utility>

#include "runtime.h"

namespace recomp {
namespace bridge_detail {

template <typename T>
inline constexpr bool kDataPointer = std::is_pointer_v<T> &&
    !std::is_function_v<std::remove_pointer_t<T>>;

template <typename T>
inline constexpr bool kScalar = [] {
  if constexpr (std::is_reference_v<T>) return false;
  else if constexpr (std::is_integral_v<T> || std::is_enum_v<T>) return sizeof(T) <= 8;
  else return kDataPointer<T> || std::is_same_v<T, float> || std::is_same_v<T, double>;
}();

template <typename Signature> struct Supported : std::false_type {};
template <typename R, typename... Args>
struct Supported<R(Args...)> : std::bool_constant<
    (std::is_void_v<R> || kScalar<R>) && (kScalar<Args> && ...)> {};
template <typename R, typename... Args>
struct Supported<R(Args...) noexcept> : Supported<R(Args...)> {};

inline uint64_t General(const State &state, unsigned index) {
  static constexpr Reg GPR::*registers[] = {&GPR::x0, &GPR::x1, &GPR::x2,
      &GPR::x3, &GPR::x4, &GPR::x5, &GPR::x6, &GPR::x7};
  return (state.gpr.*registers[index]).qword;
}

class Arguments {
 public:
  explicit Arguments(const State &state) : state_(state), stack_(state.gpr.sp.qword) {
    static_assert(sizeof(void *) == 8, "Scalar bridges require a 64-bit host");
  }

  template <typename T> T Read() {
    static_assert(kScalar<T>, "Unsupported guest scalar argument type");
    if constexpr (std::is_same_v<T, float> || std::is_same_v<T, double>) {
      T value;
      if (fp_ < 8) {
        std::memcpy(&value, &state_.simd.v[fp_++], sizeof(value));
      } else {
        ReadGuestMemory(&value, reinterpret_cast<addr_t>(StackSlot()), sizeof(value));
      }
      return value;
    } else {
      uint64_t bits;
      if (gp_ < 8) bits = General(state_, gp_++);
      else ReadGuestMemory(&bits, reinterpret_cast<addr_t>(StackSlot()), sizeof(bits));
      if constexpr (kDataPointer<T>) {
        return reinterpret_cast<T>(static_cast<uintptr_t>(bits));
      } else if constexpr (std::is_same_v<T, bool>) {
        return (bits & 0xffU) != 0;
      } else if constexpr (std::is_enum_v<T>) {
        using Underlying = std::underlying_type_t<T>;
        Underlying value;
        std::memcpy(&value, &bits, sizeof(value));
        return static_cast<T>(value);
      } else {
        T value;
        // AAPCS64 leaves upper bits unspecified: narrow the low bits in the
        // callee, preserving the bit representation of signed narrow values.
        std::memcpy(&value, &bits, sizeof(value));
        return value;
      }
    }
  }

 private:
  const void *StackSlot() {
    if (!stack_ || (stack_ & 7) || (!spilled_ && (stack_ & 15)) ||
        stack_ > std::numeric_limits<uint64_t>::max() - 8)
      throw std::invalid_argument("Invalid AAPCS64 scalar spill-stack address");
    spilled_ = true;
    auto address = stack_;
    stack_ += 8;
    return reinterpret_cast<const void *>(static_cast<uintptr_t>(address));
  }

  const State &state_;
  uint64_t stack_;
  unsigned gp_ = 0, fp_ = 0;
  bool spilled_ = false;
};

template <typename T> void Return(State &state, T value) {
  static_assert(kScalar<T>, "Unsupported guest scalar result type");
  if constexpr (std::is_same_v<T, float> || std::is_same_v<T, double>) {
    // Only the low result bits are specified by AAPCS64. Zero the remainder
    // deterministically, as scalar AArch64 register writes normally do.
    std::memset(&state.simd.v[0], 0, sizeof(state.simd.v[0]));
    std::memcpy(&state.simd.v[0], &value, sizeof(value));
  } else if constexpr (kDataPointer<T>) {
    state.gpr.x0.qword = reinterpret_cast<uintptr_t>(value);
  } else if constexpr (std::is_enum_v<T>) {
    Return(state, static_cast<std::underlying_type_t<T>>(value));
  } else if constexpr (sizeof(T) <= 4) {
    // Use the W0 representation for narrow integer results; upper X0 is zero.
    state.gpr.x0.qword = static_cast<uint32_t>(value);
  } else {
    std::memcpy(&state.gpr.x0.qword, &value, sizeof(value));
  }
}

template <typename Signature> struct Factory;
template <typename R, typename... Args>
struct Factory<R(Args...)> {
  template <typename Callable>
  static std::function<void(State &)> Make(Callable host) {
    static_assert(Supported<R(Args...)>::value,
        "Bridge supports only nonvariadic scalar signatures: fixed-width integers, enums, data pointers, float/double and void results");
    static_assert(std::is_invocable_r_v<R, Callable &, Args...>, "Host callable does not match the declared guest signature");
    if constexpr (std::is_pointer_v<Callable>) {
      if (!host) throw std::invalid_argument("Cannot bind a null host function");
    }
    return [host = std::move(host)](State &state) mutable {
      Arguments reader(state);
      // Braced initialization is left-to-right. A function-argument expansion
      // would have unspecified evaluation order and corrupt shared spill order.
      std::tuple<Args...> values{reader.Read<Args>()...};
      if constexpr (std::is_void_v<R>) std::apply(host, values);
      else {
        R result = static_cast<R>(std::apply(host, values));
        Return<R>(state, result);
      }
    };
  }
};
template <typename R, typename... Args>
struct Factory<R(Args...) noexcept> : Factory<R(Args...)> {};
}  // namespace bridge_detail

template <typename Signature>
inline constexpr bool kBridgeSupported = bridge_detail::Supported<Signature>::value;

template <typename Signature, typename Callable>
std::function<void(State &)> MakeBridge(Callable host) {
  static_assert(kBridgeSupported<Signature>, "Unsupported guest bridge signature (variadics, aggregates, references and callbacks need explicit adapters)");
  return bridge_detail::Factory<Signature>::Make(std::move(host));
}

template <typename R, typename... Args>
std::function<void(State &)> MakeBridge(R (*host)(Args...)) {
  if (!host) throw std::invalid_argument("Cannot bind a null host function");
  return MakeBridge<R(Args...)>(host);
}
}  // namespace recomp

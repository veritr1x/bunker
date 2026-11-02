#include "cooperative_poll.h"
#include <cerrno>
#include <cfenv>
#include <limits>
#include <stdexcept>
#include <thread>

namespace recomp {
struct PollBindingState {
  PollRequest *request;
  PollBinding::Handler handler;
  PollBinding::Admission admission;
  PollBindingState *previous;
  std::thread::id owner;
  uint64_t delivered = 0;
  bool delivering = false;
  void Complete(uint64_t epoch) {
    delivered = epoch;
    request->delivered_.store(epoch, std::memory_order_release);
  }
};
namespace { thread_local PollBindingState *binding; }
uint64_t PollRequest::Request() {
  auto current = requested_.load(std::memory_order_relaxed);
  do {
    if (current == std::numeric_limits<uint64_t>::max()) throw std::overflow_error("poll request epoch exhausted");
  } while (!requested_.compare_exchange_weak(current, current + 1, std::memory_order_release, std::memory_order_relaxed));
  return current + 1;
}
PollBinding::PollBinding(PollRequest &request, Handler handler, Admission admission) {
  if (!handler) throw std::invalid_argument("empty cooperative poll handler");
  auto state = std::make_unique<PollBindingState>(PollBindingState{&request, std::move(handler), std::move(admission), binding, std::this_thread::get_id()});
  if (request.bound_.exchange(true, std::memory_order_acq_rel)) throw std::invalid_argument("poll request already bound to a worker");
  state->delivered = request.delivered_.load(std::memory_order_acquire);
  state_ = std::move(state);
  binding = state_.get();
}
PollBinding::~PollBinding() {
  if (binding != state_.get() || state_->owner != std::this_thread::get_id()) std::terminate();
  binding = state_->previous;
  state_->request->bound_.store(false, std::memory_order_release);
}
}  // namespace recomp
extern "C" uint32_t __bunker_guest_poll_requested() {
  const auto *binding = recomp::binding;
  return binding && !binding->delivering && binding->request->Sequence() != binding->delivered;
}
extern "C" void __bunker_guest_poll_slow(State *state, uint64_t trace, uint64_t ordinal, addr_t entry_pc) {
  auto *binding = recomp::binding;
  if (!binding || binding->delivering || !state) throw std::invalid_argument("invalid cooperative poll boundary");
  const auto epoch = binding->request->Sequence();
  if (epoch == binding->delivered) return;
  const int saved_errno = errno;
  struct Scope {
    recomp::PollBindingState &binding;
    int error;
    fenv_t environment;
    State &state;
    bool admitted = false;
    Scope(recomp::PollBindingState &b, State &s, int saved_error) : binding(b), error(saved_error), state(s) {
      std::fegetenv(&environment); binding.delivering = true;
    }
    ~Scope() {
      binding.delivering = false;
      std::fesetenv(&environment);
      if (admitted) {
        const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
        std::fesetround(modes[state.fpcr.rmode]);
      }
      errno = error;
    }
  } scope(*binding, *state, saved_errno);
  const auto frames = recomp::CurrentExecutionFrames(*state);
  // Entry State.pc can still name the caller. Expose the authoritative PC to
  // admission without modifying State until the decision actually admits it.
  const addr_t interrupted_pc = ordinal ? state->gpr.pc.qword : entry_pc;
  const recomp::PollSite site{trace, ordinal, epoch};
  if (binding->admission) {
    const std::vector<const State *> read_only_frames(frames.begin(), frames.end());
    if (!binding->admission({*state, site, interrupted_pc, read_only_frames})) return;
  }
  scope.admitted = true;
  if (!ordinal) state->gpr.pc.qword = entry_pc;
  // Explicit delivery invalidates exclusive reservations. Fast predicates do
  // not. No memory/provider lock is held while invoking the user handler.
  __remill_aarch64_clear_exclusive(*state);
  binding->handler(*state, site, frames);
  if (state->gpr.pc.qword != interrupted_pc)
    throw std::invalid_argument("cooperative poll cannot redirect the translated continuation PC");
  // A later request cannot be consumed by this delivery. Throwing handlers
  // leave this request pending, and all scope state is restored during unwind.
  binding->Complete(epoch);
}

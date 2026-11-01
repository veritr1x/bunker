#include "runtime.h"
#include "../windows/libc.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cstdio>
#include <cstring>
#include <set>
#include <stdexcept>

static bunker::windows::LibC *libc;
static void *resolve(const char *name) { return reinterpret_cast<void *>(libc->Marker(name)); }
int main() {
  try {
    recomp::Runtime runtime;
    std::set<addr_t> translated;
    for (auto &trace : kTraces) translated.insert(trace.address);
    alignas(16) std::array<unsigned char, 65536> stack{};
    auto run = [&](addr_t entry, const std::vector<addr_t> &arguments) {
      if (!translated.count(entry)) throw std::invalid_argument("callback is not a registered translated entry");
      State state{}; state.gpr.sp.qword = reinterpret_cast<addr_t>(stack.data() + stack.size());
      state.gpr.x30.qword = 0xfeedffff;
      if (!arguments.empty()) state.gpr.x0.qword = arguments.at(0);
      runtime.Run(state, entry);
      if (state.gpr.pc.qword != 0xfeedffff || state.gpr.sp.qword != reinterpret_cast<addr_t>(stack.data() + stack.size()))
        throw std::runtime_error("callback corrupted PC/SP");
      return state.gpr.x0.qword;
    };
    bunker::windows::LibC host(run); libc = &host; host.Install(runtime);
    runtime.AddTraces(kTraces, std::size(kTraces));
    elf_image image{};
    if (elf_load(CALLBACK_LIBRARY, 0x54000000, resolve, &image)) return 2;
    uint64_t output = 0;
    run(reinterpret_cast<addr_t>(elf_symbol(&image,"callback_register")), {reinterpret_cast<addr_t>(&output)});
    run(reinterpret_cast<addr_t>(elf_symbol(&image,"callback_register_tail")), {reinterpret_cast<addr_t>(&output)});
    auto plain = reinterpret_cast<uint64_t *>(elf_symbol(&image,"callback_plain_count"));
    // Protected data remains in dynsym for the test; the destructors themselves
    // have no symbol/FDE and cannot become baseline roots through this symbol.
    if (!plain) throw std::runtime_error("plain atexit counter missing");
    host.Finalize(0xdeadbeef);
    if (output || *plain) throw std::runtime_error("unrelated DSO invoked callbacks");
    host.Finalize(CALLBACK_DSO);
    // Tail registration runs first: 13, then (13 << 4) + 7. Reversing the
    // callbacks would yield 20, so additive effects cannot hide wrong order.
    if (output != 215 || *plain) throw std::runtime_error("DSO destructor effects/order differ");
    host.Finalize();
    if (output != 215 || *plain != 11) throw std::runtime_error("plain atexit callback effects differ");
    host.Finalize();
    if (output != 215 || *plain != 11) throw std::runtime_error("destructors repeated");
    std::puts("Recovered symbol/FDE-free direct+tail destructors and plain atexit: effects/order/DSO/once-only/PC/SP pass.");
    return 0;
  } catch (const std::exception &error) { std::fprintf(stderr,"callback teardown: %s\n",error.what()); return 3; }
}

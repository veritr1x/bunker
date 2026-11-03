#include <atomic>
#include <condition_variable>
#include <cstring>
#include <functional>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>
#include "runtime.h"

namespace {
unsigned checks;
void check(bool value, const char *message) {
  ++checks;
  if (!value) throw std::runtime_error(message);
}
thread_local const std::function<void(State &)> *body;
Memory *entry(State &state, addr_t, Memory *memory) {
  (*body)(state);
  state.gpr.pc.qword = state.gpr.x30.qword;
  return memory;
}
Memory *finish(State &state, addr_t, Memory *memory) {
  state.gpr.x0.qword = __remill_aarch64_store_exclusive(state, state.gpr.x1.qword, 99, state.gpr.x2.qword, 0);
  state.gpr.pc.qword = state.gpr.x30.qword;
  return memory;
}
Memory *finish_pair(State &state, addr_t, Memory *memory) {
  state.gpr.x0.qword = __remill_aarch64_store_exclusive_pair(state, state.gpr.x1.qword, 99, 100, state.gpr.x2.qword, 0);
  state.gpr.pc.qword = state.gpr.x30.qword;
  return memory;
}
recomp::Runtime make_runtime() {
  recomp::Runtime runtime;
  const recomp::Trace traces[] = {{0x1000, entry}, {0x2000, finish}, {0x2010, finish_pair}};
  runtime.AddTraces(traces, 3);
  runtime.AddImport(0x3000, [](State &) {});
  return runtime;
}
void run(recomp::Runtime &runtime, const std::function<void(State &)> &callback) {
  const auto previous = body;
  body = &callback;
  State state{};
  state.gpr.x30.qword = 0xfeedffff;
  runtime.Run(state, 0x1000);
  body = previous;
}
struct Gate {
  std::mutex mutex;
  std::condition_variable condition;
  unsigned phase = 0;
  void reach(unsigned value) {
    std::lock_guard<std::mutex> lock(mutex);
    phase = value;
    condition.notify_all();
  }
  void wait(unsigned value) {
    std::unique_lock<std::mutex> lock(mutex);
    condition.wait(lock, [&] { return phase >= value; });
  }
};
alignas(64) uint8_t bytes[256];
addr_t address(unsigned offset = 0) { return reinterpret_cast<addr_t>(bytes + offset); }
uint64_t read_value(unsigned size, unsigned offset = 0) {
  uint64_t value = 0;
  recomp::ReadGuestMemory(&value, address(offset), size);
  return value;
}
void write_value(uint64_t value, unsigned size, unsigned offset = 0) {
  recomp::WriteGuestMemory(address(offset), &value, size);
}
}

int main(int argc, char **argv) {
  auto runtime = make_runtime();
  if (argc > 1 && (!std::strcmp(argv[1], "unresolved-zero") || !std::strcmp(argv[1], "unresolved-nonzero"))) {
    const bool zero = !std::strcmp(argv[1], "unresolved-zero");
    run(runtime, [&](State &state) {
      state.gpr.pc.qword = zero ? UINT64_C(0x1234567876543210) : UINT64_C(0x56789abc9abcdef0);
      state.gpr.x30.qword = zero ? UINT64_C(0x2345678987654321) : UINT64_C(0x6789abcdaabcdef1);
      state.gpr.sp.qword = zero ? UINT64_C(0x3456789a98765432) : UINT64_C(0x789abcdebbcdef12);
      if (zero) __remill_jump(state, 0, nullptr);
      else __remill_function_call(state, UINT64_C(0x456789ab89abcdef), nullptr);
    });
    return 2;
  }
  if (argc > 1) {
    run(runtime, [&](State &state) {
      if (!std::strncmp(argv[1], "pair-", 5)) {
        uint64_t first=0,second=0;
        __remill_aarch64_load_exclusive_pair(state,address(!std::strcmp(argv[1],"pair-align")?8:0),
          !std::strcmp(argv[1],"pair-width")?3:8,0,!std::strcmp(argv[1],"pair-null")?nullptr:&first,&second);
      } else __remill_aarch64_load_exclusive(state, address(argv[1][0] == 'a' ? 1 : 0), argv[1][0] == 'a' ? 8 : 16, 0);
    });
    return 2;
  }
  try {
    for (unsigned size : {1u, 2u, 4u, 8u}) {
      write_value(7, size);
      run(runtime, [&](State &state) {
        check(__remill_aarch64_store_exclusive(state, address(), 8, size, 0) == 1, "store without reservation");
        check(__remill_aarch64_load_exclusive(state, address(), size, 0) == 7, "exclusive load value");
        check(__remill_aarch64_store_exclusive(state, address(), 9, size, 0) == 0, "exclusive store success");
        check(read_value(size) == 9, "exclusive store data");
        check(__remill_aarch64_store_exclusive(state, address(), 10, size, 1) == 1, "store consumes reservation");
        __remill_aarch64_load_exclusive(state, address(), size, 1);
        __remill_aarch64_clear_exclusive(state);
        check(__remill_aarch64_store_exclusive(state, address(), 10, size, 1) == 1, "clear exclusive");
        __remill_aarch64_load_exclusive(state, address(), size, 1);
        write_value(100, size);
        write_value(9, size);
        check(__remill_aarch64_store_exclusive(state, address(), 10, size, 1) == 1, "tracked ABA invalidates");
        __remill_aarch64_load_exclusive(state, address(), size, 0);
        write_value(5, 1, 32);
        check(__remill_aarch64_store_exclusive(state, address(), 10, size, 0) == 1, "same granule invalidates");
        __remill_aarch64_load_exclusive(state, address(), size, 0);
        write_value(5, 1, 64);
        check(__remill_aarch64_store_exclusive(state, address(), 10, size, 0) == 0, "other granule survives");
        __remill_aarch64_load_exclusive(state, address(), size, 0);
        __remill_aarch64_load_exclusive(state, address(64), size, 0);
        check(__remill_aarch64_store_exclusive(state, address(), 10, size, 0) == 1, "new load replaces reservation");
        check(__remill_aarch64_store_exclusive(state, address(64), 10, size, 0) == 1, "failed store consumes reservation");
        __remill_aarch64_load_exclusive(state, address(), size, 0);
        state.gpr.x1.qword = address(); state.gpr.x2.qword = size;
        runtime.Dispatch(state, 0x2000, nullptr);
        check(state.gpr.x0.qword == 0 && read_value(size) == 99, "reservation crosses trace dispatch");
      });
    }
    run(runtime, [&](State &state) {
      write_value(7, 8);
      __remill_aarch64_load_exclusive(state, address(), 8, 0);
      runtime.Dispatch(state, 0x3000, nullptr);
      check(__remill_aarch64_store_exclusive(state, address(), 8, 8, 0) == 1, "import invalidates reservation");
      __remill_aarch64_load_exclusive(state, address(), 8, 0);
      auto inner = make_runtime();
      run(inner, [](State &) {});
      check(__remill_aarch64_store_exclusive(state, address(), 8, 8, 0) == 1, "nested entry invalidates parent reservation");
      __remill_aarch64_load_exclusive(state, address(), 8, 0);
      check(__remill_aarch64_store_exclusive(state, address(), 8, 8, 0) == 0, "parent context restored after nested entry");
    });
    // Every existing runtime write family participates, not only integer STR.
    std::vector<std::function<void()>> writers = {
      [] { __remill_write_memory_8(nullptr, address(), 7); },
      [] { __remill_write_memory_16(nullptr, address(), 7); },
      [] { __remill_write_memory_32(nullptr, address(), 7); },
      [] { __remill_write_memory_64(nullptr, address(), 7); },
      [] { __remill_write_memory_f32(nullptr, address(), 0.0f); },
      [] { __remill_write_memory_f64(nullptr, address(), 0.0); },
      [] { float80_t value{}; __remill_write_memory_f80(nullptr, address(), value); },
      [] { float128_t value{}; __remill_write_memory_f128(nullptr, address(), value); },
      [] { uint64_t expected=7; __remill_compare_exchange_memory_64(nullptr,address(),expected,7); },
      [] { uint128_t expected=7,desired=7; __remill_compare_exchange_memory_128(nullptr,address(),expected,desired); },
      [] { uint64_t add=1,sub=1; __remill_fetch_and_add_64(nullptr,address(),add); __remill_fetch_and_sub_64(nullptr,address(),sub); },
      [] { recomp::WithGuestMemoryWrite(address(),8,[] { uint64_t value=7;std::memcpy(bytes,&value,8); }); },
      [] { try { recomp::WithGuestMemoryWrite(address(),8,[] { throw std::runtime_error("partial write"); }); } catch(const std::runtime_error &) {} }
    };
    for (const auto &write : writers) {
      std::memset(bytes, 0, sizeof(bytes));
      write_value(7,8);
      run(runtime,[&](State &state) {
        __remill_aarch64_load_exclusive(state,address(),8,0);
        write();
        check(__remill_aarch64_store_exclusive(state,address(),8,8,0)==1,"runtime write invalidates reservation");
      });
    }
    write_value(7,8);
    run(runtime,[&](State &state) {
      __remill_aarch64_load_exclusive(state,address(),8,0);
      uint64_t expected=99;
      __remill_compare_exchange_memory_64(nullptr,address(),expected,8);
      check(expected==7,"failed CAS returns observed value");
      check(__remill_aarch64_store_exclusive(state,address(),8,8,0)==0,"failed CAS made no tracked write");
    });
    run(runtime,[&](State &state) {
      __remill_aarch64_load_exclusive(state,address(),8,0);
      uint64_t snapshot=0;
      recomp::ReadGuestMemory(&snapshot,address(),8);
      check(snapshot==8,"tracked host snapshot value");
      check(__remill_aarch64_store_exclusive(state,address(),9,8,0)==0,"snapshot does not invalidate reservation");
      __remill_aarch64_load_exclusive(state,address(),8,0);
      recomp::InvalidateGuestMemory(address(),sizeof(bytes));
      check(__remill_aarch64_store_exclusive(state,address(),10,8,0)==1,"allocation lifetime invalidates reservation");
      write_value(7,8,64);
      __remill_aarch64_load_exclusive(state,address(64),8,0);
      uint8_t crossing[8];
      recomp::ReadGuestMemory(crossing,address(60),sizeof(crossing));
      recomp::WriteGuestMemory(address(60),crossing,sizeof(crossing));
      check(__remill_aarch64_store_exclusive(state,address(64),10,8,0)==1,"write crossing granules invalidates overlapping reservation");
    });
    // Concurrent tracked ABA across two Runtime objects must defeat CAS even
    // though the final bytes equal the value read by the first thread.
    write_value(7,8);
    Gate gate;
    uint32_t status=0;
    std::thread first([&] {
      auto local=make_runtime();
      run(local,[&](State &state) {
        __remill_aarch64_load_exclusive(state,address(),8,0);
        gate.reach(1);gate.wait(2);
        status=__remill_aarch64_store_exclusive(state,address(),8,8,0);
      });
    });
    std::thread second([&] {
      gate.wait(1);
      auto local=make_runtime();
      run(local,[](State &) { __remill_write_memory_64(nullptr,address(),9);__remill_write_memory_64(nullptr,address(),7); });
      gate.reach(2);
    });
    first.join();second.join();
    check(status==1&&read_value(8)==7,"cross-runtime tracked ABA");
    write_value(0,8);
    std::vector<std::thread> workers;
    for(unsigned t=0;t<4;++t)workers.emplace_back([&] {
      auto local=make_runtime();
      run(local,[](State &state) {
        for(unsigned i=0;i<2000;++i)for(;;) {
          auto value=__remill_aarch64_load_exclusive(state,address(),8,1);
          if(!__remill_aarch64_store_exclusive(state,address(),value+1,8,1))break;
        }
      });
    });
    for(auto &worker:workers)worker.join();
    check(read_value(8)==8000,"four-thread exclusive increment");
    for (unsigned element : {4u,8u}) {
      const uint64_t first=element==4?0x89abcdef:UINT64_C(0x0123456789abcdef);
      const uint64_t second=element==4?0x76543210:UINT64_C(0xfedcba9876543210);
      uint64_t original[2]={element==4?first|(second<<32):first,element==4?0:second};
      recomp::WriteGuestMemory(address(),original,sizeof(original));
      run(runtime,[&](State &state) {
        uint64_t a=0,b=0;
        check(__remill_aarch64_store_exclusive_pair(state,address(),1,2,element,0)==1,"pair store without reservation");
        __remill_aarch64_load_exclusive_pair(state,address(),element,1,&a,&b);
        check(a==first&&b==second,"pair out-parameter values and zero extension");
        check(__remill_aarch64_store_exclusive_pair(state,address(),UINT64_C(0xfedcba9876543210),UINT64_C(0x0123456789abcdef),element,1)==0,"pair store success");
        uint64_t observed[2];recomp::ReadGuestMemory(observed,address(),sizeof(observed));
        check(element==4?(observed[0]==UINT64_C(0x89abcdef76543210)):
                        (observed[0]==UINT64_C(0xfedcba9876543210)&&observed[1]==UINT64_C(0x0123456789abcdef)),"pair store truncation/order");
        check(__remill_aarch64_store_exclusive_pair(state,address(),1,2,element,0)==1,"pair store consumes reservation");
        __remill_aarch64_load_exclusive_pair(state,address(),element,0,&a,&b);
        __remill_aarch64_clear_exclusive(state);
        check(__remill_aarch64_store_exclusive_pair(state,address(),1,2,element,0)==1,"pair CLREX");
        __remill_aarch64_load_exclusive_pair(state,address(),element,0,&a,&b);
        check(__remill_aarch64_store_exclusive(state,address(),1,8,0)==1,"pair-to-single shape mismatch");
        __remill_aarch64_load_exclusive(state,address(),8,0);
        check(__remill_aarch64_store_exclusive_pair(state,address(),1,2,element,0)==1,"single-to-pair shape mismatch");
        __remill_aarch64_load_exclusive_pair(state,address(),element,0,&a,&b);
        recomp::WriteGuestMemory(address(),observed,element*2);
        check(__remill_aarch64_store_exclusive_pair(state,address(),1,2,element,0)==1,"pair same-value tracked ABA");
        __remill_aarch64_load_exclusive_pair(state,address(),element,0,&a,&b);
        state.gpr.x1.qword=address();state.gpr.x2.qword=element;
        runtime.Dispatch(state,0x2010,nullptr);
        check(state.gpr.x0.qword==0,"pair reservation crosses trace dispatch");
      });
      uint64_t zero[2]={0,0};recomp::WriteGuestMemory(address(),zero,sizeof(zero));
      std::vector<std::thread> pair_workers;
      for(unsigned t=0;t<4;++t)pair_workers.emplace_back([&,element] {
        auto local=make_runtime();
        run(local,[element](State &state) {
          for(unsigned i=0;i<1000;++i)for(;;) {
            uint64_t a,b;__remill_aarch64_load_exclusive_pair(state,address(),element,1,&a,&b);
            if(!__remill_aarch64_store_exclusive_pair(state,address(),a+1,b+1,element,1))break;
          }
        });
      });
      for(auto &worker:pair_workers)worker.join();
      uint64_t observed[2];recomp::ReadGuestMemory(observed,address(),sizeof(observed));
      check(element==4?(observed[0]==(UINT64_C(4000)|(UINT64_C(4000)<<32))):(observed[0]==4000&&observed[1]==4000),"four-thread pair exclusive increment");
    }
    std::atomic<bool> mixed{false};
    std::memset(bytes,0,sizeof(bytes));
    std::thread writer([&] { for(unsigned i=0;i<1000;++i)recomp::WithGuestMemoryWrite(address(),sizeof(bytes),[&] {std::memset(bytes,i&255,sizeof(bytes));}); });
    std::thread reader([&] { for(unsigned i=0;i<1000;++i) {uint8_t copy[sizeof(bytes)];recomp::ReadGuestMemory(copy,address(),sizeof(copy));for(auto value:copy)if(value!=copy[0])mixed=true;} });
    writer.join();reader.join();
    check(!mixed,"tracked snapshot is coherent");
    bool threw=false;
    try { recomp::WriteGuestMemory(~addr_t(0),bytes,2); } catch(const std::invalid_argument &) {threw=true;}
    check(threw,"write range overflow rejected");
    threw=false;
    try { recomp::ReadGuestMemory(bytes,~addr_t(0),2); } catch(const std::invalid_argument &) {threw=true;}
    check(threw,"read range overflow rejected");
    std::cout<<checks<<" exclusive runtime checks passed; tracked writes only\n";
  } catch(const std::exception &error) {
    std::cerr<<error.what()<<'\n';return 1;
  }
}

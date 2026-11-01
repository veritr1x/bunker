#pragma once
// Cross-thread provider tests: reserve in a live guest Runtime/State, allow a
// different native thread to perform an actual provider operation, then STXR.
#include <condition_variable>
#include <exception>
#include <functional>
#include <mutex>
#include <thread>
#include "../whole/runtime.h"
namespace bunker::test {
struct ReservationResult {uint64_t loaded;uint32_t status;};
inline thread_local const std::function<void(State&)> *reservation_body;
inline Memory *ReservationTrace(State &s,addr_t,Memory *memory){(*reservation_body)(s);s.gpr.pc.qword=s.gpr.x30.qword;return memory;}
inline ReservationResult ReserveAcrossOperation(addr_t address,size_t size,const std::function<void()> &operation){
  std::mutex mutex;std::condition_variable condition;unsigned phase=0;std::exception_ptr failure;
  auto reach=[&](unsigned p){std::lock_guard lock(mutex);phase=p;condition.notify_all();};
  auto wait=[&](unsigned p){std::unique_lock lock(mutex);condition.wait(lock,[&]{return phase>=p;});};
  std::thread writer([&]{wait(1);try{operation();}catch(...){failure=std::current_exception();}reach(2);});
  ReservationResult result{};
  std::function<void(State&)> callback=[&](State &s){result.loaded=__remill_aarch64_load_exclusive(s,address,size,1);reach(1);wait(2);result.status=__remill_aarch64_store_exclusive(s,address,result.loaded,size,1);};
  auto previous=reservation_body;reservation_body=&callback;
  recomp::Runtime runtime;recomp::Trace trace{0x7ffe00001000ULL,ReservationTrace};runtime.AddTraces(&trace,1);
  State state{};state.gpr.x30.qword=0xfeedffff;runtime.Run(state,trace.address);reservation_body=previous;writer.join();if(failure)std::rethrow_exception(failure);return result;
}
} // namespace bunker::test

#pragma once
// Test-owned real condition-variable wake channel. No production signal policy.
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <stdexcept>
namespace wait_test {
class Channel {
 public:
  uint64_t Generation(){std::lock_guard lock(mutex_);return generation_;}
  void Notify(){std::lock_guard lock(mutex_);++generation_;condition_.notify_all();}
  void Wait(uint64_t expected,uint64_t relative){
    std::unique_lock lock(mutex_);
    if(relative)condition_.wait_for(lock,std::chrono::nanoseconds(relative),[&]{return generation_!=expected;});
    else condition_.wait(lock,[&]{return generation_!=expected;});
  }
 private:
  std::mutex mutex_;std::condition_variable condition_;uint64_t generation_=0;
};
}

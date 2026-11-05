#pragma once
#include "../whole/runtime.h"
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <stdexcept>

namespace bunker::windows {
using DescriptorImportInterceptor=std::function<void(const char*,State&,const std::function<void()>&)>;
inline State *&ActiveDescriptorState(){static thread_local State *value=nullptr;return value;}
struct DescriptorImportScope {
  State *previous;
  explicit DescriptorImportScope(State *value):previous(ActiveDescriptorState()){ActiveDescriptorState()=value;}
  ~DescriptorImportScope(){ActiveDescriptorState()=previous;}
};
// One guest namespace. Native CRT fds and native SOCKET values never escape it.
struct GuestDescriptor {
  enum class Kind { File,Socket,PipeRead,PipeWrite };
  const Kind kind;
  bool close_on_exec;
  explicit GuestDescriptor(Kind k,bool clo=false):kind(k),close_on_exec(clo){}
  virtual ~GuestDescriptor()=default;
  virtual int64_t Read(addr_t,uint64_t,int &error){error=9;return -1;}
  virtual int64_t Write(addr_t,uint64_t,int &error){error=9;return -1;}
  virtual std::shared_ptr<GuestDescriptor> Duplicate(int &error){error=95;return {};}
  virtual int StatusFlags()const{return 2;}
  virtual int SetStatusFlags(int,int &error){error=95;return -1;}
  virtual int Ioctl(uint64_t,addr_t,int &error){error=25;return -1;}
  virtual uint64_t Identity()const{return reinterpret_cast<uint64_t>(this);}
};
class GuestDescriptors {
 public:
  std::recursive_mutex mutex;
  std::map<int,std::shared_ptr<GuestDescriptor>> entries;
  std::shared_ptr<GuestDescriptor> Lookup(int descriptor){
    std::lock_guard lock(mutex);const auto i=entries.find(descriptor);return i==entries.end()?nullptr:i->second;
  }
  int Allocate(std::shared_ptr<GuestDescriptor> value,int minimum=3){
    std::lock_guard lock(mutex);int64_t candidate=minimum;
    for(auto i=entries.lower_bound(minimum);i!=entries.end()&&i->first==candidate;++i)++candidate;
    if(candidate>INT32_MAX)return -1;
    if(!entries.emplace(static_cast<int>(candidate),std::move(value)).second)throw std::logic_error("guest descriptor publication collision");
    return static_cast<int>(candidate);
  }
  std::shared_ptr<GuestDescriptor> Remove(int descriptor){
    std::lock_guard lock(mutex);auto i=entries.find(descriptor);if(i==entries.end())return {};
    auto value=std::move(i->second);entries.erase(i);return value;
  }
};
}  // namespace bunker::windows

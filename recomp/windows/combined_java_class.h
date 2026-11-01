#pragma once
#include "jni_host.h"
#include <memory>
#include <mutex>
#include <stdexcept>
namespace bunker::windows {
// Isolated profile addition; uses the existing checked runtime class operation.
// Globals survive until Host teardown: no deletion race or destructor JNI calls.
inline void DefineCombinedRuntimeClass(jni::Host&host){
 if(!host.PendingException().empty())throw std::invalid_argument("runtime-class adapter cannot hide a pending Java exception");
 struct Cache{std::mutex mutex;std::vector<addr_t> classes;};
 auto cache=std::make_shared<Cache>();
 host.DefineObjectMethod("java/lang/Object","getClass","()Ljava/lang/Class;",[&host,cache](addr_t object){
  State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=object;host.InvokeEnv(31,s);
  auto actual=s.gpr.x0.qword;if(!actual)return addr_t(0);
  struct Local{jni::Host&host;addr_t value;~Local(){host.DeleteLocalReference(value);}}local{host,actual};
  std::lock_guard<std::mutex>lock(cache->mutex);
  for(auto global:cache->classes){
   State same{};same.gpr.x0.qword=host.EnvAddress();same.gpr.x1.qword=actual;same.gpr.x2.qword=global;host.InvokeEnv(24,same);
   if(same.gpr.x0.dword)return global;
  }
  auto global=host.NewGlobalReference(actual);if(!global)return addr_t(0);
  try{cache->classes.push_back(global);}catch(...){host.DeleteGlobalReference(global);throw;}
  return global;
 });
}
}

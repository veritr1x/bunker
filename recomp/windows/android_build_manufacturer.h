#pragma once
#include "jni_host.h"
#include <stdexcept>

namespace bunker::windows {
// Setup-only compatibility profile. The caller explicitly declares Android
// product properties absent; this is not a query of Windows/device identity.
// AOSP Android13 Build.MANUFACTURER and MODEL read ro.product.manufacturer
// and ro.product.model. Both absent-property defaults are Build.UNKNOWN
// ("unknown"). Only these reached static fields are represented.
// Host outlives setup. No active guest/JNI readers may race installation.
class AndroidBuildManufacturerProfile {
 public:
  enum class PropertyPolicy { AbsentAndroidProductProperties };
  explicit AndroidBuildManufacturerProfile(jni::Host &host,PropertyPolicy policy) {
    if(policy!=PropertyPolicy::AbsentAndroidProductProperties)
      throw std::invalid_argument("unsupported Android product-property policy");
    if(!host.PendingException().empty())
      throw std::invalid_argument("manufacturer profile requires exception-free setup");
    host.DefineClass("android/os/Build",{},"java/lang/Object",true);
    host.DefineField("android/os/Build","MANUFACTURER","Ljava/lang/String;",true);
    host.DefineField("android/os/Build","MODEL","Ljava/lang/String;",true);
    struct Locals {
      jni::Host &host;addr_t owner=0,value=0;
      ~Locals(){if(value)host.DeleteLocalReference(value);if(owner)host.DeleteLocalReference(owner);}
    } locals{host};
    auto env=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){
      State state{};state.gpr.x0.qword=host.EnvAddress();state.gpr.x1.qword=a;
      state.gpr.x2.qword=b;state.gpr.x3.qword=c;host.InvokeEnv(slot,state);
      return state.gpr.x0.qword;
    };
    locals.owner=env(6,reinterpret_cast<addr_t>("android/os/Build"));
    const auto field=env(144,locals.owner,reinterpret_cast<addr_t>("MANUFACTURER"),reinterpret_cast<addr_t>("Ljava/lang/String;"));
    const auto model=env(144,locals.owner,reinterpret_cast<addr_t>("MODEL"),reinterpret_cast<addr_t>("Ljava/lang/String;"));
    locals.value=host.NewString(u"unknown");
    env(154,locals.owner,field,locals.value);
    env(154,locals.owner,model,locals.value);
    if(!locals.owner||!field||!model||!locals.value||!host.PendingException().empty())
      throw std::runtime_error("manufacturer profile static String initialization failed");
  }
  AndroidBuildManufacturerProfile(const AndroidBuildManufacturerProfile&)=delete;
  AndroidBuildManufacturerProfile &operator=(const AndroidBuildManufacturerProfile&)=delete;
  // No retained handles or cleanup: the initialized class owns the String.
};
}  // namespace bunker::windows

#pragma once
#include "../whole/bridge.h"
#include <stdexcept>
#include <string>

namespace bunker::windows {
// Explicit port capability: this build has no Android sensor-service backend.
// NULL lets the original Unity caller take its checked unavailable-service
// branch. This is not Android's ordinary empty-inventory behavior, a Windows
// hardware inventory, or a successful sensor/looper/event-queue implementation.
class SensorService {
 public:
  enum class Profile { Unavailable };
  explicit SensorService(Profile profile, addr_t marker_base=0x7ff470000000ULL)
      : marker_(marker_base) {
    if(profile!=Profile::Unavailable || !marker_ || (marker_&7))
      throw std::invalid_argument("unsupported sensor-service profile or marker");
  }
  SensorService(const SensorService&)=delete;
  SensorService& operator=(const SensorService&)=delete;
  addr_t Marker(const std::string &name) const {
    if(name!="ASensorManager_getInstance")
      throw std::invalid_argument("unsupported sensor-service import: "+name);
    return marker_;
  }
  void Install(recomp::Runtime &runtime) {
    if(installed_)throw std::logic_error("sensor-service imports already installed");
    // No device, samples, queue, callback, errno or thread-state side effects.
    runtime.AddImport(marker_,recomp::MakeBridge<addr_t()>([]{return addr_t(0);}));
    installed_=true;
  }
 private:
  addr_t marker_;
  bool installed_=false;
};
}

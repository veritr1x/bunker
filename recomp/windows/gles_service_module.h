#pragma once
#include "gl_host.h"
#include "module_registry.h"
#include <stdexcept>

namespace bunker::windows {
// Install GlHost's typed markers in the guest Runtime before registration.
// GlHost/EglHost retain backend ownership and must outlive active imports.
// This is a stateless service facade, not a mapped Android ELF or native DLL.
inline Module MakeGlesServiceModule(const GlHost &graphics) {
  Module module;
  module.name="libGLESv2.so";
  module.kind=Module::Kind::TypedService;
  for(const auto &name:GlHost::Commands()){
    if(!module.exports.emplace(name,graphics.Marker(name)).second)
      throw std::logic_error("duplicate typed GLES service export");
  }
  // Reopening only creates another registry handle generation. It does not
  // reset live GL contexts, unload ANGLE, or execute any guest lifecycle.
  module.reset_image=[]{};
  return module;
}
}  // namespace bunker::windows

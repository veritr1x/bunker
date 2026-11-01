#pragma once
#include "../whole/runtime.h"
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
class EglHost;
// GLES capability queries plus scalar state/clear commands. Native query
// results use tracked guest memory; unsupported signatures/query widths fail.
class GlHost {
 public:
  struct Query {uint32_t name;uint32_t count;uint32_t count_query=0;};
  // EglHost must outlive this provider and every active GL call.
  GlHost(EglHost &, const std::wstring &absolute_dll_directory,
                  addr_t marker_base=0x7ff450000000ULL);
  ~GlHost();
  GlHost(const GlHost&)=delete;
  GlHost &operator=(const GlHost&)=delete;
  void Install(recomp::Runtime &);
  addr_t Marker(const std::string &)const;
  void Invoke(const std::string &,State &);
  size_t QueryComponents(uint32_t name);
  static const std::vector<Query> &Queries();
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows

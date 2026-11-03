#pragma once
#include "../whole/runtime.h"
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
class EglHost;
// Typed GLES queries, scalar state, shader/program and buffer-backed draws.
// Transfers use tracked snapshots/publication. No retained client arrays,
// mapping, textures, uniforms/FBO APIs or compute execution are implemented.
// Readback is in-bounds RGBA8/default-FBO/no-PBO on owned immutable pbuffers.
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
  // Every supported typed command, in append-only marker order.
  static const std::vector<std::string> &Commands();
  struct FrameDiagnostics {uint64_t calls=0,draw_submissions=0,clear_submissions=0,capture_attempts=0;bool first_present_png=false,frame_png=false,nonuniform=false;int32_t width=0,height=0;std::string failure;};
  void EnableFrameDiagnostics(const std::wstring &absolute_png_path);
  FrameDiagnostics DescribeFrameDiagnostics();
  // Called on the render worker before an original window eglSwapBuffers.
  void CaptureWindowBeforePresent();
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows

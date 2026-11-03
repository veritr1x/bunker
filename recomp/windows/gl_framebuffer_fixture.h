#ifndef BUNKER_GL_FRAMEBUFFER_FIXTURE_H
#define BUNKER_GL_FRAMEBUFFER_FIXTURE_H
#include <stdint.h>
struct FramebufferObjects {
  uint32_t framebuffers[2];
  uint32_t renderbuffers[2];
};
struct FramebufferReport {
  uint32_t empty_status;
  uint32_t complete_status;
  int32_t renderbuffer[9];
  int32_t attachment[2];
};
struct FramebufferTextureReport { int32_t attachment[4]; };
#endif

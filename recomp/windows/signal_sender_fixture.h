#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
struct SenderReport {
  uint32_t calls;
  int32_t signal_number;
  int32_t handler_error;
  int32_t process_id;
  uint32_t real_uid;
  uint32_t caller_error_changed;
  uint64_t token, handler_sp, handler_fp;
  uint8_t info[128];
};
int sender_configure(struct SenderReport*);
int sender_invoke(uint64_t,int32_t,uint32_t);
int sender_checkpoint(void);
void sender_return_boundary(void);
#ifdef __cplusplus
}
static_assert(sizeof(SenderReport)==176,"sender report wire");
#endif

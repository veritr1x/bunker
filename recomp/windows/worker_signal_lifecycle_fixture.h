#pragma once
#include <stdint.h>
typedef struct WorkerSignalReport {
  uint64_t token,mask,pending,alt_pointer,alt_size,joined;
  int32_t alt_flags;
  uint32_t rounds,error,flags;
} WorkerSignalReport;

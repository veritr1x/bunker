#pragma once
#include <stdint.h>
typedef struct PriorityRecord {
 uint64_t before;
 int32_t value, error;
 uint64_t after;
} PriorityRecord;
typedef struct PriorityWorker {
 uint32_t tid;
 uint32_t reserved;
 uint64_t token;
 PriorityRecord direct, indirect;
} PriorityWorker;

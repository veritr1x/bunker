#pragma once
#include <stdint.h>
typedef struct AffinityRecord {uint64_t before;int64_t value;int32_t error;uint32_t padding;uint64_t after;} AffinityRecord;
typedef struct AffinityWorker {uint32_t tid,initial_mask;uint64_t token;AffinityRecord self_direct,self_indirect;} AffinityWorker;
#ifdef __cplusplus
static_assert(sizeof(AffinityRecord)==32&&sizeof(AffinityWorker)==80);
#else
_Static_assert(sizeof(AffinityRecord)==32&&sizeof(AffinityWorker)==80,"strict fixture wire sizes");
#endif

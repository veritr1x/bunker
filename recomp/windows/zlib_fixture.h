#pragma once
#include <stdint.h>
#define ZLIB_RECORDS 4096
struct ZlibRecord {
    int32_t result;uint32_t kind,avail_in,avail_out;
    uint64_t total_in,total_out,adler,input_offset,output_offset;
    int32_t data_type;uint32_t message,state,padding;
};
struct ZlibFixture {
    uint64_t input,input_size,output,output_size;
    uint32_t input_chunk,output_chunk;
    int32_t window_bits,flush;
    uint32_t options,count,allocations,frees;
    struct ZlibRecord records[ZLIB_RECORDS];
};

#pragma once
#include <stdint.h>
struct DrawInput {uint64_t vs,fs,vlengths,flengths,vertices,indices;int64_t vertex_bytes,index_bytes;int32_t vcount,fcount;};
struct DrawObjects {uint32_t vs,fs,program,buffers[2],vao;};
struct DrawStatus {int32_t vertex,fragment,linked,shader_deleted,program_log_length;};
struct DrawRead {int32_t x,y,width,height,alignment,row_length,skip_rows,skip_pixels;};

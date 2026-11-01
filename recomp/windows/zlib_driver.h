#pragma once
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "zlib_fixture.h"
#include "zlib_generated_cases.h"
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
typedef int (*zlib_call)(struct ZlibFixture*);
static int run_zlib_cases(zlib_call call){
#ifdef _WIN32
  _setmode(_fileno(stdout),_O_BINARY);
#endif
  struct ZlibFixture *fixture=(struct ZlibFixture*)malloc(sizeof(*fixture));
  unsigned char output[4096];if(!fixture)return 1;
  for(unsigned test=0;test<sizeof(zlib_cases)/sizeof(*zlib_cases);++test){
    const struct ZlibCase *c=&zlib_cases[test];memset(fixture,0,sizeof(*fixture));memset(output,0xa5,sizeof(output));
    fixture->input=(uintptr_t)c->data;fixture->input_size=c->length;fixture->output=(uintptr_t)output;fixture->output_size=c->capacity;
    fixture->input_chunk=c->input_chunk;fixture->output_chunk=c->output_chunk;
    fixture->window_bits=c->window_bits;fixture->flush=c->flush;fixture->options=c->options;
    int32_t result=call(fixture);
    if(result<=-997||fixture->count>ZLIB_RECORDS){fprintf(stderr,"zlib fixture internal failure %u: %d\n",test,result);return 1;}
    fwrite(&result,4,1,stdout);fwrite(&fixture->count,4,1,stdout);fwrite(&fixture->allocations,4,1,stdout);fwrite(&fixture->frees,4,1,stdout);
    fwrite(fixture->records,sizeof(struct ZlibRecord),fixture->count,stdout);fwrite(output,1,sizeof(output),stdout);
  }
  free(fixture);return ferror(stdout)?1:0;
}

#define BSEARCH_DRIVER
#include "libc_bsearch_fixture.h"
#include <errno.h>
int*__errno(void){return &errno;}
extern int bsearch_fixture_invoke(BSearchReport*);
extern uintptr_t bsearch_guest_empty(void);
static void invoke(BSearchReport*r){if(bsearch_fixture_invoke(r))r->calls=129;}
int main(void){if(bsearch_guest_empty())return 1;int result=execute_bsearch_records(invoke);if(result)return result;puts("BSEARCH-REFERENCE-SUCCESS empty=1");return 0;}

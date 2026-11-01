#include "zlib_driver.h"
extern int guest_inflate(struct ZlibFixture*);
int main(void){return run_zlib_cases(guest_inflate);}

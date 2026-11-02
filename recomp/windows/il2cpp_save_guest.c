#include <setjmp.h>
#include <stdint.h>
_Static_assert(sizeof(void*)==8 && sizeof(jmp_buf)==256,"Android save-helper profile");
extern void observe_save(void *,void *);
void collector_save_callback(void *opaque,void *zero){observe_save(opaque,zero);}

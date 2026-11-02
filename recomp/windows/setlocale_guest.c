#include <locale.h>
#include <stdlib.h>
#include <stdint.h>
#include <errno.h>
_Static_assert(LC_ALL==6 && LC_CTYPE==0 && LC_IDENTIFICATION==12,"Android13 category ABI");
_Static_assert(sizeof(locale_t)==8 && sizeof(size_t)==8,"Android64 locale object and MB_CUR_MAX");
struct observation {char *name;size_t maximum;locale_t selection;int32_t error,reserved;};
uintptr_t guest_setlocale(int category,const char *name,int indirect,int sentinel,struct observation *out){
 errno=sentinel;
 __typeof__(&setlocale) volatile select=setlocale;
 char*result=indirect?select(category,name):setlocale(category,name);
 out->name=result;out->error=errno;out->maximum=MB_CUR_MAX;out->selection=uselocale(0);
 return (uintptr_t)result;
}

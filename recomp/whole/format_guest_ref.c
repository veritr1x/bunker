#include <stdarg.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
static unsigned char captured[512];
static int capture(const char *format, va_list args) {
  return vsnprintf((char *)captured, sizeof(captured), format, args);
}
int fixture_printf(const char *format, ...) {
  va_list args; va_start(args,format); int r=capture(format,args); va_end(args); return r;
}
int fixture_vprintf(const char *format, va_list args) { return capture(format,args); }
int __android_log_print(int priority,const char *tag,const char *format,...) {
  (void)priority;(void)tag;va_list args;va_start(args,format);capture(format,args);va_end(args);return 1;
}
int __android_log_vprint(int priority,const char *tag,const char *format,va_list args) {
  (void)priority;(void)tag;capture(format,args);return 1;
}
int __android_log_write(int priority,const char *tag,const char *text) {
  (void)priority;(void)tag;strcpy((char *)captured,text);return 1;
}
#define printf fixture_printf
#define vprintf fixture_vprintf
#include "format_guest.c"
#undef printf
#undef vprintf
int main(void) {
  for(unsigned n=0;n<16;++n) {
    unsigned char out[512];memset(out,0xa5,sizeof(out));memset(captured,0,sizeof(captured));
    int32_t result=format_case(n,(char *)out);
    fwrite(&result,4,1,stdout);fwrite(out,1,512,stdout);fwrite(captured,1,512,stdout);
  }
}

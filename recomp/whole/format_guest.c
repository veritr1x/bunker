#include <stdarg.h>
#include <stddef.h>
extern int snprintf(char *, size_t, const char *, ...);
extern int vsnprintf(char *, size_t, const char *, va_list);
extern int sprintf(char *, const char *, ...);
extern int vsprintf(char *, const char *, va_list);
extern int printf(const char *, ...);
extern int vprintf(const char *, va_list);
extern int __android_log_print(int, const char *, const char *, ...);
extern int __android_log_vprint(int, const char *, const char *, va_list);
extern int __android_log_write(int, const char *, const char *);
static int via(char *out, size_t n, const char *format, ...) {
  va_list args; va_start(args, format); int r = vsnprintf(out, n, format, args); va_end(args); return r;
}
static int via_s(char *out, const char *format, ...) {
  va_list args; va_start(args, format); int r = vsprintf(out, format, args); va_end(args); return r;
}
static int via_p(const char *format, ...) {
  va_list args; va_start(args, format); int r = vprintf(format, args); va_end(args); return r;
}
static int via_log(const char *format, ...) {
  va_list args; va_start(args, format); int r = __android_log_vprint(4, "bunker", format, args); va_end(args); return r;
}
#define MIX "%d:%.2f|%d:%.2f|%d:%.2f|%d:%.2f|%d:%.2f|%d:%.2f|%d:%.2f|%d:%.2f|%d:%.2f|%d:%.2f"
#define VALUES 11,1.25,22,2.5,33,3.75,44,4.0,55,5.25,66,6.5,77,7.75,88,8.0,99,9.25,110,10.5
__attribute__((visibility("default"))) int format_case(unsigned n, char *out) {
  switch (n) {
    case 0: return snprintf(out, 512, MIX, VALUES);
    case 1: return via(out, 512, MIX, VALUES);
    case 2: return sprintf(out, MIX, VALUES);
    case 3: return via_s(out, MIX, VALUES);
    case 4: return snprintf(out,512,"%ld|%lu|%lld|%llu|%hhd|%hhu|%hd|%hu|%zd|%td", -4294967297L,~0UL,(-9223372036854775807LL-1),~0ULL,129,511,32769,131071,(ptrdiff_t)-12345678901L,(ptrdiff_t)12345678901L);
    case 5: return via(out,512,"%*.*f|%.*s|%#08x|%c|%%",-12,4,1.25,3,"bunker",0x12,0);
    case 6: return snprintf(out,9,"%s:%d","truncated",123);
    case 7: return snprintf(out,1,"%d",12345);
    case 8: return snprintf((char *)0,0,"%s:%d","query",123);
    case 9: return snprintf(out,512,"%+.3e|%.4g|%.3a|%F|%G",1234.5,0.0012345,1.25,__builtin_inf(),-__builtin_inf());
    case 10: return printf(MIX, VALUES);
    case 11: return via_p("%ld:%*.*f:%c:end",-4294967297L,10,3,1.25,0);
    case 12: return __android_log_print(4,"bunker",MIX,VALUES);
    case 13: return via_log(MIX,VALUES);
    case 14: return __android_log_write(5,"bunker","plain log");
    case 15: return snprintf(out,512,"%p|%020p",(void *)0x1234,(void *)0x1234);
    default: return -999;
  }
}

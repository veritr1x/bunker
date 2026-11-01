#include <errno.h>
#include <locale.h>
#include <stdint.h>
#include <stdlib.h>
#define REQUIRE(x) do { if (!(x)) return __LINE__; } while (0)

int guest_locale(const char *name, int mask, unsigned long expected) {
  locale_t initial = uselocale(0);
  REQUIRE(initial == LC_GLOBAL_LOCALE);
  REQUIRE(MB_CUR_MAX == 4);
  errno = 17;
  locale_t l = newlocale(mask, name, (locale_t)(uintptr_t)0x12345678);
  REQUIRE(l != 0 && errno == 17);
  REQUIRE(uselocale(l) == initial);
  REQUIRE(uselocale(0) == l && MB_CUR_MAX == expected);
  locale_t next = newlocale(0, "C", l);
  REQUIRE(next != 0 && next != l);
  REQUIRE(uselocale(next) == l && MB_CUR_MAX == 1);
  REQUIRE(uselocale(l) == next && MB_CUR_MAX == expected);
  REQUIRE(uselocale(initial) == l && MB_CUR_MAX == 4);
  freelocale(l);
  freelocale(next);
  return 0;
}

int guest_locale_invalid(const char *name, int mask, int expected_errno) {
  errno = 17;
  REQUIRE(newlocale(mask, name, 0) == 0);
  REQUIRE(errno == expected_errno);
  REQUIRE(uselocale(0) == LC_GLOBAL_LOCALE && MB_CUR_MAX == 4);
  return 0;
}

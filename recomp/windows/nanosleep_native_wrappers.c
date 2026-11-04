#include <time.h>
int nanosleep_direct(const struct timespec*request,struct timespec*remaining){return nanosleep(request,remaining);}
int nanosleep_indirect(const struct timespec*request,struct timespec*remaining){int(*volatile call)(const struct timespec*,struct timespec*)=nanosleep;return call(request,remaining);}

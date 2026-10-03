#pragma once
#include <stddef.h>

struct lt_rebinding {
    const char *name;     // C symbol name without the leading underscore
    void *replacement;
    void **original;      // receives the previous target; may be NULL
};

// Redirect imported calls from images whose path contains `image`.
// `bindings` must stay valid for the life of the process.
void lt_rebind_image_symbols(const char *image, const struct lt_rebinding *bindings, size_t count);

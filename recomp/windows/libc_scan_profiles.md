# Exact Unity scanner formats

The host accepts the four string formats recorded by the original Unity caller
and the existing `%llu` profile. Arguments are input, format, and four explicit
AArch64 GP output pointers; no foreign `va_list` crosses the host boundary.

The focused differential gate links the same NDK caller object into static
Bionic and the translated Windows fixture. It compares return values, guest
errno, and complete output records, including unchanged buffers and canaries.
Cases cover EOF/matching failure, partial assignment, widths 15/3/45,
suppression, `%c` without NUL, CR/LF, and high-byte UTF-8. Host guard controls
cover unsupported formats, source/format aliases, exactly assigned outputs,
invalid memory, stable page protections, and exact-fit NUL publication. The
assigned-output misuse controls are host defensive policy, outside valid C
scanf input. Input and format must be valid readable C strings; the shared
memory implementation does not promise C++ exceptions for arbitrary invalid
input pointers.

This is an exact-format profile, not general scanf support. The new string
profiles use native CRT scanning into owned temporary buffers, then checked
copyback in assignment order. State/Memory and native environment are checked
at the genuine installed callback. No game or full host build is run here.

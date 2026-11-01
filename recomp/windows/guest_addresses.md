# Host-provider guest identifier namespaces

These values identify checked runtime imports or opaque host objects; they are
not committed Windows pages or native function pointers. Convert through the
owning provider. Keep combined imports and object tokens disjoint. Runtime
AddImport rejects duplicate addresses before guest execution.

| Starting value | Owner / purpose |
|---|---|
| `0x7ff000000000` | JNI function markers; VM slots start at +0x1000 |
| `0x7ff100000000` | JNI object references |
| `0x7ff200000000` | JNI method/field IDs |
| `0x7ff400000000` | Module registry import markers |
| `0x7ff410000000` | Native window object tokens; bounded below EGL imports |
| `0x7ff420000000` | EGL import markers |
| `0x7ff430000000` | EGL opaque display/config/surface/context handles |
| `0x7ff440000000` | ANativeWindow import markers |
| `0x7ff450000000` | Typed GL resolver markers (reserved/in progress) |
| `0x7ff460000000` | Android nonlocal-jump import markers |
| `0x7ff500000000` | Module loader opaque handles |
| `0x7ff600000000` | Filesystem import markers |
| `0x7ff600100000` | Signal import markers |
| `0x7ff600200000` | Semaphore import markers |
| `0x7ff700000000` | Filesystem stream handles |
| `0x7ff800000000` | Logging import markers |
| `0x7ff900000000` | Pthread import markers |
| `0x7ffa00000000` | Pthread stable thread tokens |
| `0x7ffb00000000` | Libc import markers |
| `0x7ffd00000000` | Zlib import markers |

Standalone fixtures can use isolated test identifiers, but must not carry
those allocations into the combined application without checking this map.
In particular, ANativeWindow's original default overlapped ModuleRegistry;
its combined/default marker base is now `0x7ff440000000`. EGL's data handles
already own `0x7ff430000000`, so that value cannot be reused for window imports.

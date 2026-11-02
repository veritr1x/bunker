# Original IL2CPP stack-top-only gate

This isolated native Windows diagnostic executes the actual parameterless
helper at0x825b1974 after all9 original IL2CPP constructors. It runs the original
pthread_self/getattr_np/attr_getstack/attr_destroy path, returning the current
thread's actual guest stack base+size. Pthreads::Run enforces return PC/SP.

The gate independently queries the real Pthreads attributes before/after,
checks actual committed Windows backing, requires stable identity/stack data
and verifies the original helper result. It destroys the copied attributes,
executes both original finalizers through normal ModuleRegistry close, runs
remaining registered teardown callbacks, retires the original thread/TLS, and
checks the old token no longer exposes stack attributes. It never calls Self
after retirement. Original init counters, GC flags, collector record-init flag
and all256 thread buckets must remain pristine throughout. No record is created
or rewritten to make an assertion pass.

The constructor/helper/finalizer execution is explicitly exploratory: the old
393781-trace/3079-object cohort retains189 unsupported traces after its already
validated128-definition shard01066 replacement. The overlay's exact ownership,
closure and canonical State-layout proof are required; no engine retranslation
or old-object modification is performed. This does not call il2cpp_init,
metadata loading, GC initialization/collection, signals, save callbacks or
nonlocal control transfer. Those remain separate gates.

`il2cpp_stack_prepare.py` requires a NEW output directory, pins old metadata,
objects, input ELF, overlay proof and State header, and freezes committed host
6d097e1. The new harness is an explicit separately hashed source overlay. Live
filesystem/setvbuf or graphics edits cannot enter that archive. Remill headers,
zlib headers/backend and old trace/data headers are copied and hashed. The new
builder links only these frozen files using a response file. Missing imports
retain named fatal markers; signals remain explicitly undeliverable in the
unpolled profile. No success stubs or raw ARM64 execution are supplied.

From WSL prepare against the preserved accepted Windows baseline:

```sh
python il2cpp_stack_prepare.py --baseline WINDOWS_IL2CPP_BASELINE \
  --out NEW_STACK_DIRECTORY --remill REMILL_HEADERS --zlib WINDOWS_ZLIB
```

Then run `il2cpp_stack_build.ps1 -BuildDirectory NEW_STACK_DIRECTORY` on Windows
and `test_il2cpp_stack.py --build NEW_STACK_DIRECTORY --apk ORIGINAL_APK` in WSL.
The latter uses a fresh process and new storage, preserves its log/final audit,
and reverifies old executables, metadata, frozen sources, all3079 original
objects and the overlay before/after. Actual original ELF/APK SHA256 are checked
again by the executable for the exact runtime paths. A passing helper gate is
not evidence that the original collector's thread registration or scanning works.
The isolated il2cpp_stack_hashes.ps1 performs batched read-only SHA256 on native
Windows paths, avoiding cross-WSL file-read overhead; it changes no artifacts.

The corrected candidate uses a hash-object backing vector declared before the
BCrypt handle scope, so BCryptDestroyHash runs while its backing is still live.
The earlier stack3 executable/proof is preserved as superseded evidence; the
corrected harness is prepared and verified in a fresh stack4 directory.

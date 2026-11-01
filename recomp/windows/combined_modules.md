# Bounded Unity / IL2CPP module diagnostic

This separate diagnostic uses the accepted old Unity COFF snapshot and the
original IL2CPP snapshot with its validated shard-01066 overlay. Host sources
come from parent-approved commit 1942e24. It does not refresh either engine.
The two engine snapshots are mixed and unpolled; this is not a whole-library,
signal-delivery, GC, managed-code or game-execution proof.

The sole isolated Java profile addition is Object.getClass, absent from the
frozen host cohort. combined_java_class.h delegates to the existing checked
[JNI GetObjectClass operation (slot 31)](https://docs.oracle.com/en/java/javase/17/docs/specs/jni/functions.html#getobjectclass).
It caches global jclass references by IsSameObject identity, deletes each
temporary local, and returns the stable global for Host to clone into a
caller-local reference. Cached globals remain owned by Host until teardown;
the adapter's destructor performs no JNI calls. The Linux and Windows tests
reuse the independently translated NDK direct/V/A/stack-V caller with a
zero-argument descriptor (its spare argument is ignored), checking actual
receiver-class identity, null/stale receivers, pending exceptions and worker
concurrency. No production JNI source is modified.

The preparer verifies the original APK/ELFs, derives image spans and lifecycle
arrays from ELF headers/relocations, checks x86_64 COFF machine types, and checks
the union trace-definition ownership and direct guest references. The approved
host sources (including the lifecycle extraction helper) must match their Git
blobs. It copies those sources, Remill headers, generated metadata and original
data images into a new work directory. All original engine objects stay in
place and are individually hashed. The build uses only this frozen source copy.

ModuleRegistry is the sole owner of all 417 Unity and nine IL2CPP constructors
and both pairs of reverse-order finalizers. One runtime uses the exact union
trace validator; the providers and Java host are shared. Both original data
images have distinct verified bases. The path catalog advertises only these
registered modules, with actual ELF data files mounted at their guest paths.

After Unity JNI_OnLoad, 42 native bindings and the established initJni(Context)
gate, the harness calls the actual Unity findLibrary helper at 0x7041a214:

| Machine field | Assignment and evidence |
| --- | --- |
| X0 | Original UTF-8 literal 0x70ed01b3, independently checked as "il2cpp". |
| X1 | Explicit output address of an owned, guarded 40-byte NativeString. |
| X8 | Fresh runner State starts at zero. This is not an indirect-result argument: the helper overwrites W8 with LDRB from X0 before using it. |
| SP / LR / TLS | Actual Pthreads runner guarded stack, return sentinel and per-thread TLS. |

The actual caller around RVA 0x424ab8 initializes pointer offset 0, length offset
24, inline NUL offset 8 and allocator tag 0x49 at offset 32; objects are spaced
40 bytes. Actual assignment RVA 0xdff6c and destructor RVA 0xe0044 establish the
same layout. The destructor loads the heap pointer/capacity/tag and dispatches
the real Unity allocator. The harness copies the resulting path first, calls
that actual destructor once, and checks both guards. No CRT free is substituted.
The ignored evidence directory work/unity-il2cpp-load-audit contains the exact
disassembly and source hashes.

Only the actual returned absolute path is passed to Registry.Open. The 222
Unity-requested exports must equal both the proved original rebased addresses
and the loaded ELF symbols. Alias/refcount and nonfinal close checks must avoid
reinitialization. Unity's 222 API slots plus loader handle are compared before
and after: this harness never calls the whole loader at 0x703b7650, its
post-resolution startup queue, il2cpp_init, GC, or any looked-up API body.

Run preparation under WSL with explicit --unity-build, --il2cpp-build,
--host-source, --apk, --remill, --zlib and --out paths. Then run
combined_modules_build.ps1 -BuildDirectory <new directory> -Run on Windows.
The new directory keeps combined_inputs.json, object-symbols.txt, frozen sources,
combined_build_record.json and combined-run.log. The final log/result must be
consulted for the actual reached boundary; this document alone asserts no pass.

The first verified Windows run passed the bounded gate with executable SHA256
5881a4910072ebaaab45f7537a85f53c7203c46425d197a31dbc66c9bf1449bd.
The real helper returned /data/app/bunker/lib/arm64/libil2cpp.so, and both module
lifecycle sequences completed. test_combined_modules.ps1 passed 17 checks,
including wrong-module/APK rejection before guest constructors. The isolated
runtime-class test passed 42 checks and 256 concurrent NDK calls on each host.
The initial missing-getClass executable, source, inputs, build record and log
are retained separately under names containing first-getclass in that workdir.
Run test_combined_java_class.py --build <WSL workdir> once normally and once with
--windows before a fresh combined build using this isolated Java profile.

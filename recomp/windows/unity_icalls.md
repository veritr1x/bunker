# Original Unity internal-call registration diagnostic

This NEW isolated variant follows the frozen original API-loader gate574235f.
It preserves that executable, sources, data images, manifests and all3,548 old
COFF objects; no whole-engine refresh or shared provider/runtime edits occur.
Prepare a fresh workdir using unity_icalls_prepare.py --base-build pointing to
work/windows-unity-api-loader and --audit pointing to work/unity-init-audit,
then run unity_icalls_build.ps1 -Run and test_unity_icalls.ps1.

The original helper/APIloader/JNI prefix is retained. Actual observer count at
712ba2e0 must be zero; original IL2CPP map879a5b70 must have begin=map+8/root0/
count0, and init counter879a6190/GC flags must be zero. Differing live state is
a decisive precondition failure. No real game state is reset or fabricated.

The original709dd61c dispatcher runs once. A copied harness trace table forwards
AddInternalCall8254d19c through its unchanged original native Entry, journaling
all1,987 ordered name/guest-pointer pairs. Actual resolve_icall verifies every
returned pointer, without invoking any target. Three stored targets have
unsupported OLD Unity entry traces; this gate never qualifies their bodies.

Frozen LibC is installed once in a bridge runtime; harness forwarding journals
original malloc/free and actual __cxa_atexit/finalize effects with the same State.
The real constructor registers8257cdc0(object879a5b70,DSO8740c790). Map traversal
proves node/key allocation ownership. During actual guest cached-handle close,
real module finalizers execute the registered destructor once with the correct
DSO filter, freeing every observed map allocation. The harness never manually
calls it and never clears the destroyed C++ object's stale header. Providers and
both images remain live through callbacks; prior loader's process-lifetime
empty path-cache allocation/stale slots remain explicitly unreused.

No full3bd0d8 wrapper, configuration API, il2cpp_init/init_utf16, GC, managed code,
RegisterModules or stored native target executes. The mixed old snapshots are
unpolled and do not prove collector or whole-library correctness. OOM/translated
C++ exception paths are outside the bounded normal-registration proof and fail
decisively if reached. The isolated --self-test checks pristine-state rejection
without changing guest memory or running constructors.

# Three original IL2CPP preinit APIs

NEW isolated variant after accepted registration gate7a32580. Prepare a fresh
workdir using unity_preinit_prepare.py --base-build work/windows-unity-icalls
--out work/windows-unity-preinit, then unity_preinit_build.ps1 -Run and
test_unity_preinit.ps1. Old sources,3,548 objects/images/executables are preserved;
the profile retains frozen1942e24 host sources and mixed unpolled old engines.

After real417+9constructors/JNI42/initJni/APIloader222/ICalls1987,only these
original loaded APIs execute: log callback70425524,policy0,commandline with LIVE
original371778/371784 getter results and nullbase. Void returns are ignored;
actual IL2CPP log/policy/argc/ownedUTF16 vector state is checked. The real Unity
argv backing40-byte NativeStrings,pointer array/count/guard and checked decoder
are snapshotted; no fabricated argv or trailing-null assumption. Measured argc0
proves only the empty-argument path; no broader copy coverage is implied.

The ctor6-registered vector destructor825baac4(object879a7608,DSO8740c790)
runs once through real module/DSO close,freeing all observed owned allocations.
Only afterward Unity's registered419c74 destroys the original input owner.
Providers/images remain live. No manual destructor/global reset occurs; destroyed
headers and prior process-lifetime cache/top slots are not reused or cleared.

Paths/config-dir/data-dir/debugger/lazy-manager/full3bd0d8 are deferred while the
normal Managed-copy prerequisite is qualified separately. This API-level gate
does not claim boot advanced through that copy. Initcounter/GC remain0;the real
ICall map/observer and deferred state stay unchanged. No init,GC,managed or stored
native target runs. Existing3unsupported stored bodies remain explicitly untested.

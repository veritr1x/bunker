# APK ReflectionHelper

This adapter implements the original APK's `ReflectionHelper` metadata lookup
and a bounded, separate native proxy protocol. It uses real Host method/field
IDs and backed `Constructor`, `Method`, and `Field` objects. It does not share
JNIBridge's native ABI or infer a callback from an opaque native handle.

Constructor, method and field lookup enumerate copied declared metadata, follow
the original superclass stopping rules, and compare descriptors using the DEX
scores: exact 1, declared subtype 0.5, reverse assignability 0.1, otherwise 0.
JNI assignability supplies the actual supported class relationships. The
4096-entry synchronized cache uses the original class-identity/String hash and
retains positive and negative results. Field signatures describe the selected
field's actual type, including a covariant result requested as `Object`.
Declared-member order is the Host's deterministic metadata order; ART order and
unmodeled constructor access modifiers are not claimed.

The proxy factory currently supports the declared singleton `Runnable` profile
through either original factory overload. It preserves the actual application
loader, class identities, complete 64-bit handle, and the existing
`ReflectionLaunchEpoch` owner. `run()` invokes the actually registered
`nativeProxyInvoke(J,String,Object[])Object` through the provided native runner.
The nullable argument array remains null for the zero-argument callback. The
native exception/default flag is retained, including logging token zero for the
abstract-method branch. An expired launch returns null and suppresses native
finalization, as in the APK. Explicit handler finalization uses the actual
registered `nativeProxyFinalize`; adapter destruction never issues a finalizer.
Other interface, default-method, primitive-boxing and Object callback profiles
fail explicitly.

The derived Java catalog corrects the APK's real `ReflectionHelper$b` interface
and `$1` handler ancestry. The core `InvocationHandler` declaration precedes the
APK catalog. Existing JNIBridge interface declarations are conditional when the
same core interface already exists. Four Java arguments require a fresh
bootstrap and all JNI-dependent host translation units.

`prepare_reflection_catalog.py --parent <qualified unity_bootstrap_data.h>
--out <fresh directory>` reproduces the reviewed catalog using only the Python
standard library. It checks the exact parent digest and requires output digest
`6516d02411aa51376b90f23fff08d2c55ec9797c92c4b369fd9fd97c97f2a29d`
before writing. The original catalog is preserved.

The original DEX is preserved in
`work/launch-url1-end-launch-boundary1/classes2.dex.ReflectionHelper.txt`.
`work/field-reflection-native-proxy-audit1/acceptance.json` identifies the real
native table and lazy engine initialization callback; registration execution in
the earlier game run was unobserved. Active callbacks require a real
`Host.NativeEntry`, with no hardcoded-address fallback or manual initializer.
The focused module qualification passes 244 checks through 87 actual NDK calls,
including four lookup-call forms, three factory-call forms, nine actual fixture
native invocations and two native exception-log calls. It covers covariant
Activity/Object selection, positive/negative cache behavior and collisions,
full-width handles, nullable arguments and shared-epoch suppression. The native
bodies are explicitly compiled TEST callbacks, not original Unity callbacks;
automatic or explicit native finalization was not executed by this gate.
Evidence is `work/reflection-helper-qualification2/acceptance.json`, SHA256
`38f506eee7aaed31afcc15519a1bc4d9dfef829a18f52f6b8212494ac5670636`.
The combined packet is
`work/reflection-helper-source-preparation1/final-acceptance.json`, SHA256
`36631154b4cd582ab5b1c80849eca4671f25f0e285d815c8120484ba4fed27f9`.
This port does not establish a visible original game frame, full ART reflection,
or automatic Java GC/finalization.

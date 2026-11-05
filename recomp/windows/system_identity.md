# Java object identity for the Windows JNI host

The host implements the static method
`java.lang.System.identityHashCode(Object): int`. A null reference returns zero.
Every live reference alias to the same host Java object returns the same stable
identity, including local, global and weak references. The operation uses the
existing `Object::identity_hash` field and counter under `ProviderLock`, shared
with the default `Object.toString` representation. It never invokes a virtual
`hashCode` override. Hash collisions are permitted; numeric hashes are not
required to match a different Java VM.

The method uses the existing checked static JNI callback path. Reference/thread
validation, pending exceptions, callback ownership and the 32-bit JNI result ABI
retain their normal behavior. No public header, object layout, clock service,
locale service or Android SDK implementation was added. Other unsupported
System methods remain unsupported.

The actual original run reported a missing `java/lang/System`, followed by a
`UnityEngine.AndroidJavaProxy` type-initializer exception. Unity's official
[2019.4 AndroidJava implementation](https://github.com/Unity-Technologies/UnityCsReference/blob/2019.4/Modules/AndroidJNI/AndroidJava.cs)
initializes that proxy's static System class reference and resolves exactly
`identityHashCode` with signature `(Ljava/lang/Object;)I`. Those three literals
also occur in the original game's metadata. This identifies a concrete missing
core Java dependency; it does not establish that the exception caused every
black frame.

The source and requirement evidence are retained in
`recomp/work/system-identity-source-preparation1`. Its source manifest records
the exact frozen parent/candidate hashes, unchanged header, and a whole-file
inverse removing only the eight added lines. The method's contract follows
[System.identityHashCode](https://docs.oracle.com/javase/8/docs/api/java/lang/System.html#identityHashCode-java.lang.Object-).
Focused translated JNI qualification is separate from actual game integration.

The focused Windows gate passes 567 checks through 40 actual translated NDK
calls in direct, V and A forms. It covers null, reference aliases and ownership,
cleared weak references, strings, arrays, classes, override bypass, threads and
consistency with default `toString`. A separate Windows JDK 24 contract fixture
passes 21 checks; it compares properties rather than arbitrary numeric hashes.
Receipts are `recomp/work/system-identity-qualification2/acceptance.json`
(SHA-256 `853a099d1a0c12dccadfcb9111a2c8e70a096b396347871d96be77b1cb1ee315`)
and `recomp/work/system-identity-jdk-contract1/acceptance.json`
(`4720db02cafe613691626143991e462e2e77396d74e79e8d1e7e9a8c73308661`).

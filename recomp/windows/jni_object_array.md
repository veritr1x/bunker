# Reached JNI reference arrays

The natural frame diagnostic reached JNIEnv slot 172 while handling the missing
Settings.Secure class. The host now implements NewObjectArray, GetArrayLength,
GetObjectArrayElement and SetObjectArrayElement (slots 172/171/173/174).
The [JNI specification](https://docs.oracle.com/en/java/javase/17/docs/specs/jni/functions.html#array-operations)
defines their table positions, reference results, element initialization and
store/index checks. These are real owned arrays, not empty placeholder results.

Each array owns its elements independently of local/global reference handles.
Reads return fresh caller-local references. Replacing an element defers arbitrary
payload destruction until the outer provider mutex is released, matching the
existing field/reference ownership protocol. Cleared weak references used as
values become null; invalid live handles retain explicit reference errors.

Reference-array class metadata is created from a declared component class,
including nested arrays. The array's class loader follows its component and
creation does not initialize that component. GetObjectClass/FindClass share one
class identity. Arrays have Object as superclass, implement Cloneable and
Serializable, and use recursive reference covariance. The builtin String,
Class, Throwable (including subclasses), StringBuilder and File Serializable
facts are also represented, along with Intent/ComponentName/Bundle Cloneable
facts. This supplies type metadata, not Java serialization or object cloning.
Invalid descriptors exceeding 255 array dimensions are rejected before recursion.

Bounds and failed stores preserve existing elements. Negative lengths are
rejected; native allocation failure reports OutOfMemoryError. Interface and
array classes cannot be instantiated through NewInstance/NewObject/AllocObject.
Invalid JNI inputs have host diagnostics; no Android-device behavior for invalid
constructor IDs or out-of-contract allocation inputs is claimed.

`test_jni_object_array.py` freezes the host and seven actual NDK API24 fixture
functions, translates them using the accepted indexed-FP toolchain, then executes
the real JNI table calls on Windows and Linux. Candidate4 passes 1,450 checks on
each host with no unsupported traces or unresolved direct targets. It covers
257 initialized elements, fresh local identities, weak/global/nested ownership,
null/cleared-weak values, bounds/store failures, Serializable/interface types,
application-array class loaders, local-frame promotion, attached-thread access
and payload retirement that reenters JNI from another native thread. Earlier
candidates are preserved; candidate1's 1,395-check gate predates the weak/loader/
interface review fixes. Evidence is ignored in `work/jni-object-array4/acceptance.json`.
The existing JNI36, Java141, Context14, PackageManager155, callback464 and
constructor362 regressions pass on each host, including the enabled-AR failure
subprocess. They use the reviewed provider immediately before the isolated rank
guard and four additional framework marker facts; the final focused gate covers
those deltas. Exact source versions remain in `work/jni-array-regressions1/`.

Primitive arrays, array method-descriptor marshaling, arbitrary application
interface declarations, Java serialization and tracing collection of cyclic
Java object graphs remain outside this explicit host catalog. These checks do
not establish full Java execution, Settings values or a completed game frame.

Builtin interface facts are recorded in the official Java API declarations for
[String](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/lang/String.html),
[Class](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/lang/Class.html),
[Throwable](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/lang/Throwable.html)
and [StringBuilder](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/lang/StringBuilder.html).
Android13 framework declarations confirm
[Intent](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-13.0.0_r1/core/java/android/content/Intent.java),
[ComponentName](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-13.0.0_r1/core/java/android/content/ComponentName.java)
and [Bundle](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-13.0.0_r1/core/java/android/os/Bundle.java).

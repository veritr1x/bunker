# JNI reference-array method results

The OBB getter's genuine `()[Ljava/io/File;` result needs the JNI object-call
family. JNI specifies arrays as reference types beneath `jobject` and describes
array signatures with the full `[` descriptor:

- [JNI reference types and signatures](https://docs.oracle.com/en/java/javase/17/docs/specs/jni/types.html#reference-types)
- [JNI object method direct/V/A calls](https://docs.oracle.com/en/java/javase/17/docs/specs/jni/functions.html#calltypemethod-routines-calltypemethoda-routines-calltypemethodv-routines)

The zero-argument convenience overload and general handler declaration accept
reference-array results through the existing `FindReferenceArrayClass` validator.
Object invocation accepts `[` in the object-call family, and callback result
validation retains the full descriptor for existing `Assignable` covariance
checks. Ordinary `Lclass;` validation, constructor rules, callback frames,
unlocked retirement and one-local return promotion retain their existing paths.
Primitive arrays, FP handlers, unknown/malformed descriptors, rank over 255 and
more than three argument slots remain unsupported. This supplies no OBB getter,
storage backend or Java platform behavior.

`test_jni_array_result.py` freezes committed support plus only the owned JNI
provider and new fixture/test overlays. Candidate `work/jni-array-result1` uses
support `f6e472a83603fc6a8978017d721482727abdcdb6` and the accepted immutable
lifter/semantics. Both native Windows and Linux hosts pass 2,289 focused checks
from the same actual Android NDK fixture, with 36 strict trace heads and zero
unsupported traces or unresolved direct targets. The unchanged regressions pass
on each host: JNI36, constructor362, callback464 and object-array1450.

The focused gate executes instance, static and existing-static binding calls;
direct/V/A and forced stack-V transport; null and cleared weak returns; typed
File[], subclass covariance, Object[] and nested arrays; wrong scalar/component/
rank rejection; unchanged ordinary-object guards; exact result class/identity;
callee-local retirement, nested user frames, array-owned element lifetime and
exceptional cleanup. Guest jvalue and output canaries remain intact. Evidence,
source/tool/binary hashes and actual stdout/stderr are preserved in the candidate
acceptance JSON and per-host logs. This component gate makes no frame-render claim.

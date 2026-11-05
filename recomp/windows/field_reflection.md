# Backed Java field reflection and four-argument JNI calls

The JNI host represents `java.lang.reflect.Field` using a real declared field
ID and its declaring Class object. `ToReflectedField` (JNI slot 12) creates a
fresh local Field reference after checking the supplied class and static flag.
An inherited field retains its actual declaring owner. `FromReflectedField`
(slot 8) recovers that same field ID. Plain host instances, Method objects,
unknown IDs and mismatched class/static combinations cannot create a backed
Field. Existing pending exceptions are preserved by both conversion operations.

`Field.getDeclaringClass()` and `Field.getName()` read that metadata. The host's
`DescribeReflectedField` and `DescribeReflectedMethod` APIs return copied
owner/name/signature/static records while holding the provider lock. They expose
no internal pointers and reject objects without the corresponding real
reflection backing. The Method form also describes genuine Constructor objects.
Other Field operations, including `getType`, are not implied by this support.

`DeclaredFields` and `DeclaredMethods` copy only the members owned by the supplied
Class. They retain actual owner/name/signature/static metadata and deterministic
catalog key order; original DEX declaration order is not modeled. Constructors
and static initializers remain explicit method names. Callers must check pending
exceptions before treating an empty result as an empty class. These APIs provide
metadata for the separate ReflectionHelper lookup adapter; they execute no Java
method and invent no overload candidates.

The declared host Java callback limit is now four arguments; five are rejected.
Direct JNI calls read the fourth general argument from X6, and V/A calls use the
existing checked variadic/jvalue decoding. Reference retention and owned callback
frames also cover all four arguments. This changes the public C++ callback type
from `std::array<addr_t,3>` to `std::array<addr_t,4>`: bootstrap and all dependent
host objects must be freshly compiled together. Guest State, Memory and translated
guest code are unchanged.

The core catalog declares the standard `java.lang.reflect.InvocationHandler`
interface before application metadata is installed. Its invocation body remains
the responsibility of a real implementing class.

The original run advanced past System lookup and reported missing Field followed
by an `AndroidReflection` initializer exception. Unity's official
[2019.4 AndroidJava source](https://github.com/Unity-Technologies/UnityCsReference/blob/2019.4/Modules/AndroidJNI/AndroidJava.cs)
resolves `Field.getDeclaringClass()Ljava/lang/Class;` in that initializer. Its
ReflectionHelper method/field lookups have four Java arguments. Implementing those
application helper bodies and their separate native proxy bridge is distinct
from the core metadata/conversion operations described here.

Source snapshots and whole-file inverses are retained under
`recomp/work/field-reflection-source-preparation4`. Component qualification and
actual game integration are separate; this support does not establish the cause
of a black frame or force an original scene transition.

The focused Windows gate passes 194 checks through 42 actual translated NDK
entries, including eight four-argument callbacks. A separate real JDK 24/native
JNI fixture passes 28 checks for valid Field conversions, inherited declaring
owners, static fields and four-argument calls. Receipts are
`recomp/work/jni-field-four-qualification3/acceptance.json` (SHA-256
`46c2e9e9690ccf69fdc03e066b4e688f41ba3fc939738edfce0fd1f1915199b1`)
and `recomp/work/jni-field-four-jdk-contract2/acceptance.json`
(`199ec10a9528a0cef38a8787683732156cf2a2866a8f391be4d12167e85af0a0`).
Declared-member selection is exercised separately by the application
ReflectionHelper adapter's qualification.

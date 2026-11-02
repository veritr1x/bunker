# JNI integer and binary32 methods

`DefineIntMethod` and `DefineStaticIntMethod` take a callback returning int32_t.
`DefineFloatBitsMethod` and `DefineStaticFloatBitsMethod` take a callback returning
the exact uint32_t binary32 representation. The latter is a bits API: do not
numerically cast stored bits to float. Neither API supplies Number/Integer/Float,
preferences, hashCode or other Java method bodies.

MethodArguments remains three addr_t words. I uses its low32bits; J retains64;
F is zero-extended raw32bits. References/arrays remain checked handles. Numeric
arguments are never cloned as references. Callbacks retain the existing owned
frame, borrowed receiver/reference locals, unlocked invocation, cleanup floors,
exception preservation and reentrant retirement. Numeric results promote no
object reference. Object results and exact-owner constructors still use their
existing guarded promotion, including when an argument is F.

Instance int49-51/static129-131 write W0; instance float55-57/static135-137 write
S0 and zero its unused128-bit register portion. Family/signature/receiver/static
guards remain in the shared invocation path. No double, primitive-array, nonvirtual
call or wider argument-count support was added. All old L/array result guards,
native binding rules and no-body unsupported boundaries remain.

Direct calls use independent GP and FP cursors after the three fixed JNI GP
arguments. F arrives as a default-promoted double in D0 onward. V calls snapshot
Android's va_list and consume GR slots8bytes or VR slots16bytes, then use the
shared8-byte stack cursor as each bank exhausts. Only an accessed negative bank
cursor is validated; unused or exhausted banks are not mistaken for references.
The double is numerically narrowed to float. A calls read the4-byte jvalue.f
representation instead. All caller lists, save areas and argument arrays remain
unchanged. The scalar result writer copies raw bits without an FP conversion.

[Android13 ART reflection.cc](https://android.googlesource.com/platform/art/+/android-13.0.0_r1/runtime/reflection.cc)
uses va_arg(jdouble) followed by AppendFloat for F, while its A-array path copies
the raw32-bit union word. The separate register save areas and stack allocation
are specified by the pinned
[AAPCS64 2025Q1 appendix](https://github.com/ARM-software/abi-aa/blob/2025Q1/aapcs64/aapcs64.rst).
Primary source hashes are preserved in work/jni-numeric-proposal/sources.json.

Candidate work/jni-numeric3 freezes committed3c7309a plus the owned core/new tests.
The original Android NDK numeric object is also linked into a native ARM64
reference executable and run under the pinned QEMU Cortex-A53. Its18 promotion
rows, including signaling-NaN quieting, are recorded before lifting. Expectations
therefore do not come from the host's JNI argument reader or lifted conversions.

Windows and Linux each pass11125 focused checks: actual compiler-produced
instance/static direct/V/A and forced GP/VR/both-stack V calls, actual Base and
interface declaration IDs selecting derived I/F/object overrides before decoding,
mixed F/J/F and
reference/F/I arguments, signed extrema, Â±0, subnormals, finite values, infinities,
quiet/signaling NaN payloads, exact S0/W0 banks, caller va_list/register-save/jvalue
canaries, object/constructor promotion, callback exceptions/retirement, malformed
active cursors and deliberately invalid unused bank metadata. The unchanged
regressions pass on each host: JNI36, Java141, constructor362, callback464,
raw64/array/staticvoid861 and array-result2289. This is core transport evidence,
not proof of PlayerPrefs storage or a rendered frame.

The known proxy hashCode()I declaration remains unimplemented. Once slot49 has
generic integer transport, its reached error moves from unsupported JNIEnv slot
to the actual Java method having no host implementation. No default hash/body
was added. Old frozen proxy evidence is preserved; its runner expectation string
needs this explicit diagnostic update when rerun against the new core.

Candidate1 stopped during build because its freeze script omitted the new header;
it is preserved and makes no host-runtime claim. Candidate2 includes both core
files, the complete old regression fixtures, and its own runner source.

Candidate2 passed the initial10751 checks but review identified a real declaration
ID gap: decoding before virtual selection used an abstract/base declaration's
empty host argument metadata. Candidate3 resolves the existing receiver/override/
result guards first, then decodes with the selected implementation metadata.
Internal builtin recursive calls retain their already-decoded/default arguments;
Class.forName retains its known three-GP shape, and constructors keep exact-owner
decoding. The new Base/interface tests reproduce that legal JNI use directly.
Candidate2 and its qualification records remain preserved.

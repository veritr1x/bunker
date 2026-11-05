# Named String byte-charset profile

The checked host implements `String(byte[], String)` and
`String.getBytes(String)` for UTF-8, UTF-16, UTF-16BE, UTF-16LE, US-ASCII and
ISO-8859-1, with explicitly tested aliases. Exact malformed replacement,
UTF-16 code units, encoded bytes and BOM behavior follow the installed
JDK 24.0.1 oracle recorded by this qualification. Public named-constructor
malformed behavior is implementation dependent; this is a named JDK profile,
not an ART equivalence or a promise to implement all JDK charsets.

NDK callers exercise direct, `V` and `A` construction and object-method calls,
read actual UTF-16 JNI characters and returned byte arrays, and check identity,
frames, lifetime and the generic constructor control. Null and invalid-name
exceptions match the oracle. A syntactically valid name outside the qualified
profile, such as Shift_JIS, fails with an explicit native host-profile guard;
it is not assigned an invented Java unsupported-encoding result.

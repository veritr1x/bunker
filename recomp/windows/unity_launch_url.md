# Retained UnityPlayer launch URL

The original APK's protected `UnityPlayer.getLaunchURL()String` reads the
instance field `m_launchUri:Landroid/net/Uri;`. It returns null when the field
is null; otherwise it invokes that URI's virtual `toString()` and returns the
result. The constructor captures `currentActivity.getIntent().getData()` into
that field. `newIntent` changes the field and also posts an original native/job
operation; implementing it as a field setter alone would omit required behavior.

`AndroidContext::BindUnityPlayer` now adds this retained constructor fact and
binds the getter through the existing checked JNI object/virtual-call helpers.
It snapshots the configured Activity's actual Intent data. Each subsequent
getter reads the player's field, allowing null, an empty string, Unicode and
supported URI subclasses' virtual results. Method exceptions remain pending.
Fresh local references are returned and temporary URI/Intent references released;
the Java field retains the URI independently of the Context adapter's lifetime.
This change adds no general Java interpreter or `newIntent` implementation.

Native startup `70424358..704250ec` calls `70425858` at `70425000`, which reaches
the launch-URL bridge `70426850` and guards a null result at `704268bc`. After
that call, this startup function sets its initialized flag and destroys seven
temporary strings before returning. No further UnityPlayer callback occurs in
that bounded continuation; other independent callbacks remain separate work.

The Context change is confined to `AndroidContext::BindUnityPlayer`. A new
instance-object `BindObjectMethod` API adds a two-line declaration and two-line
forwarder to the existing checked `DefineHandler` path. All existing JNI
handlers, invocation/frame code, metadata IDs and object layout remain exact.
The collector source guard must admit that qualified addition by reversing it
to the historical JNI source hashes; historical receipts remain unchanged.
Bootstrap, build script, collector execution, graphics, guest translations,
audio-disabled APK and generated headers remain unchanged. Qualification must
use real translated NDK direct/V/A callers and check URI field replacement,
virtual dispatch, null/empty/Unicode results and reference lifetimes. Existing
Intent and initial AR behavior remain relevant regression checks.
Binding tests must reject unknown, native, static, already implemented and
incompatible declarations without changing the existing declaration checks.

The completed gate passes1262 checks per Windows/Linux host:176 launch-URL and
binding checks,83 unchanged Intent checks,141 initial-AR checks, and the existing
JNI core36/callback-frame464/constructor-frame362 checks. The enabled-AR profile
still reaches its expected unsupported boundary. URI tests include absent,
empty, Unicode/NUL/non-BMP strings, retained identity, reference lifetimes,
field replacement, virtual dispatch and exceptions through NDK direct/V/A calls.
Receipt `work/unity-launch-url-qualification3/acceptance.json`, SHA256
`5751e2f3ec2d12e8ce0bf962e0ce8000072a9400a0f03f341f810f1068fa4a93`.
Earlier attempts are preserved: the first applied an inappropriate strict-warning
setting to a historical fixture; the second exposed the missing instance-object
binding API. The third uses the qualified binder and passes.

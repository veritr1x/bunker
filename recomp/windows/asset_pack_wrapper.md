# APK AssetPackManagerWrapper missing-library branch

`AndroidAssetPackWrapper` ports only the reached original startup branch of the
exact APK. It binds the existing nonnative `init(Context)` and
`playCoreApiMissing()` declarations. It creates a real nonnull wrapper object,
stores null manager field `b`, allocates an owned empty typed HashSet in `c`,
leaves `d` null, and publishes the same object in original class-static `a`.
`playCoreApiMissing` reads actual field `b`; it does not supply an unconditional
missing result. A second init throws the exact original RuntimeException and
does not replace the singleton. A dedicated recursive class monitor serializes
publication, matching the original synchronized init path. The original Context
argument can be null on this missing-class branch: resolution fails before a
Factory implementation could dereference it.

The adapter is enabled only for actual verified APK SHA256
`9ded0797ee607b6892b531ba3a02f4c4510774f5fe098ccada78ccff881c9209`,
complete accepted code/split proof SHA256
`b2be67185a866f3489146d9864ca40d1de5c2668037f026609890afe12940689`,
and an explicitly closed APK-only application code scope. The integration owner
must verify the mounted APK against its normal input identity contract and keep
the approved loader scope closed; a matching string is not a runtime APK verifier.
The independent proof scans all4968 ZIP entries, all four DEX containers (including
`assets/audience_network.dex`) and22777 class definitions. None defines PlayCore
AssetPackManagerFactory, assetpacks or tasks classes. Split metadata exists, but
its one empty module and74 language entries have no named code splits; no
uses-split is declared. Additional/unknown/present code profiles are rejected.

Init also performs a real Factory class lookup and catches only the actual
NoClassDefFoundError, matching the original constructor's encoded catch range.
Unexpected visible Factory metadata stops explicitly. It never defines a fake
Factory, invokes a fabricated getInstance, returns a null wrapper to skip work,
or reports empty pack success. This profile establishes missing API code; it
does not establish that the game has no local assets or asset packs.

HashSet support is bounded to its exact class identity, actual superclass chain
HashSet→AbstractSet→AbstractCollection→Object, the already supported
Cloneable/Serializable facts and an empty owned host hash container. It does not
port unrelated Set/Collection graph behavior, Java HashMap internals or collection
operations. Android's [HashSet source](https://android.googlesource.com/platform/libcore/+/309f9df/ojluni/src/main/java/java/util/HashSet.java)
documents the original empty construction and type facts. No general collection
capability is advertised by this private constructor allocation.

Original native init0x704221f8 keeps a real JNI GlobalRef to the returned wrapper
at native instance+0x78. It immediately queries playCoreApiMissing through
0x704223f0; true takes0x704222cc and skips the original path/listener/callback
setup. Native destructor0x7042a7c0 owns deletion of its references; the adapter
never calls it or deletes any original native handle. Class-static `a` is the
real Java singleton root and remains owned by Host after local/GlobalRef drops
and adapter retirement. The adapter has no additional strong wrapper cache or
root cycle. Its method closures hold weak adapter state; calls after retirement
stop with an explicit owner-expired boundary. Worker callers and original
JNI/module teardown must quiesce before adapter retirement, and Host must outlive
the adapter. No native callback/finalizer executes from adapter destruction.

The original getInstance wait(3000)/interrupt/retry loop is unported and remains
an explicit unimplemented method. Pack path/state/download/remove/listener/
mobile-data methods remain unimplemented. The wrapper's original missing-API
check protects their reached native setup, but this port makes no path, count,
download, Binder, callback, gameplay or collection claim.

## Qualification

Run `test_asset_pack_wrapper.py --out <fresh-directory>` in WSL using the tools
Python environment. It archives host21b12c4, freezes the five implementation/
fixture/runner overlays and accepted code profile, compiles the actual strict NDK
callers, and tests both native hosts. The NDK fixture invokes real JNI direct/V/A
factory and boolean calls; examines actual static/private fields and typed Java
exceptions; checks static/local/GlobalRef/adapter ownership; and races four
attached JNI threads so exactly one init publishes and the other three throw.
TEST native callback/delete bindings are actual translated fixture addresses and
are never invoked by the adapter. A TEST-only typed manager assignment proves
the boolean body reads `b` and changes with the field; it is not a production
Factory or PlayCore implementation. Changed APK, unknown/present code, open scope,
unexpected visible Factory, active path/getInstance calls, and retired-owner calls
stop at named boundaries.

Candidate1 passed173 focused checks and seven boundaries per host, plus the
unchanged JNI core36, callback-frame464 and constructor-frame362 regression
checks per host. Candidate2 adds the TEST field mutation and retired-owner boundary
with provider bytes unchanged and passes209 focused checks and eight boundaries
per host. It rechecks only the focused fixture; its final acceptance is recorded
separately. Frozen source/object/binary hashes and logs
are retained under `work/asset-pack-wrapper1` and `work/asset-pack-wrapper2`.
The original DEX/native evidence and proposed scope are in
`work/assetpack-version-audit`; the independent complete APK proof is in
`work/playcore-init-audit`.

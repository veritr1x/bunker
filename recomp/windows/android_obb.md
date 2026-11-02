# Context OBB directories from an explicit host catalog

The reached original Unity call is `getObbDirs()[Ljava/io/File;` through Env33,
returning to `0x70ab5d38`. Original `0x4250ec` calls the generated wrapper
`0xabaf8c` at `0x425150`. A null or empty array invokes legacy `getObbDir()`;
the loop skips null elements, obtains each actual File's absolute path, and
constructs `main.<version>.<package>.obb` and `patch.<version>.<package>.obb`.
No expansion file is supplied by this implementation.

[Android 13 ContextImpl](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/app/ContextImpl.java)
derives OBB roots from the ordered external volume list, attempts to create the
directories, and preserves unavailable/failed entries as null slots.
`getObbDir()` takes the first slot, including null, rather than searching for a
successful secondary volume. The exact primary sources, original native
consumer and package inventory are preserved in `work/obb-audit`.

`AndroidContextConfig::external_obb_volumes` is an optional closed host capability
catalog. Unset means unsupported. An explicitly empty vector means this port
exposes zero Android external volumes; it does not describe an Android device or
infer device absence from package metadata. Each entry declares a canonical
absolute virtual root and availability. Context snapshots the ordered catalog,
derives only `<root>/Android/obb/<actual-package>`, and invokes
`prepare_obb_directory` outside JNI and storage cache locks. Available entries
require that verifier. Zero means a real directory was verified; positive Android
errno makes that slot null, and negative status is an invalid callback contract.
Unavailable entries retain null without a filesystem attempt.

Each getter creates a fresh typed File array and fresh backed File objects.
Caller mutation cannot change the configured catalog. File path strings belong
to each File's actual host object graph and survive with retained JNI references;
there is no hidden cached array/File root. Results are path snapshots, not leases
against later filesystem changes. Every new getter call verifies backing again.

On Windows, `MakeObbDirectoryPreparer` accepts only exact paths derived from its
own catalog and package. It requires a real mounted directory root, checks the
provider's write access, creates only the fixed Android/obb/package descendants,
and rechecks every existing object as a directory. Unmounted/read-only roots,
ordinary files and arbitrary paths fail. Existing central FS containment/reparse
rules apply. Windows creation uses the existing owner-private policy; no Android
UID, chmod, vold, FUSE, device-volume enumeration or full ACL equivalence is
claimed. The FileSystem and explicit mounts must outlive retained callbacks.

The existing external-storage state reports the port's internal-only unmounted
profile. The `MEDIA_MOUNTED` String is a platform constant, not evidence of a
mounted volume. A production empty OBB catalog must be selected explicitly by the
harness. Nonempty catalogs need corresponding real backing; this API does not
automatically mount host drives or change the other external directory APIs.

The exact APK SHA256 `9ded0797ee607b6892b531ba3a02f4c4510774f5fe098ccada78ccff881c9209`
contains 4968 ZIP members and no `.obb` member. That inventory does not establish
the presence or absence of separately installed expansion files or device volumes.

## Validation

`test_android_obb.py --out <fresh-directory>` archives committed `81cd2d0` and
overlays only its owned Context/OBB source and test files. Real NDK direct/V/A
callers test unset/empty/unavailable/mixed catalogs, typed arrays and null slots,
first-slot legacy behavior, caller mutation, verifier changes, reentrant attached
workers and JNI strong/weak/local-frame lifetimes. Portable verifier tests are
explicitly injected. Windows additionally tests the production adapter against
real mounted directories, missing and read-only roots, file conflicts and later
directory replacement, through actual NDK getters. Existing Context, internal
storage and object-array regressions run on both hosts. No OBB file bytes,
rendered frame, device-storage parity or game callback is fabricated.

The accepted JNI reference-array result prerequisite `f9e4815` is included in
that frozen host. Earlier candidates `work/android-obb1` and `work/android-obb2`
are retained: both stopped at host result-descriptor validation before guest
getter execution. No object descriptor substitution or core bypass was used.

Candidate `work/android-obb3` passes 106 focused checks on Windows (including
the real mapped filesystem cases) and 88 on Linux with the injected verifier.
Both hosts also pass Context14, internal-storage220 and object-array1450;
Windows adds the existing 13 rooted internal-storage checks. The executed
implementation and runner hashes are recorded in `acceptance.json`. This
documentation was completed after the run. No production OBB volume catalog or
natural game frame was executed by this component gate.

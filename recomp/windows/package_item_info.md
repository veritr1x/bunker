# Reached PackageItemInfo inheritance

The native Unity frame attempt in Native5 reached FindClass for
android/content/pm/PackageItemInfo and raised NoClassDefFoundError at return
0x70ab5478. The later Env13 return0x70ab524c is the original exception rethrow,
not an independent missing field. Its original metadata getter at RVAabf344..
abf354 requests metaData with signature Landroid/os/Bundle; on the class proxy
at130e4e8. GetFieldID is the actual Env94 vtable call atab5e30. Explicit bounded
original-byte windows and literal references are preserved in ignored
work/package-item-info-audit; windows without FDEs are not claimed as extents.

Android13 declares ApplicationInfo extends PackageItemInfo. The base owns the
existing packageName:String and metaData:Bundle fields. AndroidContext now
models this actual hierarchy and declares those two fields on the base instead
of redeclaring them on ApplicationInfo. Source/data/library paths, targetSdk,
flags and splitPublicSourceDirs remain actual ApplicationInfo fields.

Inherited field lookup is the existing checked JNI implementation: requesting
metaData/packageName through either class returns the same field ID and accesses
the same configured object state. No extra alias fields, empty metadata bundle,
or permissive FindClass behavior is introduced. Metadata remains governed by
GET_META_DATA for PackageManager snapshots; Context retains its configured
application metadata. Other uncatalogued PackageItemInfo members remain
unsupported, and no Java bytecode/constructor execution is implied.

The updated PackageManager fixture passes155 checks on both Windows and Linux:
the existing107 checks plus48 checks across direct/V/A/stack caller modes and
four real returned ApplicationInfo profiles. Its new NDK caller explicitly
performs FindClass, GetSuperclass, IsInstanceOf, IsAssignableFrom, inherited
GetFieldID, base GetObjectField and GetObjectClass. It verifies real metadata
presence/absence and package text, shared base/derived field identity, runtime
ApplicationInfo class, fresh caller-local results and output guards. The shared
NDK image has25 strict translated traces with zero unsupported/unresolved.

Evidence and fresh frozen support/overlay source are in ignored
work/windows-package-item-info. The source archive is committed hostf6eb677;
only android_context.cpp, package_guest_fixture.c and package_manager_test.cpp
are explicit source overlays. Existing accepted PM and Native5 artifacts are
preserved. This closes the evidenced class/metadata catalog gap; a later real
engine frame must verify progress beyond it.

Primary declarations:
[PackageItemInfo](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/content/pm/PackageItemInfo.java)
and [ApplicationInfo](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/content/pm/ApplicationInfo.java).

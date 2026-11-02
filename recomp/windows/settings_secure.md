# Reached Settings.Secure Android ID read

The original Unity consumer70417904 obtains the actual resolver, reads static
ANDROID_ID:String and calls static getString(ContentResolver,String)String.
Its original null/empty branch returns an empty C string, without populating the
nonempty digest cache. The host supplies this exact static field/method and
keeps the actual reader in its real context-owned resolver state. An unset
reader, unrecognized resolver, unsupported key or backing error fails explicitly.

MakeWindowsAndroidIdReader reads HKCU's64-bit view at
Software\Bunker\Apps\<exact APK package>\SecureSettings, named REG_SZ android_id.
Only actual ERROR_FILE_NOT_FOUND from open/query means absence and Java null.
An existing empty/String value is preserved unchanged. Unsupported type, size,
termination, unstable read and other Win32 errors are explicit failures. Reads
never create a key/value, generate an identifier, derive machine/SID data,
migrate an ID or call a server. A future existing Android ID input is outside
this change. This backing is an explicit Windows port store, not an assertion
of an Android device identity.

The [Android API](https://developer.android.com/reference/android/provider/Settings.Secure#getString(android.content.ContentResolver,java.lang.String))
permits null for an absent row. The [ANDROID_ID key](https://developer.android.com/reference/android/provider/Settings.Secure#ANDROID_ID)
is android_id; actual Android8+ identities depend on signing key, user and device.
The host does not claim to generate or reproduce those identities.

test_settings_secure.py freezes explicit support source plus this overlay, builds
real NDK field/direct/V/A callers on Windows/Linux, and tests reference/frame,
resolver and backing lifetimes. Windows-only registry tests use uniquely owned
temporary test package keys; the normal application key is never written. Core
JNI/context/package/callback/constructor/Java initialization regressions are
included. Component fixture Strings are labelled test values, not game identity.

Executed candidate1 freezes accepted host05ca57e plus the settings overlay.
Its32-trace strict fixture has no unsupported/unresolved entries on either host.
Focused checks passed70 on Windows and51 on Linux, including six expected fatal
subprocess boundaries each. The six regressions passed36/14/155/464/362/141 on
each platform. Windows test-owned registry package keys were removed after
handles closed. No normal application registry key/value was created or written.
Game wiring is ready for a fresh committed-host frame variant; it has not yet
established a new normal frame or a returned Android identifier.

# Context.DISPLAY_SERVICE

Android 13's `Context.java` declares `public static final String DISPLAY_SERVICE = "display";` at line 5347. The held [primary source](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/content/Context.java) SHA256 is `31f106e272391fc0d9679b6a7c369fc77940e37c5fac8fb9089bbed8df12de15`.

The Context catalog declares this exact static String field and initializes a real Java String through existing JNI SetStaticObjectField154. The class static field owns the String after the initialization local is deleted. This follows the existing LOCATION_SERVICE ownership path; no extra global reference or display-service object keeps it alive.

This provides the constant only. It supplies no getSystemService body, DisplayManager, display enumeration, monitor result, dimensions or hardware state. Game31's later null strcasecmp and pending-exception causality are a separate audit.

The new NDK fixture uses actual GetStaticFieldID144, GetStaticObjectField145 and SetStaticObjectField154. The focused host test checks exact content/type, inherited class lookup and declaring-field identity, fresh locals to the same String, wrong descriptors/staticness/owner/type, unchanged value after rejection, attached-thread reads, and class-owned lifetime after AndroidContext and caller-global teardown. It also verifies LOCATION_SERVICE remains the distinct exact `location` String. The existing LOCATION_SERVICE and Context tests run unchanged.

The runner freezes committed `da638ad866b21750a506ba1f68eff7587dfee873` support and overlays only android_context.cpp plus the three new executable fixture/test/runner sources. It proves the production source differs by only the field declaration and initialization line. Both hosts use the same real NDK object and frozen qualified lifter/semantics pair.

Fresh candidate1 passed on Linux and Windows: focused DISPLAY_SERVICE57, unchanged LOCATION_SERVICE56, and unchanged Context14 checks per host. Each actual NDK union has eight closed traces, zero unsupported traces and zero unresolved direct targets. The focused guest and C++ test compile with `-Wall -Wextra -Werror`. Acceptance `work/display-service1/acceptance.json` SHA256 is `50d9dfa655258da645c208deb44d26a2ddecf12cf41b088738a17874984b5df0`; source pin SHA256 is `08916f459ec19b5908ab13934527390700b174c5b4948f05aa0c51e576d1ad6f`. Original JNI test bodies and support are frozen; no Android runtime/hardware reference or game result is claimed. The Android value comes directly from the pinned primary source.

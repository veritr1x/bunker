package org.veritr1x.bunker;

import android.app.Application;
import dalvik.system.DexClassLoader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

/**
 * Lets the game start without Google Play services (a de-Googled phone,
 * Waydroid). Two of the game's libraries wait on them before the title screen:
 * Firebase's start-up asks Google to make Play services available, and the
 * Lilium attestation reports their absence, which stops the game. Bunker's own
 * versions of those two classes (android/no-play-services, built into
 * assets/lunar/no-play-services.dex) are loaded in place of the game's.
 *
 * A class loader placed in front of the game's (as its parent, which the
 * game's loader and Firebase's ask first) answers for the classes in that dex.
 * Lilium's other classes come from the game's own loader, so the replacement
 * and the game's classes it works with are the ones the rest of the game uses.
 */
final class NoPlayServices {
    private static final String LILIUM = "com.nekolaboratory.Lilium.";
    private static final String FIREBASE_HELPER = "com.google.firebase.app.internal.cpp.GoogleApiAvailabilityHelper";

    private NoPlayServices() {}

    static void install(Application app) {
        try {
            File dex = copy(app);
            ClassLoader game = app.getClassLoader();
            Field parent = ClassLoader.class.getDeclaredField("parent");
            parent.setAccessible(true);
            ClassLoader above = (ClassLoader) parent.get(game);
            Method find = ClassLoader.class.getDeclaredMethod("findClass", String.class);
            find.setAccessible(true);
            parent.set(game, new DexClassLoader(dex.getPath(), null, null, above) {
                @Override protected Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
                    boolean lilium = name.startsWith(LILIUM);
                    if (!lilium && !name.startsWith(FIREBASE_HELPER)) return super.loadClass(name, resolve);
                    synchronized (this) {
                        Class<?> loaded = findLoadedClass(name);
                        if (loaded != null) return loaded;
                        try {
                            return findClass(name);
                        } catch (ClassNotFoundException notOurs) {
                            if (!lilium) return super.loadClass(name, resolve);
                            try {
                                return (Class<?>) find.invoke(game, name);
                            } catch (ReflectiveOperationException e) {
                                throw new ClassNotFoundException(name, e.getCause() != null ? e.getCause() : e);
                            }
                        }
                    }
                }
            });
        } catch (Exception | LinkageError e) {
            android.util.Log.w("Bunker", "Could not load the game's Play services stand-ins; it needs Google Play services", e);
        }
    }

    /** The dex as a read-only file (Android 14 refuses writable code): copied again for each new build. */
    private static File copy(Application app) throws Exception {
        long installed = app.getPackageManager().getPackageInfo(app.getPackageName(), 0).lastUpdateTime;
        File file = new File(app.getCodeCacheDir(), "no-play-services-" + installed + ".dex");
        if (file.isFile()) return file;
        File[] old = app.getCodeCacheDir().listFiles((dir, name) -> name.startsWith("no-play-services-"));
        if (old != null) for (File f : old) f.delete();
        File partial = new File(app.getCodeCacheDir(), "no-play-services.partial");
        partial.delete();
        try (InputStream in = app.getAssets().open("lunar/no-play-services.dex"); OutputStream out = new FileOutputStream(partial)) {
            byte[] buffer = new byte[8192];
            for (int n; (n = in.read(buffer)) > 0; ) out.write(buffer, 0, n);
        }
        if (!partial.setReadOnly() || !partial.renameTo(file)) throw new java.io.IOException("Could not prepare " + file);
        return file;
    }
}

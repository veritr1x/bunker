package org.veritr1x.bunker;

import android.app.Activity;
import android.app.Application;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Runs in the game's own process before the game starts (providers are created
 * at process start). It serves no data. It:
 * - sends the game's loopback requests past any phone proxy (see LoopbackProxy);
 * - makes sure the local server is running when the game opens. The launcher
 *   starts the server before the game, but Android can also reopen the game
 *   directly, for example from Recent apps after an update or after the server
 *   was stopped. The game then waits on a black screen after the logo. In that
 *   case the launcher is opened instead: it starts the server and the game.
 */
public final class GameProcessProvider extends ContentProvider {
    @Override public boolean onCreate() {
        LoopbackProxy.install();
        Application app = (Application) getContext().getApplicationContext();
        refreshGameCodeAfterUpdate(app);
        forgetListOnPortChange(app);
        String game = gameActivity(app);
        if (game != null) app.registerActivityLifecycleCallbacks(new ServerCheck(game, Ports.assets(app)));
        return true;
    }

    /**
     * Unity extracts the game's code data (il2cpp/Metadata/global-metadata.dat)
     * to external storage on first launch and re-extracts only when the Unity
     * version changes, which our updates never do. Without this, an update's
     * patched addresses (for example a new --port-offset) would be ignored and
     * the game would keep using the first install's copy. Deleting the copy
     * after each install or update makes Unity extract the current one.
     */
    private static void refreshGameCodeAfterUpdate(Application app) {
        try {
            long installed = app.getPackageManager().getPackageInfo(app.getPackageName(), 0).lastUpdateTime;
            android.content.SharedPreferences prefs = app.getSharedPreferences("lunar_ports", android.content.Context.MODE_PRIVATE);
            if (prefs.getLong("installed", 0) == installed) return;
            java.io.File external = app.getExternalFilesDir(null);
            if (external != null) delete(new java.io.File(external, "il2cpp"));
            prefs.edit().putLong("installed", installed).commit();
        } catch (PackageManager.NameNotFoundException ignored) {}
    }

    /**
     * The game caches its asset list with the server's address written into it,
     * and keeps that copy while the list's revision is unchanged. After a build
     * with different ports (--port-offset), it would keep asking the old port.
     * Deleting the cached list (files/octo/pdb) makes it download the list again;
     * the downloaded asset files themselves are kept.
     */
    private static void forgetListOnPortChange(Application app) {
        android.content.SharedPreferences prefs = app.getSharedPreferences("lunar_ports", android.content.Context.MODE_PRIVATE);
        int offset = Ports.offset(app);
        if (prefs.getInt("offset", 0) == offset) return;
        delete(new java.io.File(app.getFilesDir(), "octo/pdb"));
        prefs.edit().putInt("offset", offset).commit();
    }

    private static void delete(java.io.File file) {
        java.io.File[] children = file.listFiles();
        if (children != null) for (java.io.File child : children) delete(child);
        file.delete();
    }

    private static String gameActivity(Application app) {
        try {
            Bundle meta = app.getPackageManager().getApplicationInfo(app.getPackageName(), PackageManager.GET_META_DATA).metaData;
            return meta == null ? null : meta.getString("org.veritr1x.bunker.GAME_ACTIVITY");
        } catch (PackageManager.NameNotFoundException e) {
            return null;
        }
    }

    /** Sends the player to the launcher when the game opens without its server. */
    private static final class ServerCheck implements Application.ActivityLifecycleCallbacks {
        private final String game;
        private final int assetsPort;
        ServerCheck(String game, int assetsPort) { this.game = game; this.assetsPort = assetsPort; }

        @Override public void onActivityCreated(Activity activity, Bundle state) {
            if (!activity.getClass().getName().equals(game)) return;
            Handler main = new Handler(Looper.getMainLooper());
            // Network calls are not allowed on the main thread.
            new Thread(() -> {
                if (serverAnswers()) return;
                main.post(() -> {
                    if (activity.isFinishing()) return;
                    // The launcher shares the game's task; clearing it replaces the
                    // game with the launcher, which then starts the server and the game.
                    activity.startActivity(new Intent(activity, MainActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
                });
            }, "lunar-server-check").start();
        }

        /** True when this app's server, not another program on the port, answers. */
        private boolean serverAnswers() {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL("http://127.0.0.1:" + assetsPort + "/companion/health").openConnection();
                connection.setConnectTimeout(1500);
                connection.setReadTimeout(1500);
                try (InputStream in = connection.getInputStream()) {
                    byte[] body = new byte[256];
                    int n = in.read(body);
                    return n > 0 && new String(body, 0, n, "UTF-8").contains("\"service\":\"lunar-tear\"");
                }
            } catch (Exception e) {
                return false;
            } finally {
                if (connection != null) connection.disconnect();
            }
        }

        @Override public void onActivityStarted(Activity activity) {}
        @Override public void onActivityResumed(Activity activity) {}
        @Override public void onActivityPaused(Activity activity) {}
        @Override public void onActivityStopped(Activity activity) {}
        @Override public void onActivitySaveInstanceState(Activity activity, Bundle out) {}
        @Override public void onActivityDestroyed(Activity activity) {}
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) { return null; }
    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) { return null; }
    @Override public int delete(Uri uri, String selection, String[] args) { return 0; }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { return 0; }
}

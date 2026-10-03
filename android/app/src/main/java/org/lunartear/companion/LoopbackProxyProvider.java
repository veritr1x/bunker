package org.lunartear.companion;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;

/**
 * Runs in the game's own process before the game starts (providers are created
 * at process start), to send its loopback requests past any phone proxy.
 * It serves no data.
 */
public final class LoopbackProxyProvider extends ContentProvider {
    @Override public boolean onCreate() { LoopbackProxy.install(); return true; }
    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) { return null; }
    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) { return null; }
    @Override public int delete(Uri uri, String selection, String[] args) { return 0; }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { return 0; }
}

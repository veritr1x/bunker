package com.nekolaboratory.Lilium;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import java.lang.reflect.Method;

/**
 * Stands in for the game's Lilium attestation step (NoPlayServices loads this
 * class in place of the game's own). The original checks Google Play
 * services and asks SafetyNet to attest the device. Without Play services it
 * reports PLAY_SERVICE_ERROR_*, and the game then shows Google's "enable Google
 * Play services" dialog and stops; with them, SafetyNet (shut down by Google)
 * fails and the game carries on. This reports that failure straight away on
 * every device, without touching Play services. The server never reads the
 * attestation.
 *
 * Loaded by another class loader, this class is outside the game's Lilium
 * package at run time, so it reaches the listener (a package-private
 * interface) by reflection.
 */
public class d {
    private Context a;
    private Object b;

    public d(Context context, d$d listener) {
        a = context;
        b = listener;
    }

    public void a(d$d listener) {
        b = listener;
    }

    public void a(byte[] nonce, String apiKey) {
        final Object listener = b;
        new Handler(Looper.getMainLooper()).post(() -> {
            try {
                Class<?> type = Class.forName("com.nekolaboratory.Lilium.d$d", false, listener.getClass().getClassLoader());
                Method failed = type.getDeclaredMethod("a", c.class);
                failed.setAccessible(true);
                failed.invoke(listener, c.c("ATTEST_UNEXPECTED_ERROR"));
            } catch (ReflectiveOperationException e) {
                android.util.Log.w("Bunker", "Lilium: could not report the attestation result", e);
            }
        });
    }
}

package org.veritr1x.bunker;

import android.util.Log;

/**
 * Starts the game's audio output again after a pause (audio_resume.c). The
 * game's Unity leaves it stopped when the game comes back, so the music and
 * sounds stay off until the game restarts.
 */
final class AudioResume {
    private static boolean done;

    private AudioResume() {}

    /** Points Unity's focus callback at the native fix, once Unity is running. */
    static void install() {
        if (done) return;
        String result;
        try {
            result = nativeInstall();
        } catch (Throwable error) {
            result = String.valueOf(error);
        }
        if (result.equals("not ready")) return;
        done = true;
        if (!result.isEmpty()) Log.w("Bunker", "Music after a pause not fixed: " + result);
    }

    /** The game was paused. */
    static void paused() {
        try {
            nativePaused();
        } catch (Throwable ignored) {
            // The library is missing; the game's own behaviour stays.
        }
    }

    private static native String nativeInstall();
    private static native void nativePaused();
}

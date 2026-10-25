package com.google.firebase.app.internal.cpp;

import android.app.Activity;

/**
 * Stands in for Firebase's helper of the same name (NoPlayServices loads this
 * class in place of the one Firebase's C++ library carries). The game's
 * Firebase start-up asks it to make Google Play services available; without
 * them the original shows Google's "enable Google Play services" dialog and
 * Firebase never answers, so the game stays black after the logo. This answers
 * at once as the original does when Play services are already there. Firebase
 * itself is not used: the server stands in for its services.
 */
public class GoogleApiAvailabilityHelper {
    private static final Object lock = new Object();
    private static boolean stopAllCallbacks = false;

    public static boolean makeGooglePlayServicesAvailable(Activity activity) {
        synchronized (lock) {
            stopAllCallbacks = false;
        }
        onComplete(0, "Google Play services are already available");
        return true;
    }

    public static void stopCallbacks() {
        synchronized (lock) {
            stopAllCallbacks = true;
        }
    }

    private static void onComplete(int resultCode, String resultMessage) {
        synchronized (lock) {
            if (!stopAllCallbacks) onCompleteNative(resultCode, resultMessage);
        }
    }

    private static native void onCompleteNative(int resultCode, String resultMessage);
}

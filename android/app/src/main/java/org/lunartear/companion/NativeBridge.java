package org.lunartear.companion;

public final class NativeBridge {
    static { System.loadLibrary("lunar"); }
    private NativeBridge() {}
    public static native String start(String dataDirectory, String assetDirectory);
    public static native void stop();
    public static native String status();
    public static native String checkDatabase(String directory);
    public static native String prepareBackup(String directory);
    public static native String edit(String dataDirectory, String assetDirectory, String request);
}

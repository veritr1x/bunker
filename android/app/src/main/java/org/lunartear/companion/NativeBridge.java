package org.lunartear.companion;

public final class NativeBridge {
    static { System.loadLibrary("lunar"); }
    private NativeBridge() {}
    public static native String start(String dataDirectory, String assetDirectory);
    public static native void stop();
    public static native String status();
    public static native String checkDatabase(String directory);
    public static native String prepareBackup(String directory);
    /** Unpacks revision 0 from an open .7z or .zip; the descriptor stays owned by the caller. */
    public static native String importArchive(int fd, String stage);
    public static native String importProgress();
    /** Applies the build's port offset (see Ports) before start; "" or an error. */
    public static native String setPortOffset(int offset);
    /** {"game":8003,"assets":8080,"accounts":3000}, moved by the offset. */
    public static native String ports();
    /** {"ok":bool,"checks":[{"name","port","ok","detail"}]}: is this server reachable on every port? */
    public static native String selfTest();
    public static native void cancelImport();
    public static native String importSaves(String dataDirectory, String source);
    public static native String edit(String dataDirectory, String assetDirectory, String request);
}

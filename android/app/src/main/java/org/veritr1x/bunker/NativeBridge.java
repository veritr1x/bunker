package org.veritr1x.bunker;

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
    /** Also keeps the server log in this folder, between sessions; "" or an error. */
    public static native String setLogDir(String directory);
    /** Writes a zip of the saved logs and the device details to an open document. */
    public static native String exportLogs(String directory, int fd, String info);
    public static native String importSaves(String dataDirectory, String source);
    /** Writes the largest texture in an asset bundle to target as a PNG for the Archive, no side over maxSide (0: full size); "" or an error. */
    public static native String texture(String bundle, String target, int maxSide);
    /** Writes the first audio clip in an asset bundle to target as Ogg Vorbis for the Archive; "" or an error. */
    public static native String audio(String bundle, String target);
    /** Writes a costume folder (…/3d/actor/ch008001) as a .glb for the Archive's 3D viewer; "" or an error. */
    public static native String model(String actorFolder, String target);
    /** Writes an animation clip for that costume as three.js clip JSON; "" or an error. */
    public static native String motion(String clipBundle, String actorFolder, String target);
    public static native String edit(String dataDirectory, String assetDirectory, String request);
}

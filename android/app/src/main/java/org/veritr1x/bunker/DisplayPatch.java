package org.veritr1x.bunker;

import android.content.Context;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/**
 * Frame rate and resolution chosen in Pod Programs (android_display.py writes
 * tools/display.conf). Applied in the game's process before Unity starts, so
 * a change takes effect the next time the game opens. The outcome is written
 * to tools/display.status for Pod Programs to show.
 */
final class DisplayPatch {
    private DisplayPatch() {}

    static void apply(Context context) {
        File tools = new File(context.getFilesDir(), "tools");
        File status = new File(tools, "display.status");
        int fps = 0, size = 0;
        try {
            for (String line : Files.readAllLines(new File(tools, "display.conf").toPath(), StandardCharsets.UTF_8)) {
                String[] pair = line.split("=", 2);
                if (pair.length != 2) continue;
                String value = pair[1].trim();
                if (pair[0].trim().equals("fps") && value.equals("60")) fps = 60;
                if (pair[0].trim().equals("resolution")) size = size(value);
            }
        } catch (Exception missing) {
            // Never chosen: the game's own settings.
        }
        if (fps == 0 && size == 0) {
            status.delete();
            return;
        }
        String result;
        try {
            System.loadLibrary("bunkerdisplay");
            result = apply(fps, size);
        } catch (Throwable error) {
            result = String.valueOf(error);
        }
        if (!result.isEmpty()) Log.w("Bunker", "Display settings not applied: " + result);
        try (FileOutputStream out = new FileOutputStream(status)) {
            out.write((result.isEmpty() ? "ok" : "error=" + result).getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {}
    }

    /** RenderTargetSize: FullHD 6, WQHD 7, DeviceMax 8; 0 keeps the game's presets. */
    private static int size(String name) {
        switch (name) {
            case "1080": return 6;
            case "1440": return 7;
            case "native": return 8;
            default: return 0;
        }
    }

    private static native String apply(int fps, int size);
}

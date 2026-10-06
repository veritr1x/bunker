package org.veritr1x.bunker;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.hardware.display.DisplayManager;
import android.os.Bundle;
import android.view.Display;
import android.view.WindowManager;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/**
 * Frame rate and resolution chosen in Pod Programs (android_display.py writes
 * tools/display.conf). The frame rate is capped at the screen's highest
 * refresh rate, which the game's window then asks for. Applied in the game's
 * process before Unity starts, so
 * a change takes effect the next time the game opens. The outcome is written
 * to tools/display.status for Pod Programs to show.
 */
final class DisplayPatch {
    private DisplayPatch() {}

    static void apply(Application context) {
        File tools = new File(context.getFilesDir(), "tools");
        File status = new File(tools, "display.status");
        int fps = 0, size = 0;
        try {
            for (String line : Files.readAllLines(new File(tools, "display.conf").toPath(), StandardCharsets.UTF_8)) {
                String[] pair = line.split("=", 2);
                if (pair.length != 2) continue;
                String value = pair[1].trim();
                if (pair[0].trim().equals("fps")) fps = frameRate(value, maxMode(context));
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
        else if (fps > 0) requestRefreshRate(context, fps);
        try (FileOutputStream out = new FileOutputStream(status)) {
            out.write((result.isEmpty() ? "ok" : "error=" + result).getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {}
    }

    /** The chosen rate ("60", "90", "120" or "max"), capped at the screen; 0 keeps the game's 30. */
    static int frameRate(String value, Display.Mode max) {
        int screen = max == null ? 60 : Math.round(max.getRefreshRate());
        int rate;
        if (value.equals("max")) rate = screen;
        else {
            try { rate = Integer.parseInt(value); } catch (NumberFormatException e) { return 0; }
        }
        rate = Math.min(Math.min(rate, screen), 240);
        return rate > 30 ? rate : 0;
    }

    /** The screen's mode with the highest refresh rate at its current resolution. */
    private static Display.Mode maxMode(Context context) {
        Display display = context.getSystemService(DisplayManager.class).getDisplay(Display.DEFAULT_DISPLAY);
        if (display == null) return null;
        Display.Mode current = display.getMode(), best = current;
        for (Display.Mode mode : display.getSupportedModes())
            if (mode.getPhysicalWidth() == current.getPhysicalWidth() && mode.getPhysicalHeight() == current.getPhysicalHeight()
                    && mode.getRefreshRate() > best.getRefreshRate()) best = mode;
        return best;
    }

    /** Asks for the refresh mode closest above the game's rate on each of its windows. */
    private static void requestRefreshRate(Application app, int fps) {
        app.registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
            @Override public void onActivityCreated(Activity activity, Bundle state) {
                Display display = activity.getWindowManager().getDefaultDisplay();
                Display.Mode current = display.getMode(), chosen = null;
                for (Display.Mode mode : display.getSupportedModes()) {
                    if (mode.getPhysicalWidth() != current.getPhysicalWidth() || mode.getPhysicalHeight() != current.getPhysicalHeight()) continue;
                    if (mode.getRefreshRate() + 0.5f < fps) continue;
                    if (chosen == null || mode.getRefreshRate() < chosen.getRefreshRate()) chosen = mode;
                }
                if (chosen == null) return;
                WindowManager.LayoutParams params = activity.getWindow().getAttributes();
                params.preferredDisplayModeId = chosen.getModeId();
                activity.getWindow().setAttributes(params);
            }
            @Override public void onActivityStarted(Activity activity) {}
            @Override public void onActivityResumed(Activity activity) {}
            @Override public void onActivityPaused(Activity activity) {}
            @Override public void onActivityStopped(Activity activity) {}
            @Override public void onActivitySaveInstanceState(Activity activity, Bundle out) {}
            @Override public void onActivityDestroyed(Activity activity) {}
        });
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

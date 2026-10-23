package org.veritr1x.bunker;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.hardware.display.DisplayManager;
import android.os.Bundle;
import android.view.ActionMode;
import android.view.Display;
import android.view.KeyEvent;
import android.view.KeyboardShortcutGroup;
import android.view.Menu;
import android.view.MenuItem;
import android.view.MotionEvent;
import android.view.SearchEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;

/**
 * Frame rate, resolution and screen area chosen in Pod Programs (android_display.py writes
 * tools/display.conf). The frame rate is capped at the screen's highest
 * refresh rate, which the game's window then asks for. Applied in the game's
 * process before Unity starts, so
 * a change takes effect the next time the game opens. The outcome is written
 * to tools/display.status for Pod Programs to show. The library also carries
 * the story-event zone fix, so it loads with the game's own settings too.
 */
final class DisplayPatch {
    private DisplayPatch() {}

    static void apply(Application context) {
        File tools = new File(context.getFilesDir(), "tools");
        File status = new File(tools, "display.status");
        int fps = 0, size = 0;
        boolean full = true;  // the game's own setting leaves a black bar beside the camera
        try {
            for (String line : Files.readAllLines(new File(tools, "display.conf").toPath(), StandardCharsets.UTF_8)) {
                String[] pair = line.split("=", 2);
                if (pair.length != 2) continue;
                String value = pair[1].trim();
                if (pair[0].trim().equals("fps")) fps = frameRate(value, maxMode(context));
                if (pair[0].trim().equals("resolution")) size = size(value);
                if (pair[0].trim().equals("screen")) full = !value.equals("safe");
            }
        } catch (Exception missing) {
            // Never chosen: the game's own frame rate and resolution, on the full screen.
        }
        // The story-event fix (display_patch.c) applies even with the game's own settings.
        String result;
        try {
            System.loadLibrary("bunkerdisplay");
            result = apply(fps, size);
        } catch (Throwable error) {
            result = String.valueOf(error);
        }
        if (!result.isEmpty()) Log.w("Bunker", "Display settings not applied: " + result);
        else if (fps > 0) requestRefreshRate(context, fps);
        if (full) useFullScreen(context);
        if (fps == 0 && size == 0) {
            status.delete();  // Pod Programs reports on chosen settings only.
            return;
        }
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

    /**
     * The game was built without Unity's "render outside safe area", so in
     * landscape Android leaves the camera cutout's whole edge black. Drawing
     * there is a window setting, and Unity sets it back from its own setting
     * once it starts, through Window.setAttributes. Every such change passes
     * through the window's callback with the window's own attributes, so the
     * callback restores short edges before the change reaches the screen.
     */
    private static void useFullScreen(Application app) {
        app.registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
            @Override public void onActivityCreated(Activity activity, Bundle state) {}
            @Override public void onActivityStarted(Activity activity) {
                Window window = activity.getWindow();
                if (window.getCallback() instanceof ShortEdges) return;
                window.setCallback(new ShortEdges(window.getCallback()));
                window.setAttributes(window.getAttributes());
            }
            @Override public void onActivityResumed(Activity activity) {}
            @Override public void onActivityPaused(Activity activity) {}
            @Override public void onActivityStopped(Activity activity) {}
            @Override public void onActivitySaveInstanceState(Activity activity, Bundle out) {}
            @Override public void onActivityDestroyed(Activity activity) {}
        });
    }

    /** The activity's window callback, keeping the window around the camera cutout. */
    private static final class ShortEdges implements Window.Callback {
        private final Window.Callback base;
        ShortEdges(Window.Callback base) { this.base = base; }

        @Override public void onWindowAttributesChanged(WindowManager.LayoutParams attrs) {
            attrs.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            base.onWindowAttributesChanged(attrs);
        }
        @Override public boolean dispatchKeyEvent(KeyEvent event) { return base.dispatchKeyEvent(event); }
        @Override public boolean dispatchKeyShortcutEvent(KeyEvent event) { return base.dispatchKeyShortcutEvent(event); }
        @Override public boolean dispatchTouchEvent(MotionEvent event) { return base.dispatchTouchEvent(event); }
        @Override public boolean dispatchTrackballEvent(MotionEvent event) { return base.dispatchTrackballEvent(event); }
        @Override public boolean dispatchGenericMotionEvent(MotionEvent event) { return base.dispatchGenericMotionEvent(event); }
        @Override public boolean dispatchPopulateAccessibilityEvent(AccessibilityEvent event) { return base.dispatchPopulateAccessibilityEvent(event); }
        @Override public View onCreatePanelView(int feature) { return base.onCreatePanelView(feature); }
        @Override public boolean onCreatePanelMenu(int feature, Menu menu) { return base.onCreatePanelMenu(feature, menu); }
        @Override public boolean onPreparePanel(int feature, View view, Menu menu) { return base.onPreparePanel(feature, view, menu); }
        @Override public boolean onMenuOpened(int feature, Menu menu) { return base.onMenuOpened(feature, menu); }
        @Override public boolean onMenuItemSelected(int feature, MenuItem item) { return base.onMenuItemSelected(feature, item); }
        @Override public void onContentChanged() { base.onContentChanged(); }
        @Override public void onWindowFocusChanged(boolean focused) { base.onWindowFocusChanged(focused); }
        @Override public void onAttachedToWindow() { base.onAttachedToWindow(); }
        @Override public void onDetachedFromWindow() { base.onDetachedFromWindow(); }
        @Override public void onPanelClosed(int feature, Menu menu) { base.onPanelClosed(feature, menu); }
        @Override public boolean onSearchRequested() { return base.onSearchRequested(); }
        @Override public boolean onSearchRequested(SearchEvent event) { return base.onSearchRequested(event); }
        @Override public ActionMode onWindowStartingActionMode(ActionMode.Callback callback) { return base.onWindowStartingActionMode(callback); }
        @Override public ActionMode onWindowStartingActionMode(ActionMode.Callback callback, int type) { return base.onWindowStartingActionMode(callback, type); }
        @Override public void onActionModeStarted(ActionMode mode) { base.onActionModeStarted(mode); }
        @Override public void onActionModeFinished(ActionMode mode) { base.onActionModeFinished(mode); }
        @Override public void onProvideKeyboardShortcuts(List<KeyboardShortcutGroup> data, Menu menu, int device) { base.onProvideKeyboardShortcuts(data, menu, device); }
        @Override public void onPointerCaptureChanged(boolean captured) { base.onPointerCaptureChanged(captured); }
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

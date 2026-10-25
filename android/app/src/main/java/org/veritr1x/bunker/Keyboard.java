package org.veritr1x.bunker;

import android.app.Activity;
import android.content.Intent;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.Window;

/**
 * Keyboard controls in the game, for the Windows emulator and for Android
 * devices with a keyboard. Ctrl+B opens the Bunker, as ⌘B does on a Mac.
 * W A S D or the arrow keys move: they hold a finger on the game's movement
 * stick and push it that way. Shift walks instead of running. On Windows,
 * Bunker.exe reports which keys are really held (HostKeys), and those
 * replace the emulator's own key events for moving.
 */
final class Keyboard {
    // Where the finger goes down, as a share of the window's width and height,
    // and how far it pushes, as a share of the height.
    static final float ANCHOR_X = 0.22f, ANCHOR_Y = 0.70f, REACH = 0.12f;

    // The game takes a touch as its stick only once the finger has rested a
    // moment: a push straight away barely moves the character. After that
    // the push repeats, as a real thumb's small movements do.
    private static final long REST_MS = 200, REPEAT_MS = 100;

    // The emulator sends a held key as a stream of taps: a press and its
    // release in the same millisecond, again every 30 ms after a first gap
    // of about half a second, like typing's key repeat. A release that quick
    // is no human's, so the key counts as held until the stream stops.
    private static final long TAP_MS = 15, FIRST_GAP_MS = 600, STREAM_GAP_MS = 100;

    private final Activity activity;
    private final Window.Callback target;
    private final Key up = new Key(), down = new Key(), left = new Key(), right = new Key(), walk = new Key();
    private long downTime = -1;
    private boolean pushing;
    private float x, y, targetX, targetY;

    private final Runnable push = new Runnable() {
        @Override public void run() {
            if (downTime < 0) return;
            pushing = true;
            x = targetX;
            y = targetY;
            send(MotionEvent.ACTION_MOVE, SystemClock.uptimeMillis());
            root().postDelayed(this, REPEAT_MS);
        }
    };

    /** One key's state, held through the emulator's stream of taps. */
    private final class Key implements Runnable {
        boolean held, streaming, waiting;
        long pressedAt;

        void press(long time) {
            pressedAt = time;
            if (waiting) {
                // The next tap of the emulator's stream: still held.
                root().removeCallbacks(this);
                waiting = false;
                streaming = true;
                return;
            }
            if (!held) {
                held = true;
                move();
            }
        }

        void lift(long time) {
            if (time - pressedAt < TAP_MS) {
                waiting = true;
                root().postDelayed(this, streaming ? STREAM_GAP_MS : FIRST_GAP_MS);
            } else {
                run();
            }
        }

        /** Lets go: the stream stopped, or the key was really lifted. */
        @Override public void run() {
            root().removeCallbacks(this);
            held = streaming = waiting = false;
            move();
        }
    }

    Keyboard(Activity activity, Window.Callback target) {
        this.activity = activity;
        this.target = target;
    }

    /** Handles a key, or returns false to pass it on to the game. */
    boolean handle(KeyEvent event) {
        int action = event.getAction();
        if (action != KeyEvent.ACTION_DOWN && action != KeyEvent.ACTION_UP) return false;
        Key key;
        switch (event.getKeyCode()) {
            case KeyEvent.KEYCODE_B:
                if (!event.isCtrlPressed()) return false;
                if (action == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) openBunker();
                return true;
            case KeyEvent.KEYCODE_W: case KeyEvent.KEYCODE_DPAD_UP: key = up; break;
            case KeyEvent.KEYCODE_S: case KeyEvent.KEYCODE_DPAD_DOWN: key = down; break;
            case KeyEvent.KEYCODE_A: case KeyEvent.KEYCODE_DPAD_LEFT: key = left; break;
            case KeyEvent.KEYCODE_D: case KeyEvent.KEYCODE_DPAD_RIGHT: key = right; break;
            case KeyEvent.KEYCODE_SHIFT_LEFT: case KeyEvent.KEYCODE_SHIFT_RIGHT:
                if (downTime < 0 && !walk.held) return false;
                key = walk;
                break;
            default: return false;
        }
        if (HostKeys.connected()) return true;
        if (action == KeyEvent.ACTION_DOWN) {
            if (event.getRepeatCount() == 0) key.press(event.getEventTime());
        } else {
            key.lift(event.getEventTime());
        }
        return true;
    }

    /** A key that Bunker.exe reports pressed or released on the computer. */
    void host(String name, boolean pressed) {
        Key key;
        switch (name) {
            case "w": case "up": key = up; break;
            case "s": case "down": key = down; break;
            case "a": case "left": key = left; break;
            case "d": case "right": key = right; break;
            case "shift": key = walk; break;
            default: return;
        }
        root().removeCallbacks(key);
        key.streaming = key.waiting = false;
        if (key.held == pressed) return;
        key.held = pressed;
        move();
    }

    /** Lifts the finger, for when the game loses focus with a key held. */
    void release() {
        for (Key key : new Key[] {up, down, left, right, walk}) {
            root().removeCallbacks(key);
            key.held = key.streaming = key.waiting = false;
        }
        move();
    }

    private View root() { return activity.getWindow().getDecorView(); }

    private void openBunker() {
        release();
        activity.startActivity(new Intent(activity, MainActivity.class).putExtra("manage", true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
    }

    private void move() {
        View root = root();
        int width = root.getWidth(), height = root.getHeight();
        if (width == 0 || height == 0) return;
        float dx = (right.held ? 1 : 0) - (left.held ? 1 : 0), dy = (down.held ? 1 : 0) - (up.held ? 1 : 0);
        long now = SystemClock.uptimeMillis();
        if (dx == 0 && dy == 0) {
            root.removeCallbacks(push);
            if (downTime >= 0) send(MotionEvent.ACTION_UP, now);
            downTime = -1;
            pushing = false;
            return;
        }
        float anchorX = width * ANCHOR_X, anchorY = height * ANCHOR_Y;
        float reach = height * REACH * (walk.held ? 0.4f : 1f) / (float) Math.hypot(dx, dy);
        targetX = anchorX + dx * reach;
        targetY = anchorY + dy * reach;
        if (downTime < 0) {
            // The game places its stick where the finger lands.
            downTime = now;
            x = anchorX;
            y = anchorY;
            send(MotionEvent.ACTION_DOWN, now);
            root.postDelayed(push, REST_MS);
        } else if (pushing) {
            x = targetX;
            y = targetY;
            send(MotionEvent.ACTION_MOVE, now);
        }
    }

    private void send(int action, long now) {
        MotionEvent event = MotionEvent.obtain(downTime, now, action, x, y, 0);
        event.setSource(InputDevice.SOURCE_TOUCHSCREEN);
        target.dispatchTouchEvent(event);
        event.recycle();
    }
}

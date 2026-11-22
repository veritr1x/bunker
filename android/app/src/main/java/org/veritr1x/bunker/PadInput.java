package org.veritr1x.bunker;

import android.app.Activity;
import android.content.Context;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.hardware.input.InputManager;
import android.os.SystemClock;
import android.view.*;
import java.util.Locale;

/** One controller owns this window until it disconnects or the window loses focus. */
final class PadInput implements InputManager.InputDeviceListener, Choreographer.FrameCallback {
    boolean sendingTouch;
    private final Window.Callback target;
    private final View root;
    private final InputManager devices;
    private final boolean game;
    private final Runnable toggle, back;
    private final Cursor cursor = new Cursor();
    private final boolean[] contact = new boolean[2];
    private final float[] x = new float[2], y = new float[2];
    private final MotionEvent.PointerProperties[] ids = new MotionEvent.PointerProperties[2];
    private final MotionEvent.PointerCoords[] coords = new MotionEvent.PointerCoords[2];
    private long downAt, anchoredAt, lastFrame;
    private int device = -1, arrows, width, height;
    private float lx, ly, rx, ry, hx, hy, px, py;
    private boolean focused, scheduled, visible, finger;
    private static native void gameAction(int action);

    PadInput(Activity activity, Window.Callback target, boolean game, Runnable toggle, Runnable back) {

        this.target = target;
        this.game = game;
        this.toggle = toggle;
        this.back = back;
        root = activity.getWindow().getDecorView();
        devices = activity.getSystemService(InputManager.class);
        for (int i = 0; i < 2; i++) {
            ids[i] = new MotionEvent.PointerProperties();
            coords[i] = new MotionEvent.PointerCoords();
        }
    }

    void focus(boolean active) {
        if (active == focused) return;
        focused = active;
        if (active) devices.registerInputDeviceListener(this, null);
        else {
            devices.unregisterInputDeviceListener(this);
            reset();
            finger = false;
        }
    }
    public void onInputDeviceAdded(int id) {}
    public void onInputDeviceChanged(int id) { if (id == device) reset(); }
    public void onInputDeviceRemoved(int id) { if (id == device) reset(); }

    private boolean controller(InputEvent e) {
        InputDevice d = e.getDevice();
        return focused && d != null && (d.supportsSource(InputDevice.SOURCE_GAMEPAD) ||
            d.supportsSource(InputDevice.SOURCE_JOYSTICK)) && (device == -1 || device == e.getDeviceId());
    }
    static boolean launcherButton(int key, int vendor, String name) {
        String label = name.toLowerCase(Locale.ROOT);
        boolean sony = vendor == 0x054c || label.contains("dualshock") || label.contains("dualsense");
        return key == (sony ? KeyEvent.KEYCODE_BUTTON_START : KeyEvent.KEYCODE_BUTTON_SELECT);
    }
    private void command(int action) {
        if (game) try { gameAction(action); } catch (UnsatisfiedLinkError unavailable) {
            android.util.Log.w("Bunker", "Controller game actions unavailable", unavailable);
        }
    }
    boolean key(KeyEvent e) {
        if (!controller(e)) return false;
        int key = e.getKeyCode();
        boolean down = e.getAction() == KeyEvent.ACTION_DOWN;
        if (!down && e.getAction() != KeyEvent.ACTION_UP) return false;
        boolean first = down && e.getRepeatCount() == 0;
        InputDevice d = e.getDevice();
        if (launcherButton(key, d.getVendorId(), d.getName())) {
            device = e.getDeviceId();
            if (first) { cancelTouches(); toggle.run(); }
            return true;
        }
        switch (key) {
        case KeyEvent.KEYCODE_BUTTON_A:
            if (!finger && bounds()) {
                showCursor();
                if (first) change(1, true, px, py);
                else if (!down) change(1, false, px, py);
            }
            break;
        case KeyEvent.KEYCODE_BUTTON_B:
            if (first) back.run();
            break;
        case KeyEvent.KEYCODE_BUTTON_Y:
            if (first) command(1);
            break;
        case KeyEvent.KEYCODE_DPAD_LEFT: case KeyEvent.KEYCODE_DPAD_RIGHT:
        case KeyEvent.KEYCODE_DPAD_UP: case KeyEvent.KEYCODE_DPAD_DOWN:
            int mask = 1 << (key - KeyEvent.KEYCODE_DPAD_UP);
            arrows = down ? arrows | mask : arrows & ~mask;
            schedule();
            break;
        default: return false;
        }
        device = e.getDeviceId();
        return true;
    }
    boolean motion(MotionEvent e) {
        if (!e.isFromSource(InputDevice.SOURCE_JOYSTICK) || e.getActionMasked() != MotionEvent.ACTION_MOVE ||
            !controller(e)) return false;
        device = e.getDeviceId();
        lx = e.getAxisValue(MotionEvent.AXIS_X); ly = e.getAxisValue(MotionEvent.AXIS_Y);
        boolean z = e.getDevice().getMotionRange(MotionEvent.AXIS_Z, e.getSource()) != null;
        rx = e.getAxisValue(z ? MotionEvent.AXIS_Z : MotionEvent.AXIS_RX);
        ry = e.getAxisValue(z ? MotionEvent.AXIS_RZ : MotionEvent.AXIS_RY);
        float left = gain(lx, ly, .24f), right = gain(rx, ry, .265f);
        lx *= left; ly *= left; rx *= right; ry *= right;
        hx = e.getAxisValue(MotionEvent.AXIS_HAT_X); hy = e.getAxisValue(MotionEvent.AXIS_HAT_Y);
        schedule();
        return true;
    }
    static float gain(float x, float y, float dead) {
        float r = (float)Math.hypot(x, y);
        return r <= dead ? 0 : (Math.min(1, r) - dead) / ((1 - dead) * r);
    }
    void physicalTouch(MotionEvent e) {
        if (e.getActionMasked() == MotionEvent.ACTION_DOWN) {
            cancelTouches();
            hideCursor();
            finger = true;
        } else if (e.getActionMasked() == MotionEvent.ACTION_UP || e.getActionMasked() == MotionEvent.ACTION_CANCEL) {
            finger = false;
            schedule();
        }
    }
    private void reset() {
        cancelTouches();
        if (device >= 0) command(0);
        Choreographer.getInstance().removeFrameCallback(this);
        scheduled = false; lastFrame = 0;
        arrows = 0; lx = ly = rx = ry = hx = hy = 0; device = -1;
        hideCursor();
    }
    private void cancelTouches() {
        if (contact[0] || contact[1]) send(MotionEvent.ACTION_CANCEL, -1);
        contact[0] = contact[1] = false;
    }
    private boolean bounds() {
        int w = root.getWidth(), h = root.getHeight();
        if (w <= 0 || h <= 0) return false;
        if (w != width || h != height) {
            cancelTouches();
            px = width == 0 ? w * .5f : px * w / width;
            py = height == 0 ? h * .5f : py * h / height;
            width = w; height = h;
            if (visible) placeCursor();
        }
        return true;
    }
    private void schedule() {
        if (focused && !scheduled) {
            scheduled = true;
            Choreographer.getInstance().postFrameCallback(this);
        }
    }
    @Override public void doFrame(long time) {
        scheduled = false;
        if (!focused || finger || !bounds()) { lastFrame = 0; return; }
        float dt = lastFrame == 0 ? 1f/60 : Math.min(.05f, (time - lastFrame) * 1e-9f);
        lastFrame = time;
        if (rx != 0 || ry != 0) {
            px = Math.max(0, Math.min(width - 1, px + rx * height * dt));
            py = Math.max(0, Math.min(height - 1, py + ry * height * dt));
            showCursor();
            if (contact[1]) drag(1, px, py);
        }
        float dx = ((arrows & 8) != 0 ? 1 : 0) - ((arrows & 4) != 0 ? 1 : 0);
        float dy = ((arrows & 2) != 0 ? 1 : 0) - ((arrows & 1) != 0 ? 1 : 0);
        if (dx == 0 && dy == 0) { dx = hx; dy = hy; }
        if (dx == 0 && dy == 0) { dx = lx; dy = ly; }
        float scale = Math.max(1, (float)Math.hypot(dx, dy));
        dx /= scale; dy /= scale;
        if (!game) {
            if (dx != 0 || dy != 0) scroll(dx * dt * 14, dy * dt * 14);
        } else if (dx == 0 && dy == 0) change(0, false, x[0], y[0]);
        else {
            float ax = width * Keyboard.ANCHOR_X, ay = height * Keyboard.ANCHOR_Y;
            if (!contact[0]) {
                anchoredAt = time;
                change(0, true, ax, ay);
            } else if (time - anchoredAt >= 200_000_000L) {
                drag(0, ax + dx * height * .15f, ay + dy * height * .15f);
            }
        }
        if (rx != 0 || ry != 0 || dx != 0 || dy != 0) schedule();
        else lastFrame = 0;
    }
    private void scroll(float dx, float dy) {
        MotionEvent.PointerCoords at = coords[0];
        at.clear(); at.x = px; at.y = py;
        at.setAxisValue(MotionEvent.AXIS_HSCROLL, dx);
        at.setAxisValue(MotionEvent.AXIS_VSCROLL, -dy);
        ids[0].id = 0; ids[0].toolType = MotionEvent.TOOL_TYPE_MOUSE;
        long now = SystemClock.uptimeMillis();
        MotionEvent e = MotionEvent.obtain(now, now, MotionEvent.ACTION_SCROLL, 1, ids, coords,
            0, 0, 1, 1, 0, 0, InputDevice.SOURCE_MOUSE, 0);
        try { target.dispatchGenericMotionEvent(e); } finally { e.recycle(); }
    }
    private void change(int slot, boolean down, float nx, float ny) {
        if (down == contact[slot]) return;
        boolean other = contact[1 - slot];
        if (down && !other) downAt = SystemClock.uptimeMillis();
        contact[slot] = true; x[slot] = nx; y[slot] = ny;
        int action = down ? (other ? MotionEvent.ACTION_POINTER_DOWN : MotionEvent.ACTION_DOWN)
                          : (other ? MotionEvent.ACTION_POINTER_UP : MotionEvent.ACTION_UP);
        send(action, slot);
        contact[slot] = down;
    }
    private void drag(int slot, float nx, float ny) {
        x[slot] = nx; y[slot] = ny;
        send(MotionEvent.ACTION_MOVE, -1);
    }
    private void send(int action, int changed) {
        int n = 0;
        for (int i = 0; i < 2; ++i) if (contact[i]) {
            if (i == changed && (action == MotionEvent.ACTION_POINTER_UP || action == MotionEvent.ACTION_POINTER_DOWN))
                action |= n << MotionEvent.ACTION_POINTER_INDEX_SHIFT;
            ids[n].id = i; ids[n].toolType = MotionEvent.TOOL_TYPE_FINGER;
            coords[n].clear(); coords[n].x = x[i]; coords[n].y = y[i];
            coords[n].pressure = 1; coords[n].size = .1f; n++;
        }
        MotionEvent event = MotionEvent.obtain(downAt, SystemClock.uptimeMillis(), action, n, ids, coords,
            0, 0, 1, 1, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
        sendingTouch = true;
        try { target.dispatchTouchEvent(event); } finally { sendingTouch = false; event.recycle(); }
    }
    private void placeCursor() {
        int radius = Math.max(6, Math.round(root.getResources().getDisplayMetrics().density * 8));
        cursor.setBounds((int)px-radius, (int)py-radius, (int)px+radius, (int)py+radius);
    }
    private void showCursor() {
        placeCursor();
        if (!visible) { root.getOverlay().add(cursor); visible = true; }
    }
    private void hideCursor() {
        if (visible) { root.getOverlay().remove(cursor); visible = false; }
    }
    private static final class Cursor extends Drawable {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        @Override public void draw(Canvas c) {
            Rect b = getBounds(); float r = b.width() * .37f;
            paint.setStyle(Paint.Style.STROKE); paint.setColor(Color.BLACK); paint.setStrokeWidth(r * .60f);
            c.drawCircle(b.exactCenterX(), b.exactCenterY(), r, paint);
            paint.setColor(Color.WHITE); paint.setStrokeWidth(r * .28f);
            c.drawCircle(b.exactCenterX(), b.exactCenterY(), r, paint);
        }
        @Override public void setAlpha(int alpha) {}
        @Override public void setColorFilter(ColorFilter filter) {}
        @Override public int getOpacity() { return android.graphics.PixelFormat.TRANSLUCENT; }
    }
}

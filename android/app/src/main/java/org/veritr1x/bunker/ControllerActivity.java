package org.veritr1x.bunker;

import android.app.Activity;
import android.view.KeyEvent;
import android.view.MotionEvent;

/** Native launcher, Pod Programs and Archive use their usual window and Back handling. */
abstract class ControllerActivity extends Activity {
    private PadInput pad;
    private PadInput pad() {
        if (pad == null) pad = new PadInput(this, getWindow(), this, false, this::controllerToggle, this::onBackPressed);
        return pad;
    }
    protected void controllerToggle() { onBackPressed(); }
    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        pad().focus(focused);
    }
    @Override public boolean dispatchKeyEvent(KeyEvent e) {
        return pad().key(e) || super.dispatchKeyEvent(e);
    }
    @Override public boolean dispatchGenericMotionEvent(MotionEvent e) {
        return pad().motion(e) || super.dispatchGenericMotionEvent(e);
    }
    @Override public boolean dispatchTouchEvent(MotionEvent e) {
        if (!pad().sendingTouch) pad.physicalTouch(e);
        return super.dispatchTouchEvent(e);
    }
    @Override protected void onDestroy() {
        if (pad != null) pad.focus(false);
        super.onDestroy();
    }
}

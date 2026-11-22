package org.veritr1x.bunker;

import android.view.KeyEvent;
import junit.framework.TestCase;

public final class ControllerMappingTest extends TestCase {
    public void testLauncherButtonByControllerFamily() {
        int select = KeyEvent.KEYCODE_BUTTON_SELECT, start = KeyEvent.KEYCODE_BUTTON_START;
        assertTrue(PadInput.launcherButton(select, 0x045e, "Xbox Wireless Controller"));
        assertFalse(PadInput.launcherButton(start, 0x045e, "Xbox Wireless Controller"));
        assertTrue(PadInput.launcherButton(start, 0x054c, "Wireless Controller"));
        assertFalse(PadInput.launcherButton(select, 0x054c, "Wireless Controller"));
        assertTrue(PadInput.launcherButton(start, 0, "DualSense Wireless Controller"));
        assertFalse(PadInput.launcherButton(KeyEvent.KEYCODE_BUTTON_MODE, 0x045e, "Xbox"));
    }

    public void testStickDeadZoneAndDiagonalSpeed() {
        assertEquals(0f, PadInput.gain(.1f, .1f, .24f), 0f);
        assertEquals(1f, PadInput.gain(1, 0, .24f), .0001f);
        float diagonal = PadInput.gain(1, 1, .24f);
        assertEquals(1.0, Math.hypot(diagonal, diagonal), .0001);
        assertTrue(PadInput.gain(.5f, 0, .24f) > 0);
        assertTrue(PadInput.gain(.5f, 0, .24f) < 1);
    }
}

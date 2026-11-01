package org.veritr1x.bunker;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/**
 * After an update, the Original calendar's game data is brought up to the new
 * build before the server starts (android_runtime.update_calendar), once per
 * version; before, that waited until Pod Programs opened. Python starts only
 * when calendar.json is there and calendar.updated names another version.
 * iOS uses the same rule (LunarTools.m LTCalendarNeedsUpdate).
 */
final class CalendarUpdate {
    private CalendarUpdate() {}

    /** True when the calendar is on in data (the saves folder) and was not yet updated for version. */
    static boolean needed(File data, String version) {
        if (!new File(data, "calendar.json").isFile()) return false;
        try {
            return !new String(Files.readAllBytes(new File(data, "calendar.updated").toPath()), StandardCharsets.UTF_8).trim().equals(version);
        } catch (Exception missing) {
            return true;
        }
    }
}

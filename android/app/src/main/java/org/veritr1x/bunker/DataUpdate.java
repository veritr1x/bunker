package org.veritr1x.bunker;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/**
 * After an update, the game data is brought up to the new build before the
 * server starts (android_runtime.update_data): the Original calendar's, or the
 * Pod Programs preset's, so fixes reach the game without opening Pod Programs.
 * It runs once per version. Python starts only when the calendar is on or a
 * preset made the master data, and data.updated names another version.
 * iOS uses the same rule (LunarTools.m LTDataNeedsUpdate).
 */
final class DataUpdate {
    private DataUpdate() {}

    /** True when data (the saves folder) or tools (Pod Programs' folder) has game data not yet updated for version. */
    static boolean needed(File data, File tools, String version) {
        if (!new File(data, "calendar.json").isFile() && !new File(tools, "patcher/active.json").isFile()) return false;
        try {
            return !new String(Files.readAllBytes(new File(data, "data.updated").toPath()), StandardCharsets.UTF_8).trim().equals(version);
        } catch (Exception missing) {
            return true;
        }
    }
}

package org.veritr1x.bunker;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Pod Programs' timeline links a summon or an event to its Archive page with
 * "bunker-archive:/schedule/summon/46". The Archive is another screen with its
 * own server, so the link opens it at that page (ToolsActivity, ArchiveActivity).
 * Only those pages open; anything else is ignored. iOS uses the same rule
 * (LunarTools.m kArchiveLink, android/tools/test_archive_links.py).
 */
final class ArchiveLinks {
    private static final Pattern LINK = Pattern.compile("^bunker-archive:(/schedule/(?:summon|event)/[0-9]+)$");

    private ArchiveLinks() {}

    /** The Archive path a link opens, or null. */
    static String path(String url) {
        if (url == null) return null;
        Matcher m = LINK.matcher(url);
        return m.matches() ? m.group(1) : null;
    }
}

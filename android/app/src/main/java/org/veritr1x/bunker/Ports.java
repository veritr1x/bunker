package org.veritr1x.bunker;

import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Bundle;

/**
 * The loopback ports the game uses: 8003 (game), 8080 (assets) and 3000
 * (accounts), all moved by the build's offset when another app on the phone
 * needs those ports (scripts/build.py --port-offset). The packager writes the
 * offset into the manifest, since the game has the ports built in.
 */
final class Ports {
    private Ports() {}

    static int offset(Context c) {
        try {
            Bundle meta = c.getPackageManager().getApplicationInfo(c.getPackageName(), PackageManager.GET_META_DATA).metaData;
            return meta == null ? 0 : meta.getInt("org.veritr1x.bunker.PORT_OFFSET", 0);
        } catch (PackageManager.NameNotFoundException e) {
            return 0;
        }
    }

    static int game(Context c) { return 8003 + offset(c); }
    static int assets(Context c) { return 8080 + offset(c); }
    static int accounts(Context c) { return 3000 + offset(c); }
}

package org.veritr1x.bunker;

import android.test.InstrumentationTestCase;
import org.json.JSONObject;

/** What the launcher offers for a release: the version rule and the update decision. */
public final class UpdaterTest extends InstrumentationTestCase {
    public void testNewer() {
        assertTrue(Updater.newer("1.0.1","1.0.0"));
        assertTrue(Updater.newer("1.0.1","1.0.0+dev.abc1234"));
        assertFalse(Updater.newer("1.0.0","1.0.0+dev.abc1234"));
        assertFalse(Updater.newer("1.0.0","1.0.0"));
        assertFalse(Updater.newer("0.9.9","1.0.0"));
        assertTrue(Updater.newer("1.10.0","1.9.9"));
        assertFalse(Updater.newer("garbage","1.0.0"));
        assertTrue(Updater.newer("1.0.1","dev"));
    }

    private static JSONObject update(String version,int gamePatch) throws Exception {
        return new JSONObject("{\"version\":\""+version+"\",\"gamePatch\":"+gamePatch+",\"assets\":{\"android\":{\"name\":\"bunker-android-"+version+".zip\",\"size\":10,\"sha256\":\"ab\"}}}");
    }
    private static JSONObject build(int gamePatch) throws Exception {
        return new JSONObject("{\"version\":\"1.0.0\",\"gamePatch\":"+gamePatch+",\"portOffset\":0,\"gameDex\":3}");
    }

    public void testOffers() throws Exception {
        assertEquals(Updater.Offer.NONE,Updater.offer(update("1.0.0",1),"1.0.0",build(1),true));
        assertEquals(Updater.Offer.UPDATE,Updater.offer(update("1.0.1",1),"1.0.0",build(1),true));
        assertEquals(Updater.Offer.WEB_BUILDER,Updater.offer(update("1.0.1",2),"1.0.0",build(1),true));
        assertEquals(Updater.Offer.WEB_BUILDER,Updater.offer(update("1.0.1",1),"0.1.0",null,true));
        assertEquals(Updater.Offer.OWN_KEY,Updater.offer(update("1.0.1",1),"1.0.0",build(1),false));
    }

    public void testOneUpdateAtATime() {
        Updater.finish();
        assertTrue(Updater.begin());
        assertFalse(Updater.begin());
        Updater.finish();
        assertTrue(Updater.begin());
        Updater.finish();
    }

    public void testTestReleasesOnlyInDevBuilds() {
        assertTrue(Updater.testReleasesAllowed("1.0.1+dev.abc1234"));
        assertTrue(Updater.testReleasesAllowed("1.0.1+dev"));
        assertFalse(Updater.testReleasesAllowed("1.0.1"));
    }

    public void testPlayerFacingErrors() {
        String offline="Can't reach the update server. Check the connection and try again.";
        assertEquals(offline,Updater.explain(new java.net.UnknownHostException("github.com")));
        assertEquals(offline,Updater.explain(new java.net.ConnectException("refused")));
        assertEquals("The connection timed out. Try again.",Updater.explain(new java.net.SocketTimeoutException("Read timed out")));
        assertEquals("The update files aren't available (HTTP 404). Try again later.",Updater.explain(new Updater.HttpError(404)));
        assertEquals("Update cancelled.",Updater.explain(new java.io.IOException("Update cancelled.")));
    }

    public void testCancelOnlyWhileDownloading() {
        Updater.finish();
        assertTrue(Updater.begin());
        Updater.stage(Updater.Stage.DOWNLOADING);
        assertTrue(Updater.cancellable());
        Updater.stage(Updater.Stage.BUILDING);
        assertFalse(Updater.cancellable());
        Updater.finish();
        assertFalse(Updater.cancellable());
    }
}

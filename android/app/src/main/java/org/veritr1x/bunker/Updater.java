package org.veritr1x.bunker;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Handler;
import android.os.Looper;
import android.os.StatFs;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Bunker's updates. When the launcher opens and the device is online, check()
 * asks GitHub for the latest release once; apply() downloads the release's
 * Android bundle (Bunker's own files only), rebuilds this app around the game
 * files already in it (bunker_update.py), signs it with the public Bunker key
 * and hands it to Android's installer, which asks the player to confirm.
 */
final class Updater {
    static final String LATEST="https://api.github.com/repos/veritr1x/bunker/releases/latest";
    static final String WEB_BUILDER="https://veritr1x.github.io/bunker/";
    static final String INSTALL_RESULT="org.veritr1x.bunker.UPDATE_INSTALLED";
    private static final long SPACE=350L<<20;
    private static final String PREFS="lunar_update";

    enum Offer { NONE, UPDATE, WEB_BUILDER, OWN_KEY }

    /** A newer release: its version, notes page and update.json, and what can be done here. */
    static final class Release {
        String version,notes,bundleUrl;JSONObject update;Offer offer;
    }
    interface Found { void found(Release release); }
    interface Reporter { void report(String message); }

    private Updater() {}

    // The update outlives the launcher screen (rotation, unfolding, split screen), so its state
    // lives here, once per process; MainActivity redraws from it (listener).
    static volatile Release current;
    static volatile String status="";
    static volatile boolean statusFailed;
    static volatile Runnable listener;
    private static boolean inProgress,checked;
    enum Stage { DOWNLOADING, BUILDING, INSTALLING }
    private static Stage stage=Stage.DOWNLOADING;
    static synchronized boolean begin() { if(inProgress)return false;inProgress=true;stage=Stage.DOWNLOADING;return true; }
    static synchronized void finish() { inProgress=false; }
    static synchronized void stage(Stage s) { stage=s; }
    /** Cancel works only while downloading; after that the build and the installer finish on their own. */
    static synchronized boolean cancellable() { return inProgress&&stage==Stage.DOWNLOADING; }

    /** An HTTP reply other than 200. */
    static final class HttpError extends IOException {
        final int code;
        HttpError(int code) { super("HTTP "+code);this.code=code; }
    }

    /** A message for the player: network failures in plain words, everything else as it is. */
    static String explain(Throwable e) {
        if(e instanceof java.net.UnknownHostException||e instanceof java.net.ConnectException||e instanceof java.net.NoRouteToHostException)
            return "Can't reach the update server. Check the connection and try again.";
        if(e instanceof java.net.SocketTimeoutException)return "The connection timed out. Try again.";
        if(e instanceof HttpError)return "The update files aren't available (HTTP "+((HttpError)e).code+"). Try again later.";
        if(e instanceof javax.net.ssl.SSLException)return "The secure connection to the update server failed. Try again.";
        String message=e.getMessage()==null?e.toString():e.getMessage();
        // Python errors arrive as "RuntimeError: <message>".
        return message.replaceFirst("^[A-Za-z.]*Error: ","");
    }
    static synchronized boolean updating() { return inProgress; }
    private static void show(String text,boolean failed) {
        status=text;statusFailed=failed;
        new Handler(Looper.getMainLooper()).post(()->{Runnable l=listener;if(l!=null)l.run();});
    }
    /** Checks again (the player turned "Check for updates" back on). */
    static void recheck(Context c,Found found) { synchronized(Updater.class){checked=false;} check(c,found); }
    /** Test releases (update-test.json) are honoured only by development builds. */
    static boolean testReleasesAllowed(String version) { return version.contains("+dev"); }

    /** Whether release candidate is offered to a build of version current (1.0.0 is not offered to 1.0.0+dev). */
    static boolean newer(String candidate,String current) {
        int[] a=base(candidate),b=base(current);
        if(a==null)return false;
        if(b==null)return true;
        for(int i=0;i<3;i++)if(a[i]!=b[i])return a[i]>b[i];
        return false;
    }
    private static int[] base(String version) {
        String[] parts=version.split("\\+",2)[0].split("\\.");
        if(parts.length!=3)return null;
        int[] out=new int[3];
        try{for(int i=0;i<3;i++)out[i]=Integer.parseInt(parts[i]);}catch(NumberFormatException e){return null;}
        return out;
    }

    /** What the launcher offers for update.json: installed is this app's build.json (null before 1.0.0). */
    static Offer offer(JSONObject update,String current,JSONObject installed,boolean bunkerKey) {
        if(!newer(update.optString("version"),current))return Offer.NONE;
        if(installed==null||installed.optInt("gamePatch",-1)!=update.optInt("gamePatch",-2))return Offer.WEB_BUILDER;
        if(!bunkerKey)return Offer.OWN_KEY;
        return Offer.UPDATE;
    }

    static boolean enabled(Context c) { return c.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getBoolean("check",true); }
    static void enabled(Context c,boolean on) { c.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putBoolean("check",on).apply(); }

    /** This app's build.json, or null for builds made before 1.0.0. */
    static JSONObject installedBuild(Context c) {
        try(InputStream in=c.getAssets().open("lunar/build.json")){return new JSONObject(new String(read(in),StandardCharsets.UTF_8));}
        catch(Exception e){return null;}
    }

    /** Whether this app is signed with the public Bunker key (only those builds can update themselves). */
    static boolean bunkerKey(Context c) {
        try(InputStream in=c.getAssets().open("lunar/signing/bunker-cert.der")) {
            byte[] bunker=sha256(read(in));
            PackageInfo info=c.getPackageManager().getPackageInfo(c.getPackageName(),PackageManager.GET_SIGNING_CERTIFICATES);
            Signature[] signers=info.signingInfo.getApkContentsSigners();
            for(Signature s:signers)if(MessageDigest.isEqual(sha256(s.toByteArray()),bunker))return true;
        } catch(Exception ignored) {}
        return false;
    }

    /** Looks for a newer release in the background; calls found on the main thread only if there is one. */
    static void check(Context context,Found found) {
        Context c=context.getApplicationContext();
        synchronized(Updater.class) {
            if(checked)return;
            checked=true;
            // An update the system stopped part-way (or one whose install replaced this process) leaves files behind.
            if(!inProgress)FilesStore.delete(new File(c.getCacheDir(),"update"));
        }
        if(!enabled(c))return;
        new Thread(()->{
            try {
                JSONObject release=new JSONObject(get(latestUrl(c)));
                String tag=release.getString("tag_name");
                String version=tag.startsWith("v")?tag.substring(1):tag;
                if(!newer(version,BuildConfig.BUNKER_VERSION))return;
                JSONArray assets=release.getJSONArray("assets");
                String updateUrl=null,bundleName=null,bundleUrl=null;
                for(int i=0;i<assets.length();i++)if("update.json".equals(assets.getJSONObject(i).optString("name")))
                    updateUrl=assets.getJSONObject(i).getString("browser_download_url");
                if(updateUrl==null)return;
                JSONObject update=new JSONObject(get(updateUrl));
                bundleName=update.getJSONObject("assets").getJSONObject("android").getString("name");
                for(int i=0;i<assets.length();i++)if(bundleName.equals(assets.getJSONObject(i).optString("name")))
                    bundleUrl=assets.getJSONObject(i).getString("browser_download_url");
                Release r=new Release();r.version=version;r.notes=release.optString("html_url",WEB_BUILDER);r.update=update;r.bundleUrl=bundleUrl;
                r.offer=bundleUrl==null?Offer.WEB_BUILDER:offer(update,BuildConfig.BUNKER_VERSION,installedBuild(c),bunkerKey(c));
                if(r.offer!=Offer.NONE){current=r;new Handler(Looper.getMainLooper()).post(()->found.found(r));}
            } catch(Exception ignored) {
                // Offline, rate-limited or an unexpected reply: say nothing until the next time the launcher opens.
            }
        },"update-check").start();
    }

    /**
     * For testing an update before a release exists: in a development build (+dev),
     * files/tools/update-test.json ({"latest": "http://10.0.2.2:8000/latest.json"})
     * replaces GitHub. The file is in the app's private storage (adb as root).
     */
    private static String latestUrl(Context c) {
        File test=new File(new File(c.getFilesDir(),"tools"),"update-test.json");
        try{if(testReleasesAllowed(BuildConfig.BUNKER_VERSION)&&test.isFile())return new JSONObject(new String(read(new FileInputStream(test)),StandardCharsets.UTF_8)).getString("latest");}
        catch(Exception ignored){}
        return LATEST;
    }

    /**
     * Downloads, builds and installs the release on a background thread. stopGame
     */
    static volatile boolean cancelled;
    // Lunar Tear was running when the update stopped it: started again if the install doesn't happen.
    private static volatile boolean restartServer;
    private static volatile Context appContext;

    /**
     * Downloads, builds and installs the release on a background thread (one at a time).
     * stopGame stops Lunar Tear and Pod Programs; the installer opens only once both
     * have stopped. Progress and failures go to status (and the listener); a failure
     * leaves the installed app as it was.
     */
    static boolean apply(Activity activity,Release r,Runnable stopGame) {
        if(!begin())return false;
        cancelled=false;
        Reporter report=text->show(text,false);
        Context app=activity.getApplicationContext();
        appContext=app;restartServer=false;
        Thread t=new Thread(()->{
            File work=new File(activity.getCacheDir(),"update");
            try {
                FilesStore.delete(work);FilesStore.mkdir(work);
                if(new StatFs(activity.getCacheDir().getPath()).getAvailableBytes()<SPACE)
                    throw new IOException("Updating needs about 350 MB free. Free some space and try again.");
                File bundle=new File(work,"bundle.zip");
                download(r.bundleUrl,bundle,r.update.getJSONObject("assets").getJSONObject("android").optLong("size",-1),report);
                if(cancelled)throw new IOException("Update cancelled.");
                stage(Stage.BUILDING);
                File key=new File(work,"bunker-key.pem"),cert=new File(work,"bunker-cert.der");
                copyAsset(activity,"lunar/signing/bunker-key.pem",key);copyAsset(activity,"lunar/signing/bunker-cert.der",cert);
                if(!Python.isStarted())Python.start(new AndroidPlatform(activity));
                String apk=Python.getInstance().getModule("bunker_update").callAttr("build_android",activity.getPackageCodePath(),bundle.getAbsolutePath(),
                    r.update.getJSONObject("assets").getJSONObject("android").getString("sha256"),work.getAbsolutePath(),key.getAbsolutePath(),cert.getAbsolutePath(),report).toString();
                bundle.delete();
                if(cancelled)throw new IOException("Update cancelled.");
                report.report("Stopping Lunar Tear and Pod Programs…");
                restartServer=new JSONObject(NativeBridge.status()).optString("state").equals("running");
                new Handler(Looper.getMainLooper()).post(stopGame);
                // Pod Programs may be finishing an edit (up to two minutes); never install over it.
                for(int i=0;i<600&&!stopped();i++)Thread.sleep(250);
                if(!stopped())throw new IOException("Pod Programs is still saving. Close it, wait a moment and try again.");
                report.report("Opening the installer…");
                stage(Stage.INSTALLING);
                install(activity,new File(apk));
                // The installer's answer arrives in MainActivity (installResult), which ends the update.
            } catch(Throwable e) {
                FilesStore.delete(work);
                finish();
                restartIfStopped();
                show(explain(e),true);
            }
        },"update");
        t.start();
        return true;
    }

    /** Starts Lunar Tear again when the update stopped it but nothing was installed. */
    private static void restartIfStopped() {
        Context c=appContext;
        if(!restartServer||c==null)return;
        restartServer=false;
        new Handler(Looper.getMainLooper()).post(()->c.startForegroundService(new Intent(c,ServerService.class).setAction(ServerService.START)));
    }

    /** Lunar Tear is stopped and Pod Programs is closed (both run in this process). */
    private static boolean stopped() {
        try{return new JSONObject(NativeBridge.status()).optString("state").matches("stopped|error|")&&ToolsRuntime.url.isEmpty();}
        catch(Exception e){return false;}
    }

    private static void install(Activity activity,File apk) throws IOException {
        PackageInstaller installer=activity.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams params=new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(activity.getPackageName());
        int id=installer.createSession(params);
        try(PackageInstaller.Session session=installer.openSession(id)) {
            try {
            // The written file must be closed before commit, and only once (a second close fails with EBADF).
            try(InputStream in=new FileInputStream(apk);OutputStream out=session.openWrite("bunker.apk",0,apk.length())) {
                byte[] buffer=new byte[1<<20];int n;while((n=in.read(buffer))>0)out.write(buffer,0,n);
                session.fsync(out);
            }
            // The result comes back to the launcher (MainActivity.onNewIntent), which asks the player to confirm.
            Intent result=new Intent(activity,MainActivity.class).setAction(INSTALL_RESULT).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
            session.commit(PendingIntent.getActivity(activity,id,result,PendingIntent.FLAG_MUTABLE|PendingIntent.FLAG_UPDATE_CURRENT).getIntentSender());
            } catch(IOException|RuntimeException e) {
                session.abandon();  // nothing half-written is left with the installer
                throw e;
            }
        }
    }

    /** Handles the installer's reply; returns a message to show, or null. */
    static String installResult(Activity activity,Intent intent) {
        int status=intent.getIntExtra(PackageInstaller.EXTRA_STATUS,PackageInstaller.STATUS_FAILURE);
        if(status==PackageInstaller.STATUS_PENDING_USER_ACTION) {
            @SuppressWarnings("deprecation") Intent confirm=intent.getParcelableExtra(Intent.EXTRA_INTENT);  // The typed form needs Android 13.
            if(confirm!=null){activity.startActivity(confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));return null;}
        }
        FilesStore.delete(new File(activity.getCacheDir(),"update"));
        finish();
        if(status==PackageInstaller.STATUS_SUCCESS)return null;
        restartIfStopped();
        String message=intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
        return status==PackageInstaller.STATUS_FAILURE_ABORTED?"Update cancelled.":"The update could not be installed"+(message==null?".":": "+message);
    }

    private static void download(String url,File target,long size,Reporter report) throws IOException {
        HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();
        c.setConnectTimeout(15000);c.setReadTimeout(30000);
        if(c.getResponseCode()!=200){int code=c.getResponseCode();c.disconnect();throw new HttpError(code);}
        try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(target)) {
            long total=size>0?size:c.getContentLengthLong(),done=0;int last=-1;
            byte[] buffer=new byte[1<<16];int n;
            while((n=in.read(buffer))>0) {
                if(cancelled)return;
                out.write(buffer,0,n);done+=n;
                int percent=total>0?(int)(done*100/total):-1;
                if(percent!=last){last=percent;report.report(percent>=0?"Downloading "+percent+"%":"Downloading…");}
            }
        } finally {c.disconnect();}
    }

    private static String get(String url) throws IOException {
        HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();
        c.setConnectTimeout(5000);c.setReadTimeout(5000);
        c.setRequestProperty("Accept","application/vnd.github+json");
        if(c.getResponseCode()!=200){int code=c.getResponseCode();c.disconnect();throw new HttpError(code);}
        try(InputStream in=c.getInputStream()) {
            return new String(read(in),StandardCharsets.UTF_8);
        } finally {c.disconnect();}
    }

    private static void copyAsset(Context c,String name,File target) throws IOException {
        try(InputStream in=c.getAssets().open(name);OutputStream out=new FileOutputStream(target)){out.write(read(in));}
    }
    private static byte[] read(InputStream in) throws IOException {
        try(InputStream source=in){ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[65536];int n;while((n=source.read(b))>0)out.write(b,0,n);return out.toByteArray();}
    }
    private static byte[] sha256(byte[] data) throws Exception { return MessageDigest.getInstance("SHA-256").digest(data); }
}

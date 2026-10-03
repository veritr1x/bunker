package org.lunartear.companion;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.net.Uri;
import android.os.*;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ServerService extends Service {
    static final String START="start", STOP="stop", ASSETS="assets", MASTER="master", BACKUP="backup", TOOLS="tools", CLOSE_TOOLS="close_tools", SAVE="save", ARCHIVE="archive", LINK="link";
    static volatile boolean running=false, busy=false, tools=false;
    // Import progress, 0-1000, or -1 when there is no measured copy in progress.
    static volatile int permille=-1;
    static volatile String state="Server stopped", detail="Import your game files to get started.";
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final Handler main=new Handler(Looper.getMainLooper());
    private volatile boolean cancelled=false;
    private PowerManager.WakeLock wake;
    private long lastNotification;
    private final Runnable monitor=new Runnable() { public void run() {
        if(!running) return;
        try {
            JSONObject s=new JSONObject(NativeBridge.status());
            if(s.getString("state").equals("error")) {
                running=false; state="Server stopped"; detail=s.optString("error"); finishForeground(); return;
            }
        } catch(Exception ignored) {}
        main.postDelayed(this,2000);
    }};
    @Override public void onCreate() {
        super.onCreate();
        NotificationChannel channel=new NotificationChannel("server","Local game server",NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Server status and Stop control while you play.");
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
        wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"lunartear:server");
        wake.setReferenceCounted(false);
    }
    private Notification notification() {
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class).putExtra("manage",true).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,ServerService.class).setAction(STOP),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder builder=new Notification.Builder(this,"server").setSmallIcon(Look.moon()).setContentTitle("Lunar Tear · "+state)
            .setContentText(detail).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(null,busy?"Cancel":"Stop server",stop).build());
        if(busy&&permille>=0)builder.setProgress(1000,permille,false).setStyle(new Notification.BigTextStyle().bigText(detail));
        return builder.build();
    }
    private void update(String message) {
        detail=message;
        long now=SystemClock.elapsedRealtime();
        if(now-lastNotification>1000) { lastNotification=now; getSystemService(NotificationManager.class).notify(1,notification()); }
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        if(intent==null) { stopSelf(); return START_NOT_STICKY; }
        String action=intent.getAction();
        if(TOOLS.equals(action)) {
            if(tools||busy)return START_NOT_STICKY;
            tools=true;busy=true;cancelled=false;state="Preparing tools";detail="Stopping the game…";
            if(Build.VERSION.SDK_INT>=34)startForeground(1,notification(),ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            else startForeground(1,notification());
            wake.acquire(12*60*60*1000L);
            main.removeCallbacks(monitor);
            worker.execute(()->{
                try {
                    NativeBridge.stop();running=false;
                    String error=NativeBridge.prepareBackup(FilesStore.data(this).getAbsolutePath());
                    if(!error.isEmpty())throw new IllegalStateException(error);
                    closeGame();
                    ToolsRuntime.start(this,this::update);
                    if(cancelled){ToolsRuntime.stop();tools=false;state="Server stopped";}
                    else {state="Tools ready";detail="Close Tools to return to the game.";}
                } catch(Exception|LinkageError error) {
                    tools=false;state="Needs attention";detail=error.getMessage()==null?error.toString():error.getMessage();
                    android.util.Log.e("LunarTear","Tools startup failed",error);
                } finally {
                    busy=false;
                    if(tools)getSystemService(NotificationManager.class).notify(1,notification());else finishForeground();
                }
            });
            return START_NOT_STICKY;
        }
        if(STOP.equals(action)||CLOSE_TOOLS.equals(action)) {
            cancelled=true;
            state="Stopping"; detail="Finishing the current operation and saving progress…";
            busy=true;
            worker.execute(()->{
                try {ToolsRuntime.stop();tools=false;NativeBridge.stop();running=false;state="Server stopped";detail="Your saves are stored on this phone.";}
                catch(Exception error){state="Needs attention";detail=error.getMessage();}
                finally {busy=false;if(!tools)finishForeground();}
            });
            return START_NOT_STICKY;
        }
        if(busy||running||tools) return START_NOT_STICKY;
        busy=true; cancelled=false; permille=-1;
        state=START.equals(action)?"Starting server":BACKUP.equals(action)?"Exporting saves":SAVE.equals(action)?"Importing save":"Importing files";
        detail=START.equals(action)?"Loading game data…":"Keep the source files available until this finishes.";
        if(Build.VERSION.SDK_INT>=34) startForeground(1,notification(),ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(1,notification());
        wake.acquire(12*60*60*1000L);
        Uri uri=intent.getData();
        worker.execute(()->{
            try {
                FilesStore.recover(this);
                if(START.equals(action)) {
                    FilesStore.ensureBootstrap(this);
                    String error=NativeBridge.start(FilesStore.data(this).getAbsolutePath(),FilesStore.root(this).getAbsolutePath());
                    if(error==null||!error.isEmpty()) throw new IllegalStateException(error==null?"Native server did not respond":error);
                    if(cancelled) { NativeBridge.stop(); throw new InterruptedException("Start cancelled"); }
                    running=true;state="Server running";detail="Ready to play · server is running on this phone";
                    main.post(monitor);
                } else {
                    FilesStore.Progress progress=new FilesStore.Progress(){
                        public void update(String text){ServerService.this.update(text);}
                        public boolean cancelled(){return cancelled;}
                        public void fraction(int value){permille=value;}
                    };
                    if(ASSETS.equals(action)) FilesStore.importAssets(this,uri,progress);
                    else if(ARCHIVE.equals(action)) FilesStore.importArchive(this,uri,progress);
                    else if(LINK.equals(action)) FilesStore.linkAssets(this,uri,progress);
                    else if(MASTER.equals(action)) FilesStore.importMaster(this,uri,progress);
                    else if(BACKUP.equals(action)) FilesStore.backup(this,uri);
                    else if(SAVE.equals(action)) { FilesStore.importSave(this,uri); closeGame(); }
                    else throw new IllegalArgumentException("Unknown operation");
                    state=BACKUP.equals(action)?"Saves exported":SAVE.equals(action)?"Save imported":"Import complete";
                    detail=BACKUP.equals(action)?"Keep your backup somewhere safe.":SAVE.equals(action)?"Save imported. Tap Play to continue with it.":FilesStore.ready(this)?"Your files are ready. Start the server when you want to play.":"Import the remaining game files to continue.";
                }
            } catch(Exception|LinkageError error) {
                running=false;state=cancelled?"Operation cancelled":"Needs attention";
                detail=error.getMessage()==null?error.toString():error.getMessage();
                android.util.Log.e("LunarTear",detail,error);
            } finally {
                busy=false; permille=-1;
                if(running) getSystemService(NotificationManager.class).notify(1,notification());
                else finishForeground();
            }
        });
        return START_NOT_STICKY;
    }
    // The launcher, Tools and this service share a process apart from the game.
    // Close the paused Unity process so its cached save/master cannot survive
    // the change.
    private void closeGame() {
        ActivityManager manager=getSystemService(ActivityManager.class);
        for(ActivityManager.RunningAppProcessInfo process:manager.getRunningAppProcesses())
            if(process.uid==android.os.Process.myUid()&&process.pid!=android.os.Process.myPid()&&process.processName.equals(getPackageName()))android.os.Process.killProcess(process.pid);
    }
    private void finishForeground() {
        if(wake!=null&&wake.isHeld())wake.release();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }
    @Override public void onDestroy() {
        cancelled=true;main.removeCallbacks(monitor);
        if(wake!=null&&wake.isHeld()) wake.release();
        // Never block the main thread waiting for Go's graceful shutdown.
        worker.execute(()->{if(tools){ToolsRuntime.stop();tools=false;}if(running){NativeBridge.stop();running=false;state="Server stopped";}busy=false;});
        worker.shutdown();
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }
    private final Messenger messenger=new Messenger(new Handler(Looper.getMainLooper(),message->{
        if(message.replyTo!=null) {
            Message reply=Message.obtain(null,message.what);
            Bundle b=new Bundle();b.putBoolean("running",running);b.putBoolean("busy",busy);b.putBoolean("tools",tools);b.putInt("permille",permille);b.putString("state",state);b.putString("detail",detail);
            if(message.what==2) { try { b.putString("native",NativeBridge.status()); } catch(Throwable e){b.putString("native","{\"logs\":\"Native server unavailable\"}");} }
            reply.setData(b);try{message.replyTo.send(reply);}catch(RemoteException ignored){}
        }
        return true;
    }));
    @Override public IBinder onBind(Intent intent){return messenger.getBinder();}
}

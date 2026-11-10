package org.veritr1x.bunker;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.net.Uri;
import android.os.*;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ServerService extends Service {
    static final String START="start", STOP="stop", ASSETS="assets", MASTER="master", BACKUP="backup", TOOLS="tools", CLOSE_TOOLS="close_tools", SAVE="save", ARCHIVE="archive", LINK="link", URL="url";
    static volatile boolean running=false, busy=false, tools=false;
    // Pod Programs opened beside the running game, which it has not closed yet. Cleared only once
    // the server is stopped and the save backed up, so a failed backup leaves changes refused.
    static volatile boolean toolsBesideGame=false;
    // Import progress, 0-1000, or -1 when there is no measured copy in progress.
    static volatile int permille=-1;
    static volatile String state="stopped", detail="";
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final Handler main=new Handler(Looper.getMainLooper());
    private volatile boolean cancelled=false;
    private PowerManager.WakeLock wake;
    private long lastNotification;
    /** The words the channel and notification were last made with (Texts.generation). */
    private int labelled;
    // The running service, for Pod Programs' Python (closeGameForTools).
    private static volatile ServerService instance;
    private final Runnable monitor=new Runnable() { public void run() {
        if(!running) return;
        try {
            JSONObject s=new JSONObject(NativeBridge.status());
            if(s.getString("state").equals("error")) {
                running=false; state="stopped"; detail=s.optString("error"); finishForeground(); return;
            }
        } catch(Exception ignored) {}
        main.postDelayed(this,2000);
    }};
    @Override public void onCreate() {
        super.onCreate();
        instance=this;
        NativeBridge.setLogDir(FilesStore.logs(this).getAbsolutePath());logLastExit();NativeBridge.setBackupDir(new java.io.File(new java.io.File(getFilesDir(),"tools"),"backups").getAbsolutePath());
        labelled=Texts.generation(this);channel();
        wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"lunartear:server");
        wake.setReferenceCounted(false);
    }
    /** Logs why Android ended the previous server process, which the log itself cannot show: a kill for memory leaves no last line. */
    private void logLastExit() {
        if(Build.VERSION.SDK_INT<30) return;
        try {
            SharedPreferences prefs=getSharedPreferences("lunar_server",MODE_PRIVATE);
            long seen=prefs.getLong("last_exit",0);
            for(ApplicationExitInfo exit:getSystemService(ActivityManager.class).getHistoricalProcessExitReasons(null,0,0)) {
                if(!exit.getProcessName().endsWith(":lunar_server")) continue;
                if(exit.getTimestamp()>seen) {
                    NativeBridge.log("Previous server process ended "+new java.util.Date(exit.getTimestamp())+": "+exitReason(exit.getReason())
                        +", status "+exit.getStatus()+", importance "+exit.getImportance()+", pss "+exit.getPss()+" kB, rss "+exit.getRss()+" kB"
                        +(exit.getDescription()==null?"":", "+exit.getDescription()));
                    prefs.edit().putLong("last_exit",exit.getTimestamp()).apply();
                }
                return; // newest first; earlier exits were logged when they were newest
            }
        } catch(Exception error) { android.util.Log.w("LunarTear","Exit reason unavailable",error); }
    }
    private static String exitReason(int reason) {
        switch(reason) {
            case ApplicationExitInfo.REASON_EXIT_SELF: return "exited";
            case ApplicationExitInfo.REASON_SIGNALED: return "killed by a signal";
            case ApplicationExitInfo.REASON_LOW_MEMORY: return "killed for low memory";
            case ApplicationExitInfo.REASON_CRASH: return "Java crash";
            case ApplicationExitInfo.REASON_CRASH_NATIVE: return "native crash";
            case ApplicationExitInfo.REASON_ANR: return "not responding";
            case ApplicationExitInfo.REASON_INITIALIZATION_FAILURE: return "failed to start";
            case ApplicationExitInfo.REASON_PERMISSION_CHANGE: return "permission changed";
            case ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE: return "killed for resource use";
            case ApplicationExitInfo.REASON_USER_REQUESTED: return "stopped by the user";
            case ApplicationExitInfo.REASON_USER_STOPPED: return "user stopped";
            case ApplicationExitInfo.REASON_DEPENDENCY_DIED: return "a dependency died";
            case ApplicationExitInfo.REASON_OTHER: return "ended by the system";
            default: return "reason "+reason;
        }
    }
    /** The state as the player reads it (launcher.state.<id>); the launcher compares the ids. */
    private String shown(String state){return Texts.t(this,"launcher.state."+state);}
    /** The notification channel, named in the pack's language (again when it changes). */
    private void channel() {
        NotificationChannel channel=new NotificationChannel("server",Texts.t(this,"launcher.notification.channel"),NotificationManager.IMPORTANCE_LOW);
        channel.setDescription(Texts.t(this,"launcher.notification.channel_info"));
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
    }
    /** An error's message: a Said reference or Lunar Tear's/Python's own words. */
    static String message(Throwable error){return error.getMessage()==null?error.toString():error.getMessage();}
    private Notification notification() {
        int now=Texts.generation(this);if(now!=labelled){labelled=now;channel();}
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class).putExtra("manage",true).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,ServerService.class).setAction(STOP),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder builder=new Notification.Builder(this,"server").setSmallIcon(Look.emblem(this)).setContentTitle(Texts.t(this,"launcher.notification.title","state",shown(state)))
            .setContentText(Texts.said(this,detail)).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(null,busy?Texts.t(this,"common.cancel"):Texts.t(this,"launcher.notification.stop"),stop).build());
        if(busy&&permille>=0)builder.setProgress(1000,permille,false).setStyle(new Notification.BigTextStyle().bigText(Texts.said(this,detail)));
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
            // With the game running, Pod Programs opens beside it; the first change that
            // needs the game closed closes it then (closeGameForTools).
            final boolean live=running;
            toolsBesideGame=live;
            toolsPaused=false;toolsBackedUp=false;
            tools=true;busy=true;cancelled=false;state="preparing_tools";detail=live?Said.text("launcher.detail.opening_tools"):Said.text("launcher.detail.stopping_game");
            if(Build.VERSION.SDK_INT>=34)startForeground(1,notification(),ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            else startForeground(1,notification());
            wake.acquire(12*60*60*1000L);
            if(!live)main.removeCallbacks(monitor);
            worker.execute(()->{
                try {
                    if(!live)stopGameForTools();
                    ToolsRuntime.start(this,this::update);
                    if(cancelled){ToolsRuntime.stop();tools=false;state=running?"running":"stopped";}
                    else {state="tools_ready";detail=running?Said.text("launcher.detail.tools_beside_game"):Said.text("launcher.detail.close_tools_to_play");}
                } catch(Exception|LinkageError error) {
                    tools=false;state="needs_attention";detail=message(error);
                    android.util.Log.e("LunarTear","Tools startup failed",Texts.forLog(error));
                } finally {
                    busy=false;
                    if(tools)getSystemService(NotificationManager.class).notify(1,notification());else finishForeground();
                }
            });
            return START_NOT_STICKY;
        }
        if(CLOSE_TOOLS.equals(action)&&running&&toolsBesideGame) {
            // The game was never closed: Pod Programs closes and the game plays on.
            busy=true;state="closing_tools";detail=Said.text("launcher.detail.game_keeps_running");
            worker.execute(()->{
                try {ToolsRuntime.stop();tools=false;toolsBesideGame=false;state="running";detail=Said.text("launcher.detail.ready");}
                catch(Exception error){state="needs_attention";detail=message(error);}
                finally {busy=false;}
            });
            return START_NOT_STICKY;
        }
        if(STOP.equals(action)||CLOSE_TOOLS.equals(action)) {
            cancelled=true;
            state="stopping"; detail=Said.text("launcher.detail.saving");
            busy=true;
            worker.execute(()->{
                try {ToolsRuntime.stop();tools=false;NativeBridge.stop();running=false;state="stopped";detail="";}
                catch(Exception error){state="needs_attention";detail=message(error);}
                finally {busy=false;if(!tools)finishForeground();}
            });
            return START_NOT_STICKY;
        }
        if(busy||running||tools) return START_NOT_STICKY;
        busy=true; cancelled=false; permille=-1;
        state=START.equals(action)?"starting":BACKUP.equals(action)?"exporting_saves":SAVE.equals(action)?"importing_save":"importing_files";
        detail=START.equals(action)?Said.text("launcher.detail.loading"):Said.text("launcher.detail.keep_source");
        if(Build.VERSION.SDK_INT>=34) startForeground(1,notification(),ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(1,notification());
        wake.acquire(12*60*60*1000L);
        Uri uri=intent.getData();
        worker.execute(()->{
            try {
                FilesStore.recover(this);
                if(START.equals(action)) {
                    FilesStore.ensureBootstrap(this);
                    FilesStore.noticeSource(this);
                    if(DataUpdate.needed(FilesStore.data(this),ToolsRuntime.directory(this),BuildConfig.BUNKER_VERSION)) {
                        update(Said.text("launcher.detail.updating_data"));
                        // A failure leaves the game data as it was; the game still starts.
                        try {ToolsRuntime.updateData(this);}
                        catch(Exception error){android.util.Log.e("LunarTear","Game data update failed",error);}
                    }
                    String error=NativeBridge.setPortOffset(Ports.offset(this));
                    if(error==null||!error.isEmpty()) throw new IllegalStateException(error==null?Said.text("launcher.error.no_answer"):error);
                    error=NativeBridge.start(FilesStore.data(this).getAbsolutePath(),FilesStore.root(this).getAbsolutePath());
                    if(error==null||!error.isEmpty()) throw new IllegalStateException(error==null?Said.text("launcher.error.no_answer"):error);
                    if(cancelled) { NativeBridge.stop(); throw new InterruptedException(Said.text("launcher.detail.start_cancelled")); }
                    // Confirm the game can reach this server on every port before playing.
                    String failure=selfTestFailure(NativeBridge.selfTest());
                    if(failure!=null) { NativeBridge.stop(); throw new IllegalStateException(failure); }
                    running=true;state="running";
                    detail=Said.text("launcher.detail.ready");
                    main.post(monitor);
                } else {
                    FilesStore.Progress progress=new FilesStore.Progress(){
                        public void update(String text){ServerService.this.update(text);}
                        public boolean cancelled(){return cancelled;}
                        public void fraction(int value){permille=value;}
                    };
                    // Another source replaces a stopped link download, whose files would only take space.
                    if(ASSETS.equals(action)||ARCHIVE.equals(action)||LINK.equals(action)) FilesStore.discardDownload(this);
                    if(ASSETS.equals(action)) FilesStore.importAssets(this,uri,progress);
                    else if(URL.equals(action)) FilesStore.importLink(this,uri.toString(),progress);
                    else if(ARCHIVE.equals(action)) FilesStore.importArchive(this,uri,progress);
                    else if(LINK.equals(action)) FilesStore.linkAssets(this,uri,progress);
                    else if(MASTER.equals(action)) { FilesStore.importMaster(this,uri,progress); ToolsRuntime.layerGameData(this); }
                    else if(BACKUP.equals(action)) FilesStore.backup(this,uri);
                    else if(SAVE.equals(action)) { FilesStore.importSave(this,uri); closeGame(); }
                    else throw new IllegalArgumentException(Said.text("launcher.error.unknown_operation"));
                    state=BACKUP.equals(action)?"saves_exported":SAVE.equals(action)?"save_imported":"import_complete";
                    detail=BACKUP.equals(action)?Said.text("launcher.detail.backup_saved"):SAVE.equals(action)?Said.text("launcher.detail.save_imported"):"";
                }
            } catch(Exception|LinkageError error) {
                running=false;state=cancelled?"cancelled":"needs_attention";
                detail=message(error);
                android.util.Log.e("LunarTear","Operation failed",Texts.forLog(error));
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
    /** Stops the server, backs up the save and closes the game, before Pod Programs changes them. */
    private void stopGameForTools() {
        main.removeCallbacks(monitor);
        NativeBridge.stop();running=false;
        String error=NativeBridge.prepareBackup(FilesStore.data(this).getAbsolutePath());
        if(!error.isEmpty())throw new IllegalStateException(error);
        closeGame();
    }
    /** For Pod Programs' Python, which logs what resumeForTools answers: its references in English. */
    public static String inEnglish(String said){return Texts.inEnglish(said);}
    /** Pod Programs: whether the game and its server are still running beside it. */
    public static boolean gameLive(){return tools&&toolsBesideGame;}
    /** Pod Programs, before a change to the save or the game's data: closes the game. Returns "" or why not. */
    public static String closeGameForTools(){
        ServerService service=instance;
        if(service==null)return Texts.t(null,"launcher.error.service_gone");
        synchronized(ServerService.class){
            if(!toolsBesideGame)return "";
            try {
                state="preparing_tools";detail=Said.text("launcher.detail.stopping_game");
                service.stopGameForTools();
                toolsBesideGame=false;
                state="tools_ready";detail=Said.text("launcher.detail.close_tools_to_play");
                return "";
            } catch(Exception|LinkageError error) {
                android.util.Log.e("LunarTear","Closing the game for Pod Programs failed",Texts.forLog(error));
                return Texts.said(service,message(error));
            }
        }
    }
    // Pod Programs beside the game: a change to the save or the game's data
    // stops the server for the change (pauseForTools) and starts it again
    // after (resumeForTools), which sends the game back to its title screen to
    // sign in again and load it. The game keeps running throughout.
    private static boolean toolsPaused=false, toolsBackedUp=false;
    /** Pod Programs, before a change beside the running game: stops the server, backing the save up once. Returns "" or why not. */
    public static String pauseForTools(){
        ServerService service=instance;
        if(service==null)return Texts.t(null,"launcher.error.service_gone");
        synchronized(ServerService.class){
            if(!toolsBesideGame||toolsPaused)return "";
            service.main.removeCallbacks(service.monitor);
            NativeBridge.stop();running=false;
            if(!toolsBackedUp){
                String error=NativeBridge.prepareBackup(FilesStore.data(service).getAbsolutePath());
                if(!error.isEmpty()){
                    // Nothing was changed yet: the game plays on as it was, if its server starts again.
                    String restart=resumeServer(service);
                    if(restart.isEmpty())return Texts.said(service,error);
                    // It cannot reach a server: close it, as resumeForTools does.
                    android.util.Log.e("LunarTear","Restarting the server beside the game failed: "+Texts.inEnglish(restart));
                    toolsBesideGame=false;service.closeGame();
                    state="tools_ready";detail=Said.text("launcher.detail.close_tools_to_play");
                    return Texts.t(service,"launcher.error.game_closed","error",Texts.said(service,error));
                }
                toolsBackedUp=true;
            }
            toolsPaused=true;state="applying_change";detail=Said.text("launcher.detail.change_loading");
            return "";
        }
    }
    /** Pod Programs, after a change beside the running game: starts the server and sends the game to its title screen.
     *  Returns "" or why not, as a Said reference or Lunar Tear's words: only logged (ServerService.inEnglish). */
    public static String resumeForTools(){return resumeForTools(true);}
    /** As resumeForTools; title false for a change that was refused or changed nothing, so the game keeps its place. */
    public static String resumeForTools(boolean title){
        ServerService service=instance;
        if(service==null)return Said.text("launcher.error.service_gone");
        synchronized(ServerService.class){
            if(!toolsPaused)return "";
            toolsPaused=false;
            String error=resumeServer(service);
            if(error.isEmpty()){
                if(title){NativeBridge.requestTitle();state="tools_ready";detail=Said.text("launcher.detail.change_loading");}
                else{state="tools_ready";detail=Said.text("launcher.detail.nothing_changed");}
                return "";
            }
            // The game cannot reach a server: close it, as before this change could run beside it.
            android.util.Log.e("LunarTear","Restarting the server beside the game failed: "+Texts.inEnglish(error));
            toolsBesideGame=false;service.closeGame();
            state="tools_ready";detail=Said.text("launcher.detail.close_tools_to_play");
            return error;
        }
    }
    private static String resumeServer(ServerService service){
        String error=NativeBridge.start(FilesStore.data(service).getAbsolutePath(),FilesStore.root(service).getAbsolutePath());
        if(error==null||!error.isEmpty())return error==null?Said.text("launcher.error.no_answer"):error;
        String failure=selfTestFailure(NativeBridge.selfTest());
        if(failure!=null){NativeBridge.stop();return failure;}
        running=true;service.main.post(service.monitor);
        return "";
    }
    private void closeGame() {
        ActivityManager manager=getSystemService(ActivityManager.class);
        for(ActivityManager.RunningAppProcessInfo process:manager.getRunningAppProcesses())
            if(process.uid==android.os.Process.myUid()&&process.pid!=android.os.Process.myPid()&&process.processName.equals(getPackageName()))android.os.Process.killProcess(process.pid);
    }
    /** Returns a message naming each port that failed the self-test, or null when all passed. */
    static String selfTestFailure(String report) {
        try {
            JSONObject r=new JSONObject(report);
            if(r.optBoolean("ok")) return null;
            StringBuilder text=new StringBuilder(Said.text("launcher.selftest.failed"));
            org.json.JSONArray checks=r.getJSONArray("checks");
            for(int i=0;i<checks.length();i++){
                JSONObject c=checks.getJSONObject(i);
                if(!c.optBoolean("ok")) text.append("\n• ").append(Said.text("launcher.selftest.port","port",c.optInt("port"),"name",c.optString("name"),"detail",c.optString("detail")));
            }
            return text.toString();
        } catch(Exception e) { return Said.text("launcher.selftest.unchecked","error",String.valueOf(e.getMessage())); }
    }
    private void finishForeground() {
        if(wake!=null&&wake.isHeld())wake.release();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }
    @Override public void onDestroy() {
        if(instance==this)instance=null;
        cancelled=true;main.removeCallbacks(monitor);
        if(wake!=null&&wake.isHeld()) wake.release();
        // Never block the main thread waiting for Go's graceful shutdown.
        worker.execute(()->{if(tools){ToolsRuntime.stop();tools=false;}if(running){NativeBridge.stop();running=false;state="stopped";}busy=false;});
        worker.shutdown();
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }
    private final Messenger messenger=new Messenger(new Handler(Looper.getMainLooper(),message->{
        // The launcher asks often: a language chosen since the notification was made renames it now.
        if((running||tools)&&Texts.generation(this)!=labelled)getSystemService(NotificationManager.class).notify(1,notification());
        if(message.replyTo!=null) {
            Message reply=Message.obtain(null,message.what);
            Bundle b=new Bundle();b.putBoolean("running",running);b.putBoolean("busy",busy);b.putBoolean("tools",tools);b.putInt("permille",permille);b.putString("state",state);b.putString("detail",detail);
            if(message.what==2) { try { b.putString("native",NativeBridge.status()); } catch(Throwable e){b.putString("native","{\"logs\":\"Native server unavailable\"}");} }
            if(message.what==3) {
                // The checks take up to a few seconds; answer from a background thread.
                Messenger to=message.replyTo;
                new Thread(()->{
                    Bundle result=new Bundle();
                    try { result.putString("selftest",running?NativeBridge.selfTest():""); } catch(Throwable e){ result.putString("selftest",""); }
                    Message answer=Message.obtain(null,3);answer.setData(result);
                    try{to.send(answer);}catch(RemoteException ignored){}
                },"lunar-self-test").start();
                return true;
            }
            reply.setData(b);try{message.replyTo.send(reply);}catch(RemoteException ignored){}
        }
        return true;
    }));
    @Override public IBinder onBind(Intent intent){return messenger.getBinder();}
}

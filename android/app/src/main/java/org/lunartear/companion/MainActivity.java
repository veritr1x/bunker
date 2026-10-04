package org.lunartear.companion;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import org.json.JSONObject;
import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public final class MainActivity extends Activity {
    private static final int ASSETS=10, MASTER=11, BACKUP=12, SAVE=13, ARCHIVE=14, LINK=15, LOGS=16;
    // Set while the player turns on All files access for "use in place".
    private boolean awaitingAccess;
    private Look look;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView status,detail,files,ports,save,progressText;
    private Button assetButton,play,pods;
    private ProgressBar progress;
    private Look.Segments bar;
    private int permille=-1;
    private String last="";
    private boolean running=false,busy=false,tools=false,bound=false,autoAttempted=false,launchWhenReady=true,foreground=false;
    private String serverState="Server stopped",serverDetail="Import your game files to get started.";
    private Messenger service;
    private final Messenger replies=new Messenger(new Handler(Looper.getMainLooper(),message->{
        Bundle b=message.getData();running=b.getBoolean("running");busy=b.getBoolean("busy");tools=b.getBoolean("tools");permille=b.getInt("permille",-1);serverState=b.getString("state","");serverDetail=b.getString("detail","");
        refresh();
        if(message.what==2) displayLog(b.getString("native","{}"));
        if(message.what==3) showServerCheck(b.getString("selftest",""));
        if(foreground&&running&&!tools&&launchWhenReady){launchWhenReady=false;openGame();}
        else if(foreground&&!busy&&!running&&!tools&&!autoAttempted&&FilesStore.ready(this)){autoAttempted=true;run(ServerService.START,null);}
        return true;
    }));
    private final ServiceConnection connection=new ServiceConnection(){
        public void onServiceConnected(ComponentName name,IBinder binder){service=new Messenger(binder);query(1);}
        public void onServiceDisconnected(ComponentName name){service=null;running=false;busy=false;serverState="Server stopped";serverDetail="Tap Play to restart.";refresh();}
    };
    private void query(int code){if(service==null)return;Message m=Message.obtain(null,code);m.replyTo=replies;try{service.send(m);}catch(RemoteException ignored){}}

    private final Runnable tick=new Runnable(){public void run(){query(1);refresh();handler.postDelayed(this,700);}};
    private int dp(int n){return look.dp(n);}
    private AlertDialog.Builder dialog(){return new AlertDialog.Builder(this,look.dark?android.R.style.Theme_DeviceDefault_Dialog_Alert:android.R.style.Theme_DeviceDefault_Light_Dialog_Alert);}
    private LinearLayout panel(){
        LinearLayout p=new LinearLayout(this);p.setOrientation(LinearLayout.VERTICAL);p.setBackground(look.frame());
        int pad=look.framePadding();p.setPadding(pad,pad-dp(4),pad,pad-dp(4));return p;
    }
    /** One LABEL  value row of a panel; a button in the row sits at the far right. */
    private void row(LinearLayout panel,String label,View... values){
        LinearLayout r=new LinearLayout(this);r.setGravity(Gravity.CENTER_VERTICAL);r.setMinimumHeight(dp(40));
        TextView name=look.monoText(label,11,look.mid);name.setLetterSpacing(.1f);r.addView(name,new LinearLayout.LayoutParams(dp(104),-2));
        for(View v:values){
            if(v instanceof Button){r.addView(new View(this),new LinearLayout.LayoutParams(0,1,1));r.addView(v,new LinearLayout.LayoutParams(-2,dp(40)));}
            else if(v instanceof ProgressBar){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(dp(18),dp(18));p.setMargins(dp(10),0,0,0);r.addView(v,p);}
            else r.addView(v,new LinearLayout.LayoutParams(-2,-2));
        }
        panel.addView(r,new LinearLayout.LayoutParams(-1,-2));
    }
    private static String size(long bytes){return bytes>=1<<20?String.format(Locale.US,"%.1f MB",bytes/1048576.0):Math.max(1,bytes/1024)+" KB";}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        look=Look.of(this);look.apply(this);
        autoAttempted=state!=null?state.getBoolean("attempted"):getIntent().getBooleanExtra("manage",false);
        launchWhenReady=state!=null?state.getBoolean("launch"):!getIntent().getBooleanExtra("manage",false);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackground(look.paper());
        FrameLayout frame=new FrameLayout(this);scroll.addView(frame,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(18),dp(18),dp(18),0);
        frame.addView(body,new FrameLayout.LayoutParams(Math.min(getResources().getDisplayMetrics().widthPixels,dp(520)),-1,Gravity.CENTER_HORIZONTAL));
        scroll.setOnApplyWindowInsetsListener((view,insets)->{view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        // Top bar: where you are, and the options.
        LinearLayout top=new LinearLayout(this);top.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout titles=new LinearLayout(this);titles.setOrientation(LinearLayout.VERTICAL);
        TextView caption=look.monoText("LUNAR TEAR // 127.0.0.1",10,look.mid);caption.setLetterSpacing(.2f);titles.addView(caption);
        TextView title=look.text("BUNKER",22,look.ink);title.setTypeface(null,Typeface.BOLD);title.setLetterSpacing(.28f);titles.addView(title);
        top.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
        Button more=look.outlined("⋮");more.setTextSize(20);more.setLetterSpacing(0);more.setPadding(0,0,0,0);more.setContentDescription("Options");more.setOnClickListener(this::showOptions);
        top.addView(more,new LinearLayout.LayoutParams(dp(44),dp(44)));
        LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(-1,-2);tp.setMargins(0,0,0,dp(20));body.addView(top,tp);
        // [ SYSTEM ]: game files, Lunar Tear, ports and save.
        LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(-1,-2);hp.setMargins(0,0,0,dp(8));body.addView(look.header("System"),hp);
        LinearLayout system=panel();
        files=look.chip();assetButton=look.outlined("CHOOSE");assetButton.setContentDescription("Choose game files");assetButton.setOnClickListener(v->chooseAssets());
        row(system,"GAME FILES",files,assetButton);
        status=look.chip();progress=new ProgressBar(this);progress.setIndeterminateTintList(ColorStateList.valueOf(look.ink));
        row(system,"LUNAR TEAR",status,progress);
        ports=look.monoText("",13,look.ink);row(system,"PORTS",ports);
        save=look.monoText("",13,look.ink);row(system,"SAVE",save);
        bar=new Look.Segments(look);LinearLayout.LayoutParams barParams=new LinearLayout.LayoutParams(-1,dp(14));barParams.setMargins(0,dp(10),0,dp(6));system.addView(bar,barParams);
        progressText=look.monoText("",12,look.ink);system.addView(progressText);
        LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(-1,-2);pp.setMargins(0,0,0,dp(20));body.addView(system,pp);
        // [ PLAY ]: what happens next, and Deploy.
        LinearLayout.LayoutParams hp2=new LinearLayout.LayoutParams(-1,-2);hp2.setMargins(0,0,0,dp(8));body.addView(look.header("Play"),hp2);
        LinearLayout launch=panel();
        detail=look.monoText("",12,look.ink);LinearLayout.LayoutParams dp1=new LinearLayout.LayoutParams(-1,-2);dp1.setMargins(0,dp(6),0,dp(12));launch.addView(detail,dp1);
        play=look.solid("DEPLOY  ▶");play.setContentDescription("Deploy: start the game");
        play.setOnClickListener(v->{launchWhenReady=true;autoAttempted=true;if(running){launchWhenReady=false;openGame();}else run(ServerService.START,null);});
        LinearLayout.LayoutParams bp2=new LinearLayout.LayoutParams(-1,dp(56));bp2.setMargins(0,0,0,dp(6));launch.addView(play,bp2);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,0,0,dp(20));body.addView(launch,lp);
        // [ POD PROGRAMS ]: the save editors and content choices, one tap away.
        LinearLayout.LayoutParams hp3=new LinearLayout.LayoutParams(-1,-2);hp3.setMargins(0,0,0,dp(8));body.addView(look.header("Pod Programs"),hp3);
        LinearLayout programs=panel();
        TextView about=look.monoText("Edit your save and choose which events and shops appear.",12,look.ink);
        LinearLayout.LayoutParams ap=new LinearLayout.LayoutParams(-1,-2);ap.setMargins(0,dp(6),0,dp(12));programs.addView(about,ap);
        pods=look.outlined("OPEN POD PROGRAMS  ›");pods.setTextSize(13);pods.setContentDescription("Open Pod Programs");
        pods.setOnClickListener(v->onOption(8));
        LinearLayout.LayoutParams pb=new LinearLayout.LayoutParams(-1,dp(48));pb.setMargins(0,0,0,dp(6));programs.addView(pods,pb);
        body.addView(programs,new LinearLayout.LayoutParams(-1,-2));
        body.addView(new View(this),new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,-2);fp.setMargins(0,dp(28),0,0);body.addView(look.footer(),fp);
        setContentView(scroll);
        refresh();
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);
        try{FilesStore.recover(this);}catch(Exception e){serverDetail=e.getMessage();}
        new Thread(()->{try{FilesStore.ensureBootstrap(this);}catch(Exception ignored){}runOnUiThread(()->{last="";refresh();});},"bootstrap").start();
    }
    @Override public void onResume(){super.onResume();foreground=true;
        if(awaitingAccess){awaitingAccess=false;if(FilesStore.canUseInPlace())chooseFolder(LINK);}bound=bindService(new Intent(this,ServerService.class),connection,BIND_AUTO_CREATE);handler.post(tick);}
    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);setIntent(intent);
        boolean manage=intent.getBooleanExtra("manage",false);
        autoAttempted=manage;launchWhenReady=!manage;
        query(1);
    }
    @Override public void onPause(){foreground=false;handler.removeCallbacks(tick);if(bound){unbindService(connection);bound=false;service=null;}super.onPause();}
    @Override protected void onSaveInstanceState(Bundle out){out.putBoolean("attempted",autoAttempted);out.putBoolean("launch",launchWhenReady);super.onSaveInstanceState(out);}
    private void refresh(){
        boolean hasAssets=FilesStore.list(this).length()>0,hasMaster=FilesStore.master(this).length()>0,ready=hasAssets&&hasMaster;
        String key=serverState+serverDetail+busy+running+tools+hasAssets+hasMaster+permille;
        if(key.equals(last))return;last=key;
        boolean importing=busy&&"Importing files".equals(serverState);
        if(importing)look.chip(files,"IMPORTING",look.chip,look.ink);
        else if(hasAssets)look.chip(files,"READY",look.ok,look.onOk);
        else look.chip(files,"NO FILES",look.chip,look.ink);
        assetButton.setText(hasAssets?"CHANGE":"CHOOSE");assetButton.setVisibility(running?View.GONE:View.VISIBLE);assetButton.setEnabled(!busy&&!running&&!tools);assetButton.setAlpha(assetButton.isEnabled()?1f:.45f);
        boolean attention="Needs attention".equals(serverState);
        String state=tools?"POD PROGRAMS OPEN":"Stopping".equals(serverState)&&busy?"STOPPING":running?"RUNNING":"Starting server".equals(serverState)&&busy?"STARTING":attention?"NOT RUNNING":ready?"STANDING BY":"WAITING FOR FILES";
        if(running&&!tools)look.chip(status,state,look.ok,look.onOk);
        else if(attention)look.chip(status,state,look.alert,look.paper);
        else look.chip(status,state,look.chip,look.ink);
        ports.setText(Ports.game(this)+" · "+Ports.assets(this)+" · "+Ports.accounts(this));
        File db=new File(FilesStore.data(this),"game.db");
        save.setText(db.isFile()?"game.db · "+size(db.length()):"none yet");
        boolean measured=importing&&permille>=0;
        // A measured copy shows the bar with time left; anything else, the spinner.
        progress.setVisibility(busy&&!measured?View.VISIBLE:View.GONE);
        bar.setVisibility(measured?View.VISIBLE:View.GONE);
        if(measured)bar.setPermille(permille);
        progressText.setVisibility(importing?View.VISIBLE:View.GONE);
        progressText.setText(importing?(measured?permille/10+"% · ":"")+serverDetail:"");
        play.setEnabled(!busy&&!tools&&ready);play.setAlpha(play.isEnabled()?1f:.45f);
        pods.setEnabled(!busy&&ready);pods.setAlpha(pods.isEnabled()?1f:.45f);
        String message="";
        boolean warning=attention||"Operation cancelled".equals(serverState);
        if(warning)message=serverDetail;
        else if(importing)message="Keep the app open until unpacking finishes.";
        else if(busy&&!"Starting server".equals(serverState)&&!"Stopping".equals(serverState))message=serverDetail;
        else if("Saves exported".equals(serverState))message="Backup saved.";
        else if("Save imported".equals(serverState))message=serverDetail;
        else if(hasAssets&&!hasMaster){message="Import master data from the ⋮ menu.";warning=true;}
        else if(!hasAssets&&FilesStore.linkedFolder(this)!=null){warning=true;message=FilesStore.canUseInPlace()?"Your game files folder is missing: "+FilesStore.linkedFolder(this)+". Put it back or choose the files again.":"Allow All files access for NieR in Settings to read your game files folder, or choose the files again.";}
        else if("Server stopped".equals(serverState)&&!serverDetail.isEmpty()&&!serverDetail.equals("Import your game files to get started.")&&!serverDetail.equals("Tap Play to restart.")&&!serverDetail.equals("Your saves are stored on this phone."))message=serverDetail;
        if(message.isEmpty())message=tools?"Close Pod Programs to deploy again.":running?"Lunar Tear is up. The game connects to it on this device; no network is needed.":ready?"Deploy starts Lunar Tear, then opens the game.":"Choose the game files to begin: the resource dump's .7z or its extracted folder.";
        detail.setText(warning?"> "+message:message);detail.setTextColor(warning?look.alert:look.ink);
    }
    private void chooseAssets(){
        dialog().setTitle("Choose the game files")
            .setItems(new String[]{"Extracted folder: copy into the app","Extracted folder: use in place","Archive (.7z or .zip)"},(dialog,which)->{
                if(which==0)chooseFolder(ASSETS);
                else if(which==1)useInPlace();
                // The resource dump's .7z can be chosen directly; only revision 0 is unpacked.
                else{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,ARCHIVE);}
            }).show();
    }
    private void chooseFolder(int code){
        Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(i,code);
    }
    /** Uses an extracted folder where it is, saving 21 GB. Needs All files access, which only Settings can grant. */
    private void useInPlace(){
        if(Build.VERSION.SDK_INT<30){dialog().setTitle("Use in place").setMessage("Using a folder in place needs Android 11 or later. Copy it into the app instead.").setPositiveButton("OK",null).show();return;}
        if(FilesStore.canUseInPlace()){chooseFolder(LINK);return;}
        dialog().setTitle("Allow All files access")
            .setMessage("To read the game files where they are, NieR needs All files access. It only reads the folder you choose next.\n\nTurn on the switch in Settings, then come back. Keep the folder where it is afterwards: if it is moved or deleted, choose it again.")
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Open Settings",(dialog,which)->{
                awaitingAccess=true;
                try{startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,Uri.parse("package:"+getPackageName())));}
                catch(Exception e){startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));}
            }).show();
    }
    /** The ⋮ menu, as a Bunker panel in three sections. */
    private void showOptions(View anchor){
        boolean idle=!busy&&!running&&!tools;
        Dialog menu=new Dialog(this);menu.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout panel=panel();
        // Pod Programs has its own panel on the Bunker; this section only appears while there is something to stop or check.
        if(running||busy)section(panel,"Lunar Tear");
        if(running||busy)option(panel,menu,1,busy?"Cancel operation":"Stop Lunar Tear",true);
        if(running)option(panel,menu,10,"Check Lunar Tear",true);
        section(panel,"Data");
        if(!idle){TextView note=look.monoText("> Stop Lunar Tear to import or export saves.",11,look.alert);note.setPadding(0,0,0,dp(4));panel.addView(note);}
        option(panel,menu,2,"Import master data",idle);
        option(panel,menu,3,"Export save backup",idle&&new File(FilesStore.data(this),"game.db").isFile());
        option(panel,menu,9,"Import save backup",idle);
        section(panel,"Support");
        option(panel,menu,4,"Lunar Tear log",true);
        option(panel,menu,11,"Export Lunar Tear log",true);
        option(panel,menu,12,"Display: "+Character.toUpperCase(Look.display(this).charAt(0))+Look.display(this).substring(1),true);
        option(panel,menu,5,"App settings",true);
        option(panel,menu,6,"Help",true);
        option(panel,menu,7,"About",true);
        // The frame sits on a holder around the list, so it stays put while the list scrolls,
        // and a small margin leaves room for its corner brackets.
        panel.setBackground(null);panel.setPadding(0,0,0,0);
        ScrollView scroll=new ScrollView(this);scroll.addView(panel);scroll.setVerticalScrollBarEnabled(false);
        FrameLayout holder=new FrameLayout(this);holder.setBackground(look.floating());
        int pad=look.framePadding()+dp(2);holder.setPadding(pad,pad-dp(6),pad,pad-dp(6));
        holder.addView(scroll);
        FrameLayout margin=new FrameLayout(this);margin.setPadding(dp(4),dp(4),dp(4),dp(4));margin.addView(holder);
        menu.setContentView(margin);
        Window window=menu.getWindow();
        if(window!=null){
            window.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(0));
            window.setLayout(Math.min(getResources().getDisplayMetrics().widthPixels-dp(32),dp(420)),-2);
            window.setDimAmount(look.dark?.6f:.35f);
        }
        menu.show();
    }
    private void section(LinearLayout panel,String title){
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(panel.getChildCount()==0?6:16),0,dp(6));panel.addView(look.header(title),p);
    }
    private void option(LinearLayout panel,Dialog menu,int id,String label,boolean enabled){
        // Same voice as the rest of the Bunker: uppercase monospace, like GAME FILES and the Pod Programs tabs.
        TextView item=look.monoText("■  "+label.toUpperCase(),13,look.ink);item.setLetterSpacing(.12f);item.setGravity(Gravity.CENTER_VERTICAL);item.setMinHeight(dp(44));item.setPadding(dp(8),0,dp(8),0);
        item.setBackground(new RippleDrawable(ColorStateList.valueOf(look.line),null,new android.graphics.drawable.ColorDrawable(0xffffffff)));
        item.setEnabled(enabled);item.setAlpha(enabled?1f:.4f);item.setFocusable(enabled);
        if(enabled)item.setOnClickListener(v->{menu.dismiss();onOption(id);});
        item.setAccessibilityDelegate(new View.AccessibilityDelegate(){@Override public void onInitializeAccessibilityNodeInfo(View host,android.view.accessibility.AccessibilityNodeInfo info){super.onInitializeAccessibilityNodeInfo(host,info);info.setClassName(Button.class.getName());}});
        panel.addView(item,new LinearLayout.LayoutParams(-1,-2));
        View rule=new View(this);rule.setBackgroundColor(look.line);panel.addView(rule,new LinearLayout.LayoutParams(-1,1));
    }
    /** Light, dark, or the phone's own setting. */
    private void chooseDisplay(){
        String[] modes={"system","light","dark"};
        int current=java.util.Arrays.asList(modes).indexOf(Look.display(this));
        dialog().setTitle("Display").setSingleChoiceItems(new String[]{"System (follow the phone)","Light","Dark"},Math.max(0,current),(d,which)->{
            d.dismiss();
            if(which==current)return;
            Look.display(this,modes[which]);
            recreate();
        }).setNegativeButton("Cancel",null).show();
    }
    private void onOption(int id){
        switch(id){
            case 12: chooseDisplay();break;
            case 1: autoAttempted=true;launchWhenReady=false;run(ServerService.STOP,null);break;
            case 2: {Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(i,MASTER);break;}
            case 3: {Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_TITLE,"lunar-tear-saves-"+new SimpleDateFormat("yyyyMMdd-HHmm",Locale.US).format(new Date())+".zip");startActivityForResult(i,BACKUP);break;}
            case 4: showLog();break;
            case 5: startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName())));break;
            case 6: help();break;
            case 7: dialog().setTitle("Lunar Tear").setMessage("Offline companion · 0.1.0\nBased on Lunar Tear by Walter-Sparrow.\nMIT License · Copyright 2026 Ilya Groshev.").setPositiveButton("Close",null).show();break;
            case 9: confirmSaveImport();break;
            case 10: query(3);break;
            case 11: {Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_TITLE,"lunar-tear-log-"+new SimpleDateFormat("yyyyMMdd-HHmm",Locale.US).format(new Date())+".zip");startActivityForResult(i,LOGS);break;}
            case 8: autoAttempted=true;launchWhenReady=false;startActivity(new Intent(this,ToolsActivity.class));break;
        }
    }
    private void confirmSaveImport(){
        dialog().setTitle("Import a save backup?")
            .setMessage("This replaces the save on this phone with the backup you choose: a ZIP from Export save backup (on Android or iPhone), or a game.db file. Your current save is kept as a safety copy.")
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Choose backup",(dialog,which)->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,SAVE);})
            .show();
    }
    private void run(String action,Uri uri){
        Intent intent=new Intent(this,ServerService.class).setAction(action);if(uri!=null)intent.setData(uri);
        if(ServerService.STOP.equals(action))startService(intent);else startForegroundService(intent);
    }
    private void openGame(){
        Intent intent=null;
        try {
            android.content.pm.ApplicationInfo info=getPackageManager().getApplicationInfo(getPackageName(),PackageManager.GET_META_DATA);
            String game=info.metaData==null?null:info.metaData.getString("org.lunartear.GAME_ACTIVITY");
            if(game!=null) intent=new Intent().setClassName(this,game);
            else intent=getPackageManager().getLaunchIntentForPackage("com.square_enix.android_googleplay.nierspww");
        } catch(PackageManager.NameNotFoundException ignored){}
        if(intent==null)dialog().setTitle("Install the patched game").setMessage("Install the APK patched for 127.0.0.1. The original game APK cannot connect to this server.").setPositiveButton("OK",null).show();
        else startActivity(intent);
    }
    private void help(){
        dialog().setTitle("Help").setMessage("This is the Bunker. Lunar Tear is the game's server, running on this phone.\n\nChoose the game files once: the resource dump's .7z, or an extracted folder to copy or use in place. Master data is already included. When your files are ready, Lunar Tear starts and Deploy opens the game.\n\nTap the Lunar Tear notification to return here. Stop Lunar Tear from ⋮ before changing files or exporting saves. Export a backup before uninstalling or clearing app storage. Import save backup restores one, from this phone, another phone or an iPhone. Pod Programs edits your save and chooses events.\n\nIf Samsung pauses Lunar Tear, set Battery usage to Unrestricted in App settings.")
            .setPositiveButton("Close",null).show();
    }
    private void showLog(){query(2);}
    /** Shows whether the game can reach this server on each of its ports. */
    private void showServerCheck(String report){
        StringBuilder text=new StringBuilder();
        boolean ok=false;
        try{
            org.json.JSONObject r=new org.json.JSONObject(report);ok=r.optBoolean("ok");
            org.json.JSONArray checks=r.getJSONArray("checks");
            for(int i=0;i<checks.length();i++){
                org.json.JSONObject c=checks.getJSONObject(i);
                text.append(c.optBoolean("ok")?"✓ ":"✗ ").append(c.optString("name")).append(" · port ").append(c.optInt("port"));
                if(!c.optBoolean("ok"))text.append("\n   ").append(c.optString("detail"));
                text.append("\n");
            }
        }catch(Exception e){text.append("Lunar Tear is not running.");}
        dialog().setTitle(ok?"Lunar Tear is reachable":"Lunar Tear check failed").setMessage(text.toString().trim()).setPositiveButton("Close",null).show();
    }
    private void displayLog(String nativeStatus){
        String value;
        try{JSONObject s=new JSONObject(nativeStatus);value=s.optString("logs","No server log yet.");if(value.isEmpty())value="No server log yet.";}
        catch(Throwable e){value="Unable to load native server: "+e.getMessage();}
        TextView t=look.monoText(value,12,look.ink);t.setTextIsSelectable(true);t.setPadding(dp(18),dp(12),dp(18),dp(12));ScrollView sc=new ScrollView(this);sc.addView(t);
        dialog().setTitle("Lunar Tear log").setView(sc).setPositiveButton("Close",null).show();
    }
    private void exportLogs(Uri uri){
        String version;try{version=getPackageManager().getPackageInfo(getPackageName(),0).versionName;}catch(Exception e){version="unknown";}
        String info="Companion 0.1.0, package "+getPackageName()+" "+version+"\nAndroid "+Build.VERSION.RELEASE+" (API "+Build.VERSION.SDK_INT+")\nDevice "+Build.MANUFACTURER+" "+Build.MODEL+"\nPort offset "+Ports.offset(this);
        new Thread(()->{
            String error;
            try(ParcelFileDescriptor fd=getContentResolver().openFileDescriptor(uri,"rwt")){
                error=fd==null?"Cannot open the chosen file":NativeBridge.exportLogs(FilesStore.logs(this).getAbsolutePath(),fd.getFd(),info);
            }catch(Exception e){error=e.getMessage();}
            String result=error;
            runOnUiThread(()->dialog().setTitle(result==null||result.isEmpty()?"Lunar Tear log exported":"Export failed")
                .setMessage(result==null||result.isEmpty()?"Attach the ZIP when you report a problem. It holds the Lunar Tear log and this phone's model and Android version.":result).setPositiveButton("Close",null).show());
        },"export-logs").start();
    }
    @Override protected void onActivityResult(int code,int result,Intent data){
        super.onActivityResult(code,result,data);if(result!=RESULT_OK||data==null||data.getData()==null)return;
        Uri uri=data.getData();
        if(code==LOGS){exportLogs(uri);return;}
        if(code==ASSETS||code==MASTER||code==LINK){try{getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(SecurityException ignored){}}
        if(code==ASSETS)run(ServerService.ASSETS,uri);else if(code==MASTER)run(ServerService.MASTER,uri);else if(code==BACKUP)run(ServerService.BACKUP,uri);else if(code==SAVE)run(ServerService.SAVE,uri);else if(code==ARCHIVE)run(ServerService.ARCHIVE,uri);else if(code==LINK)run(ServerService.LINK,uri);
    }
}

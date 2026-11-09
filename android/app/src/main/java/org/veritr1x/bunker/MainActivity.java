package org.veritr1x.bunker;

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
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
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
    private TextView status,detail,files,save,archiveLine,progressText;
    // The Archive's index, checked once per launcher process (and built then if missing or out of date):
    // before the game starts, or when the launcher opens from the game. Static, so a launcher opened from
    // the game's Bunker button (a new screen in the same process) shows the result instead of NOT CHECKED.
    private static volatile boolean indexChecked=false,indexing=false,openedWhileIndexing=false;
    private static volatile String indexText="NOT CHECKED";
    private Button assetButton,play;
    private View pods,archive;
    // Updates (Updater.java keeps their state, so it survives the screen being recreated).
    private LinearLayout updatePanel;
    /** A phone on its side: a shorter top bar, tighter rows, no footer. */
    private boolean compact;
    private TextView updateText;
    private Button updateButton,updateWeb,updateLater,updateSkip;
    private ProgressBar progress;
    private Look.Segments bar;
    private int permille=-1;
    private String last="";
    private boolean running=false,busy=false,tools=false,bound=false,autoAttempted=false,launchWhenReady=true,foreground=false;
    private String serverState="Server stopped",serverDetail="";
    private Messenger service;
    private final Messenger replies=new Messenger(new Handler(Looper.getMainLooper(),message->{
        Bundle b=message.getData();running=b.getBoolean("running");busy=b.getBoolean("busy");tools=b.getBoolean("tools");permille=b.getInt("permille",-1);serverState=b.getString("state","");serverDetail=b.getString("detail","");
        refresh();
        if(message.what==2) displayLog(b.getString("native","{}"));
        if(message.what==3) showServerCheck(b.getString("selftest",""));
        if(foreground&&running&&!tools&&launchWhenReady){launchWhenReady=false;launchAfterIndex();}
        else if(foreground&&!busy&&!running&&!tools&&!autoAttempted&&FilesStore.ready(this)){autoAttempted=true;run(ServerService.START,null);}
        return true;
    }));
    private final ServiceConnection connection=new ServiceConnection(){
        public void onServiceConnected(ComponentName name,IBinder binder){service=new Messenger(binder);query(1);}
        public void onServiceDisconnected(ComponentName name){service=null;running=false;busy=false;serverState="Server stopped";serverDetail="";refresh();}
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
    /** A row in a panel that opens something: its name and a chevron. */
    private View link(LinearLayout panel,String name,View.OnClickListener open){
        LinearLayout r=new LinearLayout(this);r.setGravity(Gravity.CENTER_VERTICAL);r.setMinimumHeight(dp(compact?40:48));int v=dp(compact?2:4);r.setPadding(dp(4),v,dp(4),v);
        r.setBackground(new RippleDrawable(ColorStateList.valueOf(look.line),null,new android.graphics.drawable.ColorDrawable(0xffffffff)));
        LinearLayout words=new LinearLayout(this);words.setOrientation(LinearLayout.VERTICAL);
        TextView title=look.monoText(name,13,look.ink);title.setLetterSpacing(.12f);title.setTypeface(null,Typeface.BOLD);words.addView(title);
        r.addView(words,new LinearLayout.LayoutParams(0,-2,1));
        TextView chevron=look.text("›",22,look.ink);r.addView(chevron);
        r.setOnClickListener(open);r.setFocusable(true);
        r.setAccessibilityDelegate(new View.AccessibilityDelegate(){@Override public void onInitializeAccessibilityNodeInfo(View host,android.view.accessibility.AccessibilityNodeInfo info){super.onInitializeAccessibilityNodeInfo(host,info);info.setClassName(Button.class.getName());}});
        panel.addView(r,new LinearLayout.LayoutParams(-1,-2));
        return r;
    }
    /** A [ HEADER ] and its panel, with gapAfter dp below. */
    private void block(LinearLayout parent,String header,View panel,int gapAfter){
        LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(-1,-2);hp.setMargins(0,0,0,dp(compact?6:8));parent.addView(look.header(header),hp);
        LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(-1,-2);pp.setMargins(0,0,0,dp(gapAfter));parent.addView(panel,pp);
    }
    private void row(LinearLayout panel,String label,View... values){
        LinearLayout r=new LinearLayout(this);r.setGravity(Gravity.CENTER_VERTICAL);r.setMinimumHeight(dp(compact?34:40));
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
        addMenuShortcut();
        // Auto deploy off (⋮ menu): opened as "manage" is, the launcher stays until DEPLOY.
        boolean manage=getIntent().getBooleanExtra("manage",false)||!autoDeploy(this);
        autoAttempted=state!=null?state.getBoolean("attempted"):manage;
        launchWhenReady=state!=null?state.getBoolean("launch"):!manage;
        // A screen on its side with room for two columns puts the panels side
        // by side; a short one (a phone) also tightens and drops the footer.
        android.content.res.Configuration config=getResources().getConfiguration();
        boolean twoColumns=config.orientation==android.content.res.Configuration.ORIENTATION_LANDSCAPE&&config.screenWidthDp>=600;
        compact=twoColumns&&config.screenHeightDp<600;
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackground(look.paper());
        FrameLayout frame=new FrameLayout(this);scroll.addView(frame,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(18),dp(compact?4:18),dp(18),dp(compact?6:0));
        frame.addView(body,new FrameLayout.LayoutParams(Math.min(getResources().getDisplayMetrics().widthPixels,dp(twoColumns?960:520)),-1,Gravity.CENTER_HORIZONTAL));
        scroll.setOnApplyWindowInsetsListener((view,insets)->{view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        // Top bar: where you are, and the options.
        LinearLayout top=new LinearLayout(this);top.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout titles=new LinearLayout(this);titles.setOrientation(LinearLayout.VERTICAL);
        TextView title=look.text("BUNKER",compact?18:22,look.ink);title.setTypeface(null,Typeface.BOLD);title.setLetterSpacing(.28f);titles.addView(title);
        top.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
        Button more=look.outlined("⋮");more.setTextSize(20);more.setLetterSpacing(0);more.setPadding(0,0,0,0);more.setContentDescription("Options");more.setOnClickListener(this::showOptions);
        top.addView(more,new LinearLayout.LayoutParams(dp(compact?36:44),dp(compact?36:44)));
        LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(-1,-2);tp.setMargins(0,0,0,dp(compact?6:20));body.addView(top,tp);
        // [ UPDATE ]: shown when a newer Bunker is released. Two rows: the message with WHAT'S NEW,
        // then UPDATE (or WEB BUILDER when this app can't update itself), LATER and SKIP.
        updatePanel=panel();updatePanel.setVisibility(View.GONE);
        LinearLayout updateLine=new LinearLayout(this);updateLine.setGravity(Gravity.CENTER_VERTICAL);
        updateText=look.monoText("",12,look.ink);updateLine.addView(updateText,new LinearLayout.LayoutParams(0,-2,1));
        TextView notes=look.monoText("WHAT'S NEW ›",11,look.ink);notes.setLetterSpacing(.12f);notes.setTypeface(null,Typeface.BOLD);
        notes.setPadding(dp(8),dp(8),0,dp(8));notes.setOnClickListener(v->{if(Updater.current!=null)openUrl(Updater.current.notes);});
        updateLine.addView(notes);
        LinearLayout.LayoutParams um=new LinearLayout.LayoutParams(-1,-2);um.setMargins(0,dp(2),0,dp(8));updatePanel.addView(updateLine,um);
        LinearLayout actions=new LinearLayout(this);
        updateButton=look.solid("UPDATE");updateButton.setTextSize(13);updateButton.setLetterSpacing(.16f);updateButton.setPadding(dp(8),0,dp(8),0);
        updateButton.setOnClickListener(v->{if(Updater.updating()){if(Updater.cancellable())Updater.cancelled=true;}else startUpdate();});
        updateWeb=look.outlined("WEB BUILDER");updateWeb.setOnClickListener(v->openUrl(Updater.WEB_BUILDER));
        updateLater=look.outlined("LATER");updateLater.setOnClickListener(v->{Updater.later=true;renderUpdate();});
        updateSkip=look.outlined("SKIP");updateSkip.setOnClickListener(v->{if(Updater.current!=null)Updater.skipped(this,Updater.current.version);renderUpdate();});
        for(Button b:new Button[]{updateButton,updateWeb,updateLater,updateSkip}){
            boolean wide=b==updateButton||b==updateWeb;
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(40),wide?2:1);lp.setMargins(0,0,dp(6),dp(4));actions.addView(b,lp);
        }
        ((LinearLayout.LayoutParams)updateSkip.getLayoutParams()).setMargins(0,0,0,dp(4));
        updatePanel.addView(actions);
        LinearLayout.LayoutParams upp=new LinearLayout.LayoutParams(-1,-2);upp.setMargins(0,0,0,dp(compact?12:20));body.addView(updatePanel,upp);
        // [ SYSTEM ]: game files, Lunar Tear and save.
        LinearLayout system=panel();
        files=look.chip();assetButton=look.outlined("CHOOSE");assetButton.setContentDescription("Choose game files");assetButton.setOnClickListener(v->chooseAssets());
        row(system,"GAME FILES",files,look.info("Game files","Choose the resource dump's .7z or its extracted folder. A folder used in place saves space."),assetButton);
        status=look.chip();progress=new ProgressBar(this);progress.setIndeterminateTintList(ColorStateList.valueOf(look.ink));
        row(system,"LUNAR TEAR",status,progress);
        save=look.monoText("",13,look.ink);row(system,"SAVE",save,look.info("Save","Export a save backup (⋮) before uninstalling Bunker or clearing its storage. Import save backup restores one from any device."));
        archiveLine=look.monoText(indexText,13,look.ink);row(system,"ARCHIVE",archiveLine);
        bar=new Look.Segments(look);LinearLayout.LayoutParams barParams=new LinearLayout.LayoutParams(-1,dp(14));barParams.setMargins(0,dp(10),0,dp(6));system.addView(bar,barParams);
        progressText=look.monoText("",12,look.ink);system.addView(progressText);
        // [ PLAY ]: what happens next, and Deploy.
        LinearLayout launch=panel();
        detail=look.monoText("",12,look.ink);LinearLayout.LayoutParams dp1=new LinearLayout.LayoutParams(-1,-2);dp1.setMargins(0,dp(compact?2:6),0,dp(compact?8:12));launch.addView(detail,dp1);
        play=look.solid("DEPLOY  ▶");play.setContentDescription("Deploy: start the game");
        play.setOnClickListener(v->{launchWhenReady=true;autoAttempted=true;if(running){launchWhenReady=false;openGame();}else run(ServerService.START,null);});
        LinearLayout.LayoutParams bp2=new LinearLayout.LayoutParams(-1,dp(compact?48:56));bp2.setMargins(0,0,0,dp(6));launch.addView(play,bp2);
        if(twoColumns){
            // On its side: System on the left; Play and the two programs on the right,
            // both columns ending level. The programs are rows in one panel, each with
            // what it holds, instead of two boxed buttons.
            LinearLayout links=panel();
            pods=link(links,"POD PROGRAMS",v->onOption(8));pods.setContentDescription("Open Pod Programs");
            ((LinearLayout)pods).addView(podsInfo(),((LinearLayout)pods).getChildCount()-1);
            View rule=new View(this);rule.setBackgroundColor(look.line);links.addView(rule,new LinearLayout.LayoutParams(-1,1));
            archive=link(links,"ARCHIVE",v->startActivity(new Intent(this,ArchiveActivity.class)));archive.setContentDescription("Open the Archive");
            LinearLayout left=new LinearLayout(this);left.setOrientation(LinearLayout.VERTICAL);
            LinearLayout right=new LinearLayout(this);right.setOrientation(LinearLayout.VERTICAL);
            block(left,"System",system,0);
            ((LinearLayout.LayoutParams)system.getLayoutParams()).height=0;((LinearLayout.LayoutParams)system.getLayoutParams()).weight=1;
            block(right,"Play",launch,compact?10:20);
            block(right,"Programs",links,0);
            LinearLayout columns=new LinearLayout(this);
            LinearLayout.LayoutParams lc=new LinearLayout.LayoutParams(0,-1,1);lc.setMargins(0,0,dp(18),0);columns.addView(left,lc);
            columns.addView(right,new LinearLayout.LayoutParams(0,-2,1));
            body.addView(columns,new LinearLayout.LayoutParams(-1,-2));
        }else{
            // [ POD PROGRAMS ]: the save editors and content choices, one tap away.
            LinearLayout programs=panel();
            Button podsButton=look.outlined("OPEN  ›");podsButton.setTextSize(13);podsButton.setContentDescription("Open Pod Programs");
            podsButton.setOnClickListener(v->onOption(8));pods=podsButton;
            LinearLayout podsRow=new LinearLayout(this);podsRow.setGravity(Gravity.CENTER_VERTICAL);podsRow.addView(podsButton,new LinearLayout.LayoutParams(0,dp(48),1));
            LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(dp(40),dp(40));ip.setMargins(dp(6),0,0,0);podsRow.addView(podsInfo(),ip);
            LinearLayout.LayoutParams pb=new LinearLayout.LayoutParams(-1,-2);pb.setMargins(0,dp(6),0,dp(6));programs.addView(podsRow,pb);
            // [ ARCHIVE ]: story, records, characters, pictures, movies and music, read from the game files. The game keeps running.
            LinearLayout records=panel();
            Button archiveButton=look.outlined("OPEN  ›");archiveButton.setTextSize(13);archiveButton.setContentDescription("Open the Archive");
            archiveButton.setOnClickListener(v->startActivity(new Intent(this,ArchiveActivity.class)));archive=archiveButton;
            LinearLayout.LayoutParams rb=new LinearLayout.LayoutParams(-1,dp(48));rb.setMargins(0,dp(6),0,dp(6));records.addView(archiveButton,rb);
            block(body,"System",system,20);
            block(body,"Play",launch,20);
            block(body,"Pod Programs",programs,20);
            block(body,"Archive",records,0);
        }
        body.addView(new View(this),new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,-2);fp.setMargins(0,dp(28),0,0);if(!compact)body.addView(look.footer(),fp);
        setContentView(scroll);
        refresh();
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);
        try{FilesStore.recover(this);}catch(Exception e){serverDetail=e.getMessage();}
        new Thread(()->{try{FilesStore.ensureBootstrap(this);}catch(Exception ignored){}runOnUiThread(()->{last="";refresh();});},"bootstrap").start();
        if(state==null&&Updater.INSTALL_RESULT.equals(getIntent().getAction())){Intent result=getIntent();setIntent(new Intent());String message=Updater.installResult(this,result);if(message!=null)updateFailed(message);}
    }
    /** Long-pressing the app icon offers "Bunker menu": this screen, without starting the game. */
    private void addMenuShortcut(){
        android.content.pm.ShortcutManager shortcuts=getSystemService(android.content.pm.ShortcutManager.class);
        if(shortcuts==null)return;
        Intent open=new Intent(this,MainActivity.class).setAction(Intent.ACTION_VIEW).putExtra("manage",true).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        android.content.pm.ShortcutInfo menu=new android.content.pm.ShortcutInfo.Builder(this,"bunker-menu")
            .setShortLabel("Bunker menu").setLongLabel("Open the Bunker menu")
            .setIcon(Look.shortcutEmblem(this)).setIntent(open).build();
        try{shortcuts.setDynamicShortcuts(java.util.Collections.singletonList(menu));}catch(RuntimeException ignored){}  // e.g. rate-limited
    }
    @Override public void onResume(){super.onResume();foreground=true;
        Updater.listener=this::renderUpdate;renderUpdate();Updater.check(this,r->renderUpdate());
        if(awaitingAccess){awaitingAccess=false;if(FilesStore.canUseInPlace())chooseFolder(LINK);}bound=bindService(new Intent(this,ServerService.class),connection,BIND_AUTO_CREATE);handler.post(tick);}
    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);setIntent(intent);
        if(Updater.INSTALL_RESULT.equals(intent.getAction())){
            setIntent(new Intent());  // handled once, not again if the screen is recreated
            String message=Updater.installResult(this,intent);
            if(message!=null)updateFailed(message);
            return;
        }
        boolean manage=intent.getBooleanExtra("manage",false)||!autoDeploy(this);
        autoAttempted=manage;launchWhenReady=!manage;
        query(1);
    }
    @Override public void onPause(){foreground=false;Updater.listener=null;handler.removeCallbacks(tick);if(bound){unbindService(connection);bound=false;service=null;}super.onPause();}
    @Override protected void onSaveInstanceState(Bundle out){out.putBoolean("attempted",autoAttempted);out.putBoolean("launch",launchWhenReady);super.onSaveInstanceState(out);}
    private void refresh(){
        boolean hasAssets=FilesStore.list(this).length()>0,hasMaster=FilesStore.master(this).length()>0,ready=hasAssets&&hasMaster;
        String key=serverState+serverDetail+busy+running+tools+hasAssets+hasMaster+permille;
        if(archiveLine!=null&&!indexText.contentEquals(archiveLine.getText()))archiveLine.setText(indexText);
        // Opened from the game: no launch step checks the index, so check it now (built in the background if needed).
        if(!indexChecked&&!indexing&&!launchWhenReady&&!tools&&FilesStore.ready(this))checkIndex(false);
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
        archive.setEnabled(!busy&&ready);archive.setAlpha(archive.isEnabled()?1f:.45f);
        String message="";
        boolean warning=attention||"Operation cancelled".equals(serverState);
        if(warning)message=serverDetail;
        else if(importing)message="Keep Bunker open until the import finishes.";
        else if(busy&&!"Starting server".equals(serverState)&&!"Stopping".equals(serverState))message=serverDetail;
        else if("Saves exported".equals(serverState)||"Save imported".equals(serverState))message=serverDetail;
        else if(hasAssets&&!hasMaster){message="Import master data from the ⋮ menu.";warning=true;}
        else if(!hasAssets&&FilesStore.linkedFolder(this)!=null){warning=true;message=FilesStore.canUseInPlace()?"Can't find "+FilesStore.linkedFolder(this)+". Put it back or choose the files again.":"Allow All files access for NieR in Settings, or choose the files again.";}
        else if("Server stopped".equals(serverState)&&!serverDetail.isEmpty())message=serverDetail;
        if(message.isEmpty())message=tools?"Close Pod Programs, then tap Deploy.":"";
        detail.setText(warning?"> "+message:message);detail.setVisibility(message.isEmpty()?View.GONE:View.VISIBLE);detail.setTextColor(warning?look.alert:look.ink);
    }
    private void chooseAssets(){
        dialog().setTitle("Choose the game files")
            .setItems(new String[]{"Extracted folder: copy it in","Extracted folder: use in place","Archive (.7z or .zip)"},(dialog,which)->{
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
        if(Build.VERSION.SDK_INT<30){dialog().setTitle("Use in place").setMessage("Needs Android 11 or later. Copy the folder in instead.").setPositiveButton("OK",null).show();return;}
        if(FilesStore.canUseInPlace()){chooseFolder(LINK);return;}
        dialog().setTitle("Allow All files access")
            .setMessage("Turn on the switch in Settings, then come back. NieR reads only the folder you choose. Don't move or delete it afterwards.")
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
        if(running||busy)option(panel,menu,1,busy?"Cancel":"Stop Lunar Tear",true);
        if(running)option(panel,menu,10,"Check Lunar Tear",true);
        section(panel,"Data");
        if(!idle){TextView note=look.monoText("> Stop Lunar Tear first to import or export.",11,look.alert);note.setPadding(0,0,0,dp(4));panel.addView(note);}
        option(panel,menu,2,"Import master data",idle);
        option(panel,menu,3,"Export save backup",idle&&new File(FilesStore.data(this),"game.db").isFile());
        option(panel,menu,9,"Import save backup",idle);
        section(panel,"Support");
        option(panel,menu,4,"Lunar Tear log",true);
        option(panel,menu,11,"Export Lunar Tear log",true);
        option(panel,menu,15,"Auto deploy: "+(autoDeploy(this)?"On":"Off"),true);
        option(panel,menu,12,"Display: "+Character.toUpperCase(Look.display(this).charAt(0))+Look.display(this).substring(1),true);
        option(panel,menu,13,"Check for updates: "+(Updater.enabled(this)?"On":"Off"),true);
        option(panel,menu,14,"Check for updates now",true);
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
        dialog().setTitle("Display").setSingleChoiceItems(new String[]{"System","Light","Dark"},Math.max(0,current),(d,which)->{
            d.dismiss();
            if(which==current)return;
            Look.display(this,modes[which]);
            recreate();
        }).setNegativeButton("Cancel",null).show();
    }
    /** Auto deploy (⋮ menu, on by default): opening Bunker starts Lunar Tear and the game; off, it opens on the launcher. */
    static boolean autoDeploy(Context c){return c.getSharedPreferences("launcher",MODE_PRIVATE).getBoolean("autoDeploy",true);}
    private void onOption(int id){
        switch(id){
            case 15: {boolean on=!autoDeploy(this);getSharedPreferences("launcher",MODE_PRIVATE).edit().putBoolean("autoDeploy",on).apply();
                if(!on){autoAttempted=true;launchWhenReady=false;}   // off now: nothing starts by itself from here
                Toast.makeText(this,on?"The game starts when Bunker opens":"Bunker opens here. Tap Deploy to play.",Toast.LENGTH_SHORT).show();break;}
            case 12: chooseDisplay();break;
            case 13: Updater.enabled(this,!Updater.enabled(this));if(Updater.enabled(this))Updater.recheck(this,r->renderUpdate());break;
            case 14: Updater.recheck(this,r->renderUpdate());Toast.makeText(this,"Checking for updates…",Toast.LENGTH_SHORT).show();break;
            case 1: autoAttempted=true;launchWhenReady=false;run(ServerService.STOP,null);break;
            case 2: {Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(i,MASTER);break;}
            case 3: {Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_TITLE,"lunar-tear-saves-"+new SimpleDateFormat("yyyyMMdd-HHmm",Locale.US).format(new Date())+".zip");startActivityForResult(i,BACKUP);break;}
            case 4: showLog();break;
            case 5: startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName())));break;
            case 6: help();break;
            case 7: dialog().setTitle("Bunker").setMessage("Version "+BuildConfig.BUNKER_VERSION+"\nOffline NieR Re[in]carnation, all in one app.\nCreated by veritr1x · github.com/veritr1x/bunker\n\nCREDITS\nLunar Tear by Walter-Sparrow: the offline server.\nMIT License · Copyright 2026 Ilya Groshev.\nLunar Scripts by Walter-Sparrow: APK and master data patches.\nLunar Base by NMeliksah: the save editors.\nMasterdata Patcher by NavHobbyDev: the content patcher.\nthree.js: the Archive's 3D viewer.\nChaquopy: Python on Android.\nAMD FidelityFX FSR 1 (MIT) and Qualcomm Snapdragon Game Super Resolution (BSD-3-Clause): upscaling.\n\nNieR Re[in]carnation © SQUARE ENIX. Bunker is a fan project, not affiliated with Square Enix.").setNeutralButton("Open GitHub",(d,w)->startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://github.com/veritr1x/bunker")))).setPositiveButton("Close",null).show();break;
            case 9: confirmSaveImport();break;
            case 10: query(3);break;
            case 11: {Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_TITLE,"lunar-tear-log-"+new SimpleDateFormat("yyyyMMdd-HHmm",Locale.US).format(new Date())+".zip");startActivityForResult(i,LOGS);break;}
            case 8: autoAttempted=true;launchWhenReady=false;startActivity(new Intent(this,ToolsActivity.class));break;
        }
    }
    private void confirmSaveImport(){
        dialog().setTitle("Import a save backup?")
            .setMessage("This replaces the save on this device. Your current save is kept as a copy. Choose a backup ZIP or a game.db file.")
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Choose backup",(dialog,which)->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,SAVE);})
            .show();
    }
    private void run(String action,Uri uri){
        Intent intent=new Intent(this,ServerService.class).setAction(action);if(uri!=null)intent.setData(uri);
        // Stopping never puts the service in the foreground, so it must not be started as a foreground service.
        if(ServerService.STOP.equals(action)||ServerService.CLOSE_TOOLS.equals(action))startService(intent);else startForegroundService(intent);
    }
    /**
     * Starts the game, first building the Archive's index when it is missing or
     * out of date (new game files, or an update that indexes more), so the
     * Archive and the pages that name things from it are ready in the game.
     */
    private void launchAfterIndex(){
        if(indexChecked||indexing){if(!indexing)openGame();return;}
        checkIndex(true);
    }
    /** Checks the Archive's index, building it when missing or out of date; with thenOpen, starts the game afterwards. */
    private void checkIndex(boolean thenOpen){
        indexing=true;openedWhileIndexing=false;indexText="CHECKING";archiveLine.setText(indexText);
        final File assets=FilesStore.root(this),data=new File(getFilesDir(),"archive");
        new Thread(()->{
            String done="READY";
            try{
                if(!Python.isStarted())Python.start(new AndroidPlatform(getApplicationContext()));
                com.chaquo.python.PyObject archive=Python.getInstance().getModule("android_archive");
                JSONObject st=new JSONObject(archive.callAttr("build_index",assets.getAbsolutePath(),data.getAbsolutePath()).toString());
                while(st.optBoolean("running")){
                    int total=st.optInt("total"),pct=total>0?Math.min(99,st.optInt("done")*100/total):0;
                    final String line="INDEXING "+pct+"% · "+st.optString("step");
                    indexText=line;
                    Thread.sleep(500);
                    st=new JSONObject(archive.callAttr("index_status",assets.getAbsolutePath(),data.getAbsolutePath()).toString());
                }
                if(!st.optBoolean("possible"))done="NO GAME TEXT";
                else if(!st.optBoolean("ready"))done="NOT BUILT"+(st.optString("error").isEmpty()?"":" · "+st.optString("error"));
            }catch(Exception|LinkageError error){
                android.util.Log.e("LunarTear","Archive index failed",error);
                done="NOT BUILT";
            }
            final String result=done;
            runOnUiThread(()->{
                indexing=false;indexChecked=true;indexText=result;archiveLine.setText(result);
                if(thenOpen&&foreground&&running&&!tools&&!openedWhileIndexing)openGame();
            });
        },"archive-index-check").start();
    }
    private void openGame(){
        if(indexing)openedWhileIndexing=true;
        Intent intent=null;
        try {
            android.content.pm.ApplicationInfo info=getPackageManager().getApplicationInfo(getPackageName(),PackageManager.GET_META_DATA);
            String game=info.metaData==null?null:info.metaData.getString("org.veritr1x.bunker.GAME_ACTIVITY");
            if(game!=null) intent=new Intent().setClassName(this,game);
            else {
                intent=getPackageManager().getLaunchIntentForPackage("com.square_enix.android_googleplay.nierspww");
                if(intent==null)intent=getPackageManager().getLaunchIntentForPackage("com.square_enix.android_googleplay.nierspjp");
            }
        } catch(PackageManager.NameNotFoundException ignored){}
        if(intent==null)dialog().setTitle("Install the Bunker game").setMessage("Install the game built by Bunker. The original game can't connect to Lunar Tear.").setPositiveButton("OK",null).show();
        else {
            String unity=DisplayPatch.unityArguments(this);
            if(unity!=null)intent.putExtra("unity",unity);
            startActivity(intent);
        }
    }
    private void openUrl(String url){
        try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));}catch(ActivityNotFoundException ignored){}
    }
    /** Draws the update panel from Updater's state: the release, and the update's progress or failure. */
    private void renderUpdate(){
        Updater.Release r=Updater.current;
        if(!Updater.shown(this,r)){updatePanel.setVisibility(View.GONE);return;}
        updatePanel.setVisibility(View.VISIBLE);
        boolean running=Updater.updating(),canUpdate=r.offer==Updater.Offer.UPDATE;
        String text="Bunker "+r.version+" is available.";
        if(r.offer==Updater.Offer.WEB_BUILDER)text+="\n> This update needs the web builder.";
        else if(r.offer==Updater.Offer.OWN_KEY)text+="\n> This app uses your own signing key. Rebuild it with the web builder.";
        if(running&&!Updater.status.isEmpty())text=Updater.status;
        else if(Updater.statusFailed)text+="\n> "+Updater.status;
        updateText.setText(text);
        updateText.setTextColor(Updater.statusFailed&&!running?look.alert:look.ink);
        updateButton.setText(running?"CANCEL":"UPDATE");
        // Cancel only while downloading: the build and the installer then finish on their own.
        updateButton.setVisibility(canUpdate&&(!running||Updater.cancellable())?View.VISIBLE:View.GONE);
        updateWeb.setVisibility(!running&&(!canUpdate||Updater.statusFailed)?View.VISIBLE:View.GONE);
        for(Button b:new Button[]{updateLater,updateSkip})b.setVisibility(running?View.GONE:View.VISIBLE);
    }
    private void startUpdate(){
        if(Updater.current==null)return;
        if(!getPackageManager().canRequestPackageInstalls()){
            dialog().setTitle("Allow updates").setMessage("Allow NieR to install apps in Settings, then tap Update again.")
                .setPositiveButton("Open Settings",(d,w)->startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+getPackageName()))))
                .setNegativeButton("Cancel",null).show();
            return;
        }
        Updater.status="";Updater.statusFailed=false;
        Context app=getApplicationContext();
        if(Updater.apply(this,Updater.current,()->{
            for(String action:new String[]{ServerService.CLOSE_TOOLS,ServerService.STOP})app.startService(new Intent(app,ServerService.class).setAction(action));
        }))renderUpdate();
    }
    private void updateFailed(String message){
        Updater.status=message;Updater.statusFailed=true;renderUpdate();
    }
    private void help(){
        dialog().setTitle("Help").setMessage("Lunar Tear, the game's server, runs on this device. No internet needed.\n\nTap the Lunar Tear notification to return here.\n\nIf Samsung pauses Lunar Tear, set Battery usage to Unrestricted in App settings.")
            .setPositiveButton("Close",null).show();
    }
    /** The "i" beside Pod Programs, on either layout. */
    private TextView podsInfo(){return look.info("Pod Programs","Edit your save and choose which events and shops appear. While you play, each change sends the game to its title screen.");}
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
        dialog().setTitle(ok?"Lunar Tear is reachable":"Couldn't reach Lunar Tear").setMessage(text.toString().trim()).setPositiveButton("Close",null).show();
    }
    private void displayLog(String nativeStatus){
        String value;
        try{JSONObject s=new JSONObject(nativeStatus);value=s.optString("logs","No server log yet.");if(value.isEmpty())value="No server log yet.";}
        catch(Throwable e){value="Lunar Tear couldn't load: "+e.getMessage();}
        TextView t=look.monoText(value,12,look.ink);t.setTextIsSelectable(true);t.setPadding(dp(18),dp(12),dp(18),dp(12));ScrollView sc=new ScrollView(this);sc.addView(t);
        dialog().setTitle("Lunar Tear log").setView(sc).setPositiveButton("Close",null).show();
    }
    private void exportLogs(Uri uri){
        String version;try{version=getPackageManager().getPackageInfo(getPackageName(),0).versionName;}catch(Exception e){version="unknown";}
        String info="Bunker "+BuildConfig.BUNKER_VERSION+", package "+getPackageName()+" "+version+"\nAndroid "+Build.VERSION.RELEASE+" (API "+Build.VERSION.SDK_INT+")\nDevice "+Build.MANUFACTURER+" "+Build.MODEL+"\nPort offset "+Ports.offset(this);
        new Thread(()->{
            String error;
            try(ParcelFileDescriptor fd=getContentResolver().openFileDescriptor(uri,"rwt")){
                error=fd==null?"Can't open that file":NativeBridge.exportLogs(FilesStore.logs(this).getAbsolutePath(),fd.getFd(),info);
            }catch(Exception e){error=e.getMessage();}
            String result=error;
            runOnUiThread(()->dialog().setTitle(result==null||result.isEmpty()?"Lunar Tear log exported":"Export failed")
                .setMessage(result==null||result.isEmpty()?"Attach the ZIP when you report a problem. It holds the log and this phone's model and Android version.":result).setPositiveButton("Close",null).show());
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

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
    private static final int ASSETS=10, MASTER=11, BACKUP=12, SAVE=13;
    private static final int INK=0xff303630, MUTED=0xff6a6d63, GREEN=0xff536554;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView status,detail,files;
    private Button assetButton;
    private LinearLayout play;
    private ProgressBar progress,bar;
    private int permille=-1;
    private String last="";
    private boolean running=false,busy=false,tools=false,bound=false,autoAttempted=false,launchWhenReady=true,foreground=false;
    private String serverState="Server stopped",serverDetail="Import your game files to get started.";
    private Messenger service;
    private final Messenger replies=new Messenger(new Handler(Looper.getMainLooper(),message->{
        Bundle b=message.getData();running=b.getBoolean("running");busy=b.getBoolean("busy");tools=b.getBoolean("tools");permille=b.getInt("permille",-1);serverState=b.getString("state","");serverDetail=b.getString("detail","");
        refresh();
        if(message.what==2) displayLog(b.getString("native","{}"));
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
    private int dp(int n){return (int)(n*getResources().getDisplayMetrics().density+.5f);}
    private GradientDrawable shape(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    private TextView text(String value,int size,int color){TextView v=new TextView(this);v.setText(value);v.setTextSize(size);v.setTextColor(color);v.setPadding(0,dp(5),0,dp(5));v.setLineSpacing(dp(3),1);return v;}
    private RippleDrawable surface(int color,int radius){
        return new RippleDrawable(ColorStateList.valueOf(0x18536554),shape(color,radius),shape(Color.WHITE,radius));
    }
    private LinearLayout step(LinearLayout parent,int number,boolean primary){
        LinearLayout row=new LinearLayout(this);row.setGravity(Gravity.CENTER_VERTICAL);row.setPadding(dp(18),dp(18),dp(18),dp(18));row.setMinimumHeight(dp(88));row.setBackground(surface(primary?GREEN:Color.WHITE,20));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,0,0,dp(12));parent.addView(row,p);
        TextView badge=text(String.valueOf(number),18,primary?Color.WHITE:GREEN);badge.setGravity(Gravity.CENTER);badge.setPadding(0,0,0,0);badge.setTypeface(null,Typeface.BOLD);badge.setBackground(shape(primary?0x26ffffff:0xffedf0e8,20));
        row.addView(badge,new LinearLayout.LayoutParams(dp(40),dp(40)));return row;
    }
    private LinearLayout label(LinearLayout row,String title,boolean primary){
        LinearLayout column=new LinearLayout(this);column.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1);p.setMargins(dp(16),0,dp(8),0);row.addView(column,p);
        TextView heading=text(title,18,primary?Color.WHITE:INK);heading.setPadding(0,0,0,0);heading.setTypeface(null,Typeface.BOLD);column.addView(heading);return column;
    }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        autoAttempted=state!=null?state.getBoolean("attempted"):getIntent().getBooleanExtra("manage",false);
        launchWhenReady=state!=null?state.getBoolean("launch"):!getIntent().getBooleanExtra("manage",false);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(0xfff4f1e9);
        FrameLayout frame=new FrameLayout(this);scroll.addView(frame);
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(24),dp(24),dp(24),dp(24));
        FrameLayout.LayoutParams bp=new FrameLayout.LayoutParams(Math.min(getResources().getDisplayMetrics().widthPixels,dp(520)),-2,Gravity.CENTER);frame.addView(body,bp);
        scroll.setOnApplyWindowInsetsListener((view,insets)->{view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        LinearLayout header=new LinearLayout(this);header.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(-1,-2);hp.setMargins(0,0,0,dp(24));body.addView(header,hp);
        TextView title=text("Lunar Tear",28,INK);title.setTypeface(Typeface.create("serif",Typeface.NORMAL));header.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        Button more=new Button(this);more.setText("⋮");more.setTextSize(26);more.setTextColor(INK);more.setPadding(0,0,0,0);more.setMinWidth(0);more.setMinHeight(0);more.setBackground(surface(0x00000000,24));more.setContentDescription("More options");header.addView(more,new LinearLayout.LayoutParams(dp(48),dp(48)));more.setOnClickListener(this::showOptions);
        LinearLayout assets=step(body,1,false);LinearLayout assetLabel=label(assets,"Game files",false);
        files=text("",13,MUTED);files.setPadding(0,dp(4),0,0);assetLabel.addView(files);
        assetButton=new Button(this);assetButton.setText("Choose");assetButton.setAllCaps(false);assetButton.setTextSize(14);assetButton.setTextColor(GREEN);assetButton.setPadding(dp(12),0,dp(12),0);assetButton.setMinWidth(0);assetButton.setMinimumWidth(0);assetButton.setBackground(surface(0xffedf0e8,12));assetButton.setContentDescription("Choose game assets folder");assets.addView(assetButton,new LinearLayout.LayoutParams(-2,dp(48)));assetButton.setOnClickListener(v->chooseAssets());
        LinearLayout server=step(body,2,false);LinearLayout serverLabel=label(server,"Server",false);
        status=text("",13,MUTED);status.setPadding(0,dp(4),0,0);serverLabel.addView(status);
        progress=new ProgressBar(this);progress.setIndeterminateTintList(ColorStateList.valueOf(GREEN));server.addView(progress,new LinearLayout.LayoutParams(dp(24),dp(24)));
        play=step(body,3,true);label(play,"Play",true);play.setContentDescription("3. Play");play.setFocusable(true);play.setOnClickListener(v->{launchWhenReady=true;autoAttempted=true;if(running){launchWhenReady=false;openGame();}else run(ServerService.START,null);});
        TextView arrow=text("›",28,Color.WHITE);arrow.setPadding(0,0,dp(4),0);play.addView(arrow);
        // Present Play as one accessible button, rather than three unrelated labels.
        for(int i=0;i<play.getChildCount();i++)play.getChildAt(i).setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        play.setAccessibilityDelegate(new View.AccessibilityDelegate(){@Override public void onInitializeAccessibilityNodeInfo(View host,android.view.accessibility.AccessibilityNodeInfo info){super.onInitializeAccessibilityNodeInfo(host,info);info.setClassName(Button.class.getName());}});
        detail=text("",13,MUTED);detail.setPadding(dp(4),dp(4),dp(4),0);body.addView(detail);
        bar=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);bar.setMax(1000);bar.setProgressTintList(ColorStateList.valueOf(GREEN));bar.setProgressBackgroundTintList(ColorStateList.valueOf(0xffdcdfd4));bar.setVisibility(View.GONE);
        LinearLayout.LayoutParams barParams=new LinearLayout.LayoutParams(-1,dp(12));barParams.setMargins(dp(4),dp(8),dp(4),0);body.addView(bar,barParams);
        setContentView(scroll);
        refresh();
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);
        try{FilesStore.recover(this);}catch(Exception e){serverDetail=e.getMessage();}
        new Thread(()->{try{FilesStore.ensureBootstrap(this);}catch(Exception ignored){}runOnUiThread(()->{last="";refresh();});},"bootstrap").start();
    }
    @Override public void onResume(){super.onResume();foreground=true;bound=bindService(new Intent(this,ServerService.class),connection,BIND_AUTO_CREATE);handler.post(tick);}
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
        files.setText(importing?"Importing…":hasAssets?"Ready":"Choose assets folder");
        assetButton.setText(hasAssets?"Change":"Choose");assetButton.setVisibility(running?View.GONE:View.VISIBLE);assetButton.setEnabled(!busy&&!running&&!tools);assetButton.setAlpha(assetButton.isEnabled()?1f:.45f);
        status.setText(tools?"Tools open":"Stopping".equals(serverState)&&busy?"Stopping…":running?"Running":"Starting server".equals(serverState)&&busy?"Starting…":ready?"Ready":"Waiting for files");
        boolean measured=importing&&permille>=0;
        // A measured copy shows the bar with time left; anything else, the spinner.
        progress.setVisibility(busy&&!measured?View.VISIBLE:View.GONE);
        bar.setVisibility(measured?View.VISIBLE:View.GONE);
        if(measured)bar.setProgress(permille,true);
        play.setEnabled(!busy&&!tools&&ready);play.setAlpha(play.isEnabled()?1f:.45f);
        String message="";
        if("Needs attention".equals(serverState)||"Operation cancelled".equals(serverState))message=serverDetail;
        else if(busy&&!"Starting server".equals(serverState)&&!"Stopping".equals(serverState))message=serverDetail;
        else if("Saves exported".equals(serverState))message="Backup saved.";
        else if("Save imported".equals(serverState))message=serverDetail;
        else if(hasAssets&&!hasMaster)message="Import master data from the ⋮ menu.";
        else if("Server stopped".equals(serverState)&&!serverDetail.isEmpty()&&!serverDetail.equals("Import your game files to get started.")&&!serverDetail.equals("Tap Play to restart.")&&!serverDetail.equals("Your saves are stored on this phone."))message=serverDetail;
        detail.setText(message);detail.setVisibility(message.isEmpty()?View.GONE:View.VISIBLE);
    }
    private void chooseAssets(){
        Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(i,ASSETS);
    }
    private void showOptions(View anchor){
        PopupMenu popup=new PopupMenu(this,anchor);Menu menu=popup.getMenu();
        menu.add(0,8,0,"Tools").setEnabled(!busy&&FilesStore.ready(this));
        if(running||busy)menu.add(0,1,0,busy?"Cancel operation":"Stop server");
        menu.add(0,2,1,"Import master data").setEnabled(!busy&&!running&&!tools);
        menu.add(0,3,2,"Export save backup").setEnabled(!busy&&!running&&!tools&&new File(FilesStore.data(this),"game.db").isFile());
        menu.add(0,9,2,"Import save backup").setEnabled(!busy&&!running&&!tools);
        menu.add(0,4,3,"Server log");menu.add(0,5,4,"App settings");menu.add(0,6,5,"Help");menu.add(0,7,6,"About");
        popup.setOnMenuItemClickListener(item->{switch(item.getItemId()){
            case 1: autoAttempted=true;launchWhenReady=false;run(ServerService.STOP,null);break;
            case 2: {Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(i,MASTER);break;}
            case 3: {Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_TITLE,"lunar-tear-saves-"+new SimpleDateFormat("yyyyMMdd-HHmm",Locale.US).format(new Date())+".zip");startActivityForResult(i,BACKUP);break;}
            case 4: showLog();break;
            case 5: startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName())));break;
            case 6: help();break;
            case 7: new AlertDialog.Builder(this).setTitle("Lunar Tear").setMessage("Offline companion · 0.1.0\nBased on Lunar Tear by Walter-Sparrow.\nMIT License · Copyright 2026 Ilya Groshev.").setPositiveButton("Close",null).show();break;
            case 9: confirmSaveImport();break;
            case 8: autoAttempted=true;launchWhenReady=false;startActivity(new Intent(this,ToolsActivity.class));break;
            default: return false;
        }return true;});popup.show();
    }
    private void confirmSaveImport(){
        new AlertDialog.Builder(this).setTitle("Import a save backup?")
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
        if(intent==null)new AlertDialog.Builder(this).setTitle("Install the patched game").setMessage("Install the APK patched for 127.0.0.1. The original game APK cannot connect to this server.").setPositiveButton("OK",null).show();
        else startActivity(intent);
    }
    private void help(){
        new AlertDialog.Builder(this).setTitle("Help").setMessage("Choose the extracted assets folder once. Master data is already included. The server starts and the game opens automatically when your files are ready.\n\nTap the server notification to return here. Stop the server from ⋮ before changing files or exporting saves. Export a backup before uninstalling or clearing app storage. Import save backup restores one, from this phone, another phone or an iPhone.\n\nIf Samsung pauses the server, set Battery usage to Unrestricted in App settings.")
            .setPositiveButton("Close",null).show();
    }
    private void showLog(){query(2);}
    private void displayLog(String nativeStatus){
        String value;
        try{JSONObject s=new JSONObject(nativeStatus);value=s.optString("logs","No server log yet.");if(value.isEmpty())value="No server log yet.";}
        catch(Throwable e){value="Unable to load native server: "+e.getMessage();}
        TextView t=text(value,12,INK);t.setTypeface(Typeface.MONOSPACE);t.setTextIsSelectable(true);t.setPadding(dp(18),dp(12),dp(18),dp(12));ScrollView sc=new ScrollView(this);sc.addView(t);
        new AlertDialog.Builder(this).setTitle("Server log").setView(sc).setPositiveButton("Close",null).show();
    }
    @Override protected void onActivityResult(int code,int result,Intent data){
        super.onActivityResult(code,result,data);if(result!=RESULT_OK||data==null||data.getData()==null)return;
        Uri uri=data.getData();
        if(code==ASSETS||code==MASTER){try{getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(SecurityException ignored){}}
        if(code==ASSETS)run(ServerService.ASSETS,uri);else if(code==MASTER)run(ServerService.MASTER,uri);else if(code==BACKUP)run(ServerService.BACKUP,uri);else if(code==SAVE)run(ServerService.SAVE,uri);
    }
}

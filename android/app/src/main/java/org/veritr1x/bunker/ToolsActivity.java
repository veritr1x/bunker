package org.veritr1x.bunker;

import android.app.Activity;
import android.content.*;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.view.*;
import android.webkit.*;
import android.widget.*;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

/** Private, on-device tools. Runs beside the service so Unity can fully close. */
public final class ToolsActivity extends Activity {
    private static boolean webInitialized;
    /** Pod Programs' WebView profile; its folder can be set only once per process. */
    static synchronized void initWebView(){if(!webInitialized){WebView.setDataDirectorySuffix("lunar_tools");webInitialized=true;}}
    private final Handler handler=new Handler(Looper.getMainLooper());
    private WebView web;
    private TextView message;
    private Button close;
    private boolean bound,closing,loaded;
    private String origin="",download="";
    /** A phone on its side: no top bar or system bars, and the page runs under the camera hole. */
    private boolean compact;
    /** Where the camera hole is, for the page (BunkerShell.cutout(), base.html): JSON, or null. */
    private volatile String cutout="null";
    private ValueCallback<Uri[]> upload;
    private final ServiceConnection connection=new ServiceConnection(){
        public void onServiceConnected(ComponentName name,IBinder binder){}
        public void onServiceDisconnected(ComponentName name){message.setText("> Pod Programs stopped. Close it and open it again.");web.setVisibility(View.GONE);message.setVisibility(View.VISIBLE);}
    };
    private final Runnable poll=new Runnable(){public void run(){
        if(closing&&!ServerService.busy&&!ServerService.tools){returnToLauncher();return;}
        if(!closing&&ServerService.tools&&!ServerService.busy&&!ToolsRuntime.url.isEmpty()&&!loaded){
            loaded=true;origin=ToolsRuntime.url;
            // WebView takes light or dark from the game's theme, not the phone; tell the page instead.
            CookieManager.getInstance().setCookie(origin,"lunar_theme="+(look.dark?"dark":"light")+"; Path=/; SameSite=Strict");
            CookieManager.getInstance().setCookie(origin,"lunar_tools="+ToolsRuntime.token+"; Path=/; HttpOnly; SameSite=Strict",ok->web.loadUrl(origin+"/"));
        }
        if(!loaded||closing)message.setText(ServerService.detail);
        if(loaded&&!ServerService.tools&&!ServerService.busy&&!closing){loaded=false;web.setVisibility(View.GONE);message.setVisibility(View.VISIBLE);message.setText("> Pod Programs closed. Return to Bunker.");}
        handler.postDelayed(this,300);
    }};
    private Look look;
    private int dp(int n){return look.dp(n);}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        look=Look.of(this);look.apply(this);
        if(Build.VERSION.SDK_INT>=33)getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,this::back);
        initWebView();
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setBackground(look.paper());
        // The same top bar as the Bunker: where you are, and the way back. On a
        // phone on its side (the pages' own test: automata.css) the page has the
        // whole screen instead: no top bar, the system bars hidden until a swipe,
        // and the window under the camera hole, whose place the page is told so
        // its tabs step around it. The page's tab column carries the title and
        // Close (/bunker/close) then.
        android.content.res.Configuration config=getResources().getConfiguration();
        compact=config.orientation==android.content.res.Configuration.ORIENTATION_LANDSCAPE&&config.screenHeightDp<600;
        if(compact){WindowManager.LayoutParams attrs=getWindow().getAttributes();attrs.layoutInDisplayCutoutMode=WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;getWindow().setAttributes(attrs);}
        body.setOnApplyWindowInsetsListener((view,insets)->{
            if(compact){view.setPadding(0,0,0,0);hole(insets);}
            else view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets;
        });
        LinearLayout bar=new LinearLayout(this);bar.setPadding(dp(18),dp(12),dp(18),dp(4));bar.setGravity(Gravity.CENTER_VERTICAL);body.addView(bar);if(compact)bar.setVisibility(View.GONE);
        LinearLayout titles=new LinearLayout(this);titles.setOrientation(LinearLayout.VERTICAL);
        TextView caption=look.monoText("BUNKER // POD 042",10,look.mid);caption.setLetterSpacing(.2f);titles.addView(caption);
        TextView title=look.text("POD PROGRAMS",22,look.ink);title.setTypeface(null,android.graphics.Typeface.BOLD);title.setLetterSpacing(.28f);titles.addView(title);
        bar.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
        close=look.outlined("CLOSE");close.setPadding(dp(16),0,dp(16),0);close.setOnClickListener(v->closeTools());bar.addView(close,new LinearLayout.LayoutParams(-2,dp(44)));
        message=look.monoText("> Opening Pod Programs…",13,look.ink);message.setGravity(Gravity.CENTER);message.setPadding(dp(24),dp(24),dp(24),dp(24));body.addView(message,new LinearLayout.LayoutParams(-1,0,1));
        web=new WebView(this);web.setBackgroundColor(look.paper);web.setVisibility(View.GONE);body.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        web.addJavascriptInterface(new Object(){@JavascriptInterface public String cutout(){return cutout;}},"BunkerShell");
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                // A timeline bar: open the Archive on that summon or event (ArchiveLinks); Back returns here.
                String archive=ArchiveLinks.path(request.getUrl().toString());
                if(archive!=null){startActivity(new Intent(ToolsActivity.this,ArchiveActivity.class).putExtra(ArchiveActivity.PATH,archive));return true;}
                // The page's own Close (a phone on its side): the same as the CLOSE button.
                if(local(request.getUrl().toString())&&"/bunker/close".equals(request.getUrl().getPath())){closeTools();return true;}
                return !local(request.getUrl().toString());
            }
            @Override public void onPageFinished(WebView view,String url){if(!closing&&local(url)){message.setVisibility(View.GONE);web.setVisibility(View.VISIBLE);}}
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame()){message.setText("> Couldn't open Pod Programs. Close it and try again.");message.setVisibility(View.VISIBLE);}}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(upload!=null)upload.onReceiveValue(null);upload=callback;
                try{startActivityForResult(params.createIntent(),30);}catch(ActivityNotFoundException e){upload.onReceiveValue(null);upload=null;}
                return true;
            }
        });
        web.setDownloadListener((url,userAgent,disposition,mime,length)->{
            if(!local(url))return;download=url;
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType(mime==null?"application/octet-stream":mime).addCategory(Intent.CATEGORY_OPENABLE);
            intent.putExtra(Intent.EXTRA_TITLE,URLUtil.guessFileName(url,disposition,mime));startActivityForResult(intent,31);
        });
        setContentView(body);
        if(compact)hideBars();
        bound=bindService(new Intent(this,ServerService.class),connection,BIND_AUTO_CREATE);
        startForegroundService(new Intent(this,ServerService.class).setAction(ServerService.TOOLS));
        handler.postDelayed(poll,300);
    }
    /** The system bars stay hidden; a swipe from the edge shows them for a moment. */
    private void hideBars(){
        if(Build.VERSION.SDK_INT>=30){
            getWindow().setDecorFitsSystemWindows(false);
            WindowInsetsController bars=getWindow().getInsetsController();
            if(bars!=null){bars.hide(WindowInsets.Type.systemBars());bars.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);}
        }else getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            |View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }
    @Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(focused&&compact)hideBars();}
    /** The camera hole on the left or right edge, in the page's CSS px; the page asks for it (base.html). */
    private void hole(WindowInsets insets){
        String json=Look.cutout(insets,getResources().getDisplayMetrics().density);
        if(json.equals(cutout))return;
        cutout=json;
        // A phone turned from one side to the other keeps the page; tell it.
        if(web!=null)web.evaluateJavascript("window.bunkerHoleChanged&&bunkerHoleChanged()",null);
    }
    private boolean local(String url){return !origin.isEmpty()&&(url.equals(origin)||url.startsWith(origin+"/"));}
    private void closeTools(){
        if(closing)return;closing=true;close.setEnabled(false);message.setText("> Closing Pod Programs…");web.setVisibility(View.GONE);message.setVisibility(View.VISIBLE);
        startService(new Intent(this,ServerService.class).setAction(ServerService.CLOSE_TOOLS));
    }
    private void returnToLauncher(){
        // Python and WebView cannot be unloaded, and this process serves the game next. When the server
        // was stopped for a change, the launcher reopens in a fresh process; when the game played on,
        // this process still serves it and stays.
        if(com.chaquo.python.Python.isStarted()&&!ServerService.running)RestartActivity.restart(this);
        else startActivity(new Intent(this,MainActivity.class).putExtra("manage",true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP));
        finish();
    }
    private void back(){if(!closing&&web.canGoBack())web.goBack();else closeTools();}
    @android.annotation.SuppressLint("GestureBackNavigation") // API 33+ uses the dispatcher registered above.
    @Override public void onBackPressed(){back();}
    @Override protected void onDestroy(){
        handler.removeCallbacks(poll);if(upload!=null)upload.onReceiveValue(null);if(bound)unbindService(connection);web.destroy();super.onDestroy();
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request==30&&upload!=null){upload.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result,data));upload=null;}
        if(request==31&&result==RESULT_OK&&data!=null&&data.getData()!=null){
            final Uri target=data.getData();final String source=download,cookie=CookieManager.getInstance().getCookie(origin);
            close.setEnabled(false);
            new Thread(()->{
                String feedback="Exported.";HttpURLConnection connection=null;
                try{
                    connection=(HttpURLConnection)new URL(source).openConnection();connection.setRequestProperty("Cookie",cookie);connection.setConnectTimeout(15000);connection.setReadTimeout(60000);
                    if(connection.getResponseCode()!=200)throw new IOException("Export failed");
                    try(InputStream in=connection.getInputStream();OutputStream out=getContentResolver().openOutputStream(target)){if(out==null)throw new IOException("Cannot write file");byte[] bytes=new byte[65536];int count;while((count=in.read(bytes))!=-1)out.write(bytes,0,count);}
                }catch(Exception error){feedback="Export failed: "+error.getMessage();}finally{if(connection!=null)connection.disconnect();}
                final String text=feedback;runOnUiThread(()->{close.setEnabled(true);Toast.makeText(this,text,Toast.LENGTH_LONG).show();});
            },"tools-export").start();
        }
    }
}

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

/** Private, on-device tools. Runs beside the service so Unity can fully close. */
public final class ToolsActivity extends Activity {
    private static boolean webInitialized;
    /** Pod Programs and the Archive share one WebView profile; its folder can be set only once per process. */
    static synchronized void initWebView(){if(!webInitialized){WebView.setDataDirectorySuffix("lunar_tools");webInitialized=true;}}
    private final Handler handler=new Handler(Looper.getMainLooper());
    private WebView web;
    private TextView message;
    private Button close;
    private boolean bound,closing,loaded;
    private String origin="",download="";
    private ValueCallback<Uri[]> upload;
    private final ServiceConnection connection=new ServiceConnection(){
        public void onServiceConnected(ComponentName name,IBinder binder){}
        public void onServiceDisconnected(ComponentName name){message.setText("> Pod Programs stopped. Close and reopen to retry.");web.setVisibility(View.GONE);message.setVisibility(View.VISIBLE);}
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
        if(loaded&&!ServerService.tools&&!ServerService.busy&&!closing){loaded=false;web.setVisibility(View.GONE);message.setVisibility(View.VISIBLE);message.setText("> Pod Programs closed. Return to the Bunker.");}
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
        body.setOnApplyWindowInsetsListener((view,insets)->{view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        // The same top bar as the Bunker: where you are, and the way back.
        LinearLayout bar=new LinearLayout(this);bar.setPadding(dp(18),dp(12),dp(18),dp(4));bar.setGravity(Gravity.CENTER_VERTICAL);body.addView(bar);
        LinearLayout titles=new LinearLayout(this);titles.setOrientation(LinearLayout.VERTICAL);
        TextView caption=look.monoText("BUNKER // POD 042",10,look.mid);caption.setLetterSpacing(.2f);titles.addView(caption);
        TextView title=look.text("POD PROGRAMS",22,look.ink);title.setTypeface(null,android.graphics.Typeface.BOLD);title.setLetterSpacing(.28f);titles.addView(title);
        bar.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
        close=look.outlined("CLOSE");close.setPadding(dp(16),0,dp(16),0);close.setOnClickListener(v->closeTools());bar.addView(close,new LinearLayout.LayoutParams(-2,dp(44)));
        message=look.monoText("> Opening Pod Programs…",13,look.ink);message.setGravity(Gravity.CENTER);message.setPadding(dp(24),dp(24),dp(24),dp(24));body.addView(message,new LinearLayout.LayoutParams(-1,0,1));
        web=new WebView(this);web.setBackgroundColor(look.paper);web.setVisibility(View.GONE);body.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !local(request.getUrl().toString());}
            @Override public void onPageFinished(WebView view,String url){if(!closing&&local(url)){message.setVisibility(View.GONE);web.setVisibility(View.VISIBLE);}}
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame()){message.setText("> Unable to open Pod Programs. Close and try again.");message.setVisibility(View.VISIBLE);}}
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
        bound=bindService(new Intent(this,ServerService.class),connection,BIND_AUTO_CREATE);
        startForegroundService(new Intent(this,ServerService.class).setAction(ServerService.TOOLS));
        handler.postDelayed(poll,300);
    }
    private boolean local(String url){return !origin.isEmpty()&&(url.equals(origin)||url.startsWith(origin+"/"));}
    private void closeTools(){
        if(closing)return;closing=true;close.setEnabled(false);message.setText("> Closing Pod Programs…");web.setVisibility(View.GONE);message.setVisibility(View.VISIBLE);
        startService(new Intent(this,ServerService.class).setAction(ServerService.CLOSE_TOOLS));
    }
    private void returnToLauncher(){
        startActivity(new Intent(this,MainActivity.class).putExtra("manage",true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP));finish();
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

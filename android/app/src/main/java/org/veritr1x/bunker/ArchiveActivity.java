package org.veritr1x.bunker;

import android.app.Activity;
import android.content.Intent;
import android.os.*;
import android.view.*;
import android.webkit.*;
import android.widget.*;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONObject;
import java.io.File;

/** The Archive: story, records, characters, pictures, movies and music from the imported game files. Read only, so the game keeps running. */
public final class ArchiveActivity extends Activity {
    private WebView web;
    private TextView message;
    private FrameLayout stage;
    private View fullscreen;
    private WebChromeClient.CustomViewCallback exitFullscreen;
    private String origin="";
    private Look look;
    private int dp(int n){return look.dp(n);}
    private static final int SAVE=1;
    private byte[] pending;

    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        look=Look.of(this);look.apply(this);
        if(Build.VERSION.SDK_INT>=33)getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,this::back);
        ToolsActivity.initWebView();
        stage=new FrameLayout(this);
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setBackground(look.paper());
        stage.addView(body,new FrameLayout.LayoutParams(-1,-1));
        stage.setOnApplyWindowInsetsListener((view,insets)->{body.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        // The Bunker's top bar: where you are, and the way back.
        LinearLayout bar=new LinearLayout(this);bar.setPadding(dp(18),dp(12),dp(18),dp(4));bar.setGravity(Gravity.CENTER_VERTICAL);body.addView(bar);
        LinearLayout titles=new LinearLayout(this);titles.setOrientation(LinearLayout.VERTICAL);
        TextView caption=look.monoText("BUNKER // ARCHIVE",10,look.mid);caption.setLetterSpacing(.2f);titles.addView(caption);
        TextView title=look.text("ARCHIVE",22,look.ink);title.setTypeface(null,android.graphics.Typeface.BOLD);title.setLetterSpacing(.28f);titles.addView(title);
        bar.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
        Button close=look.outlined("CLOSE");close.setPadding(dp(16),0,dp(16),0);close.setOnClickListener(v->finish());bar.addView(close,new LinearLayout.LayoutParams(-2,dp(44)));
        message=look.monoText("> Opening the Archive…",13,look.ink);message.setGravity(Gravity.CENTER);message.setPadding(dp(24),dp(24),dp(24),dp(24));body.addView(message,new LinearLayout.LayoutParams(-1,0,1));
        web=new WebView(this);web.setBackgroundColor(look.paper);web.setVisibility(View.GONE);body.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setMediaPlaybackRequiresUserGesture(false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !local(request.getUrl().toString());}
            @Override public void onPageFinished(WebView view,String url){if(local(url)){message.setVisibility(View.GONE);web.setVisibility(View.VISIBLE);}}
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())show("> Unable to open the Archive. Close and try again.");}
        });
        // Pictures from the page ("Save PNG", the 3D snapshot) go where the user picks; WebView ignores download links.
        web.addJavascriptInterface(new Object(){
            @JavascriptInterface public void savePng(String name,String dataUrl){
                byte[] png;
                try{png=android.util.Base64.decode(dataUrl.substring(dataUrl.indexOf(',')+1),android.util.Base64.DEFAULT);}catch(IllegalArgumentException e){return;}
                if(png.length<8||png[0]!=(byte)0x89||png[1]!='P'||png[2]!='N'||png[3]!='G')return;
                String file=name.replaceAll("[^A-Za-z0-9._-]","_");if(!file.endsWith(".png"))file+=".png";
                final String title=file;
                runOnUiThread(()->{
                    if(isFinishing())return;
                    pending=png;
                    startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/png").putExtra(Intent.EXTRA_TITLE,title),SAVE);
                });
            }
        },"bunkerFiles");
        // Movies can go full screen.
        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onShowCustomView(View view,CustomViewCallback callback){
                if(fullscreen!=null){callback.onCustomViewHidden();return;}
                fullscreen=view;exitFullscreen=callback;view.setBackgroundColor(0xff000000);stage.addView(view,new FrameLayout.LayoutParams(-1,-1));
            }
            @Override public void onHideCustomView(){leaveFullscreen();}
        });
        setContentView(stage);
        final File assets=FilesStore.root(this),data=new File(getFilesDir(),"archive");
        new Thread(()->{
            try{
                if(!Python.isStarted())Python.start(new AndroidPlatform(getApplicationContext()));
                JSONObject server=new JSONObject(Python.getInstance().getModule("android_archive").callAttr("start",assets.getAbsolutePath(),data.getAbsolutePath()).toString());
                final String url=server.getString("url"),token=server.getString("token");
                runOnUiThread(()->{
                    if(isFinishing())return;
                    origin=url;
                    // WebView takes light or dark from the app's theme, not the launcher's choice; tell the page.
                    CookieManager.getInstance().setCookie(origin,"lunar_theme="+(look.dark?"dark":"light")+"; Path=/; SameSite=Strict");
                    CookieManager.getInstance().setCookie(origin,"lunar_archive="+token+"; Path=/; HttpOnly; SameSite=Strict",ok->web.loadUrl(origin+"/"));
                });
            }catch(Exception|LinkageError error){
                android.util.Log.e("LunarTear","Archive startup failed",error);
                runOnUiThread(()->show("> The Archive could not start: "+(error.getMessage()==null?error.toString():error.getMessage())));
            }
        },"archive-start").start();
    }
    private void show(String text){message.setText(text);message.setVisibility(View.VISIBLE);web.setVisibility(View.GONE);}
    private boolean local(String url){return !origin.isEmpty()&&(url.equals(origin)||url.startsWith(origin+"/"));}
    private void leaveFullscreen(){
        if(fullscreen==null)return;
        stage.removeView(fullscreen);fullscreen=null;
        if(exitFullscreen!=null)exitFullscreen.onCustomViewHidden();exitFullscreen=null;
    }
    private void back(){if(fullscreen!=null)leaveFullscreen();else if(web.canGoBack())web.goBack();else finish();}
    @android.annotation.SuppressLint("GestureBackNavigation") // API 33+ uses the dispatcher registered above.
    @Override public void onBackPressed(){back();}
    @Override protected void onActivityResult(int code,int result,Intent data){
        super.onActivityResult(code,result,data);
        if(code!=SAVE)return;
        final byte[] png=pending;pending=null;
        if(result!=RESULT_OK||data==null||data.getData()==null||png==null)return;
        try(java.io.OutputStream out=getContentResolver().openOutputStream(data.getData())){
            out.write(png);
            Toast.makeText(this,"Picture saved",Toast.LENGTH_SHORT).show();
        }catch(Exception e){Toast.makeText(this,"The picture could not be saved",Toast.LENGTH_LONG).show();}
    }
    @Override protected void onPause(){super.onPause();web.onPause();}
    @Override protected void onResume(){super.onResume();web.onResume();}
    @Override protected void onDestroy(){
        web.destroy();
        // The server reads only; stopping it just frees memory.
        if(isFinishing()&&Python.isStarted())new Thread(()->Python.getInstance().getModule("android_archive").callAttr("stop"),"archive-stop").start();
        super.onDestroy();
    }
}

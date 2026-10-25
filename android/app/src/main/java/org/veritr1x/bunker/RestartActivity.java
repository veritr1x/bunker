package org.veritr1x.bunker;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Intent;
import android.os.*;
import android.os.Process;

/** Reopens the launcher in a fresh server process. Pod Programs loads Python and WebView, which cannot be
 *  unloaded, into the process that serves the game next; once it closes, this ends that process from its own
 *  and starts the launcher when it has gone (one started before would go with it). */
public final class RestartActivity extends Activity {
    static void restart(Activity from) {
        from.startActivity(new Intent(from,RestartActivity.class).putExtra("pid",Process.myPid()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
    }
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        final int pid=getIntent().getIntExtra("pid",0);
        new Thread(()->{
            if(pid!=0&&pid!=Process.myPid()){
                Process.killProcess(pid);
                ActivityManager manager=getSystemService(ActivityManager.class);
                for(int i=0;i<50&&alive(manager,pid);i++)SystemClock.sleep(100);
            }
            runOnUiThread(()->{
                startActivity(new Intent(this,MainActivity.class).putExtra("manage",true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
                finish();
                overridePendingTransition(0,0);
                new Handler(Looper.getMainLooper()).postDelayed(()->Process.killProcess(Process.myPid()),1000);
            });
        },"restart").start();
    }
    private static boolean alive(ActivityManager manager,int pid) {
        java.util.List<ActivityManager.RunningAppProcessInfo> processes=manager.getRunningAppProcesses();
        if(processes!=null)for(ActivityManager.RunningAppProcessInfo p:processes)if(p.pid==pid)return true;
        return false;
    }
}

package org.lunartear.companion;

import android.content.Context;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONObject;
import java.io.*;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;

public final class ToolsRuntime {
    static volatile String url="",token="";
    public interface Reporter { void report(String message); }
    private ToolsRuntime() {}
    static void start(Context context,Reporter reporter) throws Exception {
        File directory=new File(context.getFilesDir(),"tools");
        File patcher=new File(directory,"patcher");Files.createDirectories(patcher.toPath());
        File origin=new File(patcher,"origin.bin.e");
        if(!origin.exists()) {
            File pending=new File(patcher,"origin.pending");
            try(InputStream in=context.getAssets().open("lunar/original-master.bin.e")) {
                Files.copy(in,pending.toPath(),StandardCopyOption.REPLACE_EXISTING);
                Files.move(pending.toPath(),origin.toPath(),StandardCopyOption.ATOMIC_MOVE);
            } catch(FileNotFoundException ignored) { /* Own builds may import the original in Tools. */ }
        }
        if(!Python.isStarted())Python.start(new AndroidPlatform(context));
        String result=Python.getInstance().getModule("android_runtime").callAttr("start",FilesStore.data(context).getAbsolutePath(),FilesStore.root(context).getAbsolutePath(),directory.getAbsolutePath(),reporter).toString();
        JSONObject state=new JSONObject(result);url=state.getString("url");token=state.getString("token");
    }
    static void stop(){
        if(Python.isStarted())Python.getInstance().getModule("android_runtime").callAttr("stop");
        url="";token="";
    }
}

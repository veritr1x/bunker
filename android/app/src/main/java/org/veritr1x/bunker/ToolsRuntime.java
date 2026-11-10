package org.veritr1x.bunker;

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
    static File directory(Context context) { return new File(context.getFilesDir(),"tools"); }
    /** Before the server starts: the game data for this build, the calendar's or a preset's, once per version (DataUpdate). */
    static void updateData(Context context) {
        File data=FilesStore.data(context);
        if(!DataUpdate.needed(data,directory(context),BuildConfig.BUNKER_VERSION))return;
        if(!Python.isStarted())Python.start(new AndroidPlatform(context));
        Python.getInstance().getModule("android_runtime").callAttr("update_data",data.getAbsolutePath(),FilesStore.root(context).getAbsolutePath(),directory(context).getAbsolutePath(),BuildConfig.BUNKER_VERSION);
    }
    /** After master data is imported here (⋮ menu): its layers, Mods › Challenges and the language pack's texts
     *  (android_challenges), which Pod Programs would otherwise add only at its next change. A failure leaves
     *  the imported game data as it is: the game still starts, its texts in English. */
    static void layerGameData(Context context) {
        try {
            if(!Python.isStarted())Python.start(new AndroidPlatform(context));
            Python.getInstance().getModule("android_runtime").callAttr("layer_game_data",FilesStore.data(context).getAbsolutePath(),FilesStore.root(context).getAbsolutePath(),directory(context).getAbsolutePath());
        } catch(Exception|LinkageError error) { android.util.Log.e("LunarTear","Game data layers not applied",error); }
    }
    static void stop(){
        if(Python.isStarted())Python.getInstance().getModule("android_runtime").callAttr("stop");
        url="";token="";
    }
}

package org.lunartear.companion;

import android.test.InstrumentationTestCase;
import java.io.*;
import java.net.*;
import org.json.JSONObject;

/** Real ARM64 JNI / SQLite / migration / HTTP tests. The tiny test catalog is
 * intentionally incomplete: these checks do not claim gameplay validation. */
public final class NativeSmokeTest extends InstrumentationTestCase {
    public void testNativeServerLifecycle() throws Exception {
        File base=new File(getInstrumentation().getTargetContext().getCacheDir(),"native-smoke");
        FilesStore.delete(base);FilesStore.mkdir(base);
        File data=new File(base,"saves"), root=new File(base,"server");
        try {
            assertEquals("",NativeBridge.checkDatabase(data.getAbsolutePath()));
            String missing=NativeBridge.start(data.getAbsolutePath(),root.getAbsolutePath());
            assertTrue(missing.contains("master data"));
            File master=new File(root,"assets/release/"+FilesStore.MASTER);FilesStore.mkdir(master.getParentFile());
            try(InputStream in=getInstrumentation().getTargetContext().getAssets().open("lunar/"+FilesStore.MASTER);FileOutputStream out=new FileOutputStream(master)) {
                byte[] bytes=new byte[65536];int n;while((n=in.read(bytes))!=-1)out.write(bytes,0,n);
            }
            File index=new File(root,"assets/revisions/0/android/list.bin");FilesStore.mkdir(index.getParentFile());
            try(FileOutputStream out=new FileOutputStream(index)){out.write(new byte[]{8,1});}
            for(int iteration=0;iteration<2;iteration++) {
                assertEquals("",NativeBridge.start(data.getAbsolutePath(),root.getAbsolutePath()));
                assertEquals("running",new JSONObject(NativeBridge.status()).getString("state"));
                assertFalse(NativeBridge.prepareBackup(data.getAbsolutePath()).isEmpty());
                for(String url:new String[]{"http://127.0.0.1:8080/companion/health","http://127.0.0.1:3000/v18.0/dialog/oauth"}) {
                    HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setConnectTimeout(5000);c.setReadTimeout(5000);
                    try{assertEquals(200,c.getResponseCode());}finally{c.disconnect();}
                }
                NativeBridge.stop();
                assertEquals("",NativeBridge.prepareBackup(data.getAbsolutePath()));
                assertEquals("stopped",new JSONObject(NativeBridge.status()).getString("state"));
                for(int port:new int[]{8003,8080,3000})try(ServerSocket s=new ServerSocket()){s.bind(new InetSocketAddress("127.0.0.1",port));}
            }
            assertTrue(new File(data,"game.db").length()>0);
            assertTrue(new File(data,"auth.key").length()>0);
        } finally {NativeBridge.stop();FilesStore.delete(base);}
    }
}

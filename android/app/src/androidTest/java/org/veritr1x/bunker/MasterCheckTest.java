package org.veritr1x.bunker;

import android.test.InstrumentationTestCase;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/** Import master data takes only master data: through the bridge, as the import calls it. */
public final class MasterCheckTest extends InstrumentationTestCase {
    private File write(String name, byte[] data) throws Exception {
        File f = new File(getInstrumentation().getTargetContext().getCacheDir(), name);
        try (OutputStream out = new FileOutputStream(f)) { out.write(data); }
        return f;
    }

    public void testRefusesOtherFiles() throws Exception {
        File text = write("notes.txt", "not master data".getBytes());
        assertTrue(NativeBridge.checkMaster(text.getPath(), "notes.txt").contains("20240404193219.bin.e"));
        assertTrue(NativeBridge.checkMaster(text.getPath(), "fake.bin.e").contains("isn't NieR Re[in]carnation master data"));
        assertFalse(NativeBridge.checkMaster(text.getPath(), "").isEmpty());
    }

    public void testAcceptsTheBundledMasterData() throws Exception {
        File copy = new File(getInstrumentation().getTargetContext().getCacheDir(), "master.bin.e");
        try (InputStream in = getInstrumentation().getTargetContext().getAssets().open("lunar/" + FilesStore.MASTER);
             OutputStream out = new FileOutputStream(copy)) {
            byte[] buffer = new byte[65536]; int n;
            while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
        }
        assertEquals("", NativeBridge.checkMaster(copy.getPath(), FilesStore.MASTER));
    }
}

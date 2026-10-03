package org.lunartear.companion;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.SystemClock;
import android.provider.DocumentsContract;
import android.text.format.Formatter;
import java.io.*;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

final class FilesStore {
    static final String MASTER = "20240404193219.bin.e";
    interface Progress {
        void update(String text);
        boolean cancelled();
        /** Share of the copy finished, 0-1000, or -1 while the total is unknown. */
        default void fraction(int permille) {}
    }
    static File root(Context c) { return new File(c.getFilesDir(), "server"); }
    static File data(Context c) { return new File(c.getFilesDir(), "saves"); }
    static File assets(Context c) { return new File(root(c), "assets"); }
    static File master(Context c) { return new File(assets(c), "release/" + MASTER); }
    static File list(Context c) {
        File f = new File(assets(c), "revisions/0/android/list.bin");
        return f.isFile() ? f : new File(assets(c), "revisions/0/list.bin");
    }
    static boolean ready(Context c) { return master(c).length() > 0 && list(c).length() > 0; }
    static void ensureBootstrap(Context c) throws IOException {
        if(master(c).length()>0)return;
        mkdir(master(c).getParentFile());
        File tmp=File.createTempFile("bootstrap-",".tmp",master(c).getParentFile());
        try(InputStream in=c.getAssets().open("lunar/"+MASTER);FileOutputStream out=new FileOutputStream(tmp)) {
            byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);out.getFD().sync();
            if(master(c).length()==0)move(tmp,master(c));
        } finally {tmp.delete();}
    }
    static void mkdir(File f) throws IOException { if (!f.isDirectory() && !f.mkdirs()) throw new IOException("Cannot create " + f.getName()); }
    static void move(File from, File to) throws IOException {
        Files.move(from.toPath(), to.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }
    // All writes go to private staging locations. A failed import leaves the
    // existing installation and saves intact, including on provider disconnect.
    static void importMaster(Context c, Uri uri, Progress progress) throws Exception {
        File out = master(c); mkdir(out.getParentFile());
        File temp = new File(out.getParentFile(), ".master-import");
        try {
            copy(c, uri, temp, progress, "Importing master data");
            if (temp.length() == 0) throw new IOException("The selected file is empty");
            move(temp, out);
        } finally { temp.delete(); }
    }
    static final class Doc {
        String id, name, mime; long size;
        Doc(String id, String name, String mime, long size) { this.id=id; this.name=name; this.mime=mime; this.size=size; }
        boolean directory() { return DocumentsContract.Document.MIME_TYPE_DIR.equals(mime); }
    }
    /** One file or folder to copy, found by the scan before the copy starts. */
    static final class Entry {
        final Uri uri; final File out; final long size;
        Entry(Uri uri, File out, long size) { this.uri=uri; this.out=out; this.size=size; }
    }
    /**
     * Time left for a copy. Small files cost far more per byte than large ones,
     * so it learns from recent progress how long one file and one byte take on
     * this device, then applies that to what remains. Recent samples count most.
     */
    static final class Estimate {
        long totalFiles, totalBytes;  // may grow while an archive is still being listed
        final long started;
        long lastTime, lastFiles, lastBytes;
        double ff, fb, bb, ft, bt, shown;
        double st, sf, sb;  // recent time, files and bytes, including pauses with no progress
        Estimate(long totalFiles, long totalBytes) {
            this.totalFiles = totalFiles; this.totalBytes = totalBytes;
            started = lastTime = SystemClock.elapsedRealtime();
        }
        /** Records progress; returns seconds left, or -1 while still measuring. */
        double update(long files, long bytes) {
            long now = SystemClock.elapsedRealtime();
            double dt = (now - lastTime) / 1000.0, df = files - lastFiles, db = bytes - lastBytes;
            if (dt > 0) {
                ff = ff*.995 + df*df; fb = fb*.995 + df*db; bb = bb*.995 + db*db; ft = ft*.995 + df*dt; bt = bt*.995 + db*dt;
                st = st*.995 + dt; sf = sf*.995 + df; sb = sb*.995 + db;
            }
            lastTime = now; lastFiles = files; lastBytes = bytes;
            if (now - started < 10000 || bb <= 0) return -1;
            double perFile, perByte, det = ff*bb - fb*fb;
            if (ff > 0 && det > 1e-6 * ff * bb) { perFile = (ft*bb - bt*fb) / det; perByte = (bt*ff - ft*fb) / det; }
            else { perFile = 0; perByte = bt / bb; }
            if (perFile < 0 || perByte < 0) {  // Too little variety yet: count each file as 1 MB.
                double done = bytes + files * 1e6, total = totalBytes + totalFiles * 1e6;
                return done > 0 ? (now - started) / 1000.0 * (total - done) / done : -1;
            }
            // The fit gives the relative cost of a file and a byte. Scale it by the
            // real recent time, so pauses between bursts (as when several archive
            // blocks decompress at once) count too.
            double work = perFile * sf + perByte * sb, scale = work > 0 ? st / work : 1;
            return Math.max(0, scale * (perFile * (totalFiles - files) + perByte * (totalBytes - bytes)));
        }
        /** Share done for the progress bar: time-based once measured, and never moving back. */
        double fraction(long files, long bytes, double secondsLeft) {
            double value;
            if (secondsLeft < 0) value = (bytes + files * 1e6) / Math.max(1.0, totalBytes + totalFiles * 1e6);
            else { double elapsed = (SystemClock.elapsedRealtime() - started) / 1000.0; value = elapsed / Math.max(1e-6, elapsed + secondsLeft); }
            shown = Math.max(shown, Math.min(1, value));
            return shown;
        }
    }
    // "8.2 GB of 20.9 GB · 39% · about 4 min left"
    static String progressText(Context c, String verb, long bytes, long totalBytes, double fraction, double secondsLeft) {
        String line = verb + " " + Formatter.formatFileSize(c, bytes) + " of " + Formatter.formatFileSize(c, totalBytes) + " · " + (int) (fraction * 100) + "%";
        if (secondsLeft < 0) return line + " · estimating time left…";
        long seconds = Math.round(secondsLeft);
        String left = seconds < 60 ? "under a minute left"
            : seconds < 3600 ? "about " + (seconds + 30) / 60 + " min left"
            : "about " + seconds / 3600 + " h " + (seconds % 3600 + 30) / 60 + " min left";
        return line + " · " + left;
    }
    static List<Doc> children(Context c, Uri tree, String id) throws IOException {
        List<Doc> docs = new ArrayList<>();
        Uri uri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, id);
        try (Cursor cur = c.getContentResolver().query(uri, new String[]{"document_id", "_display_name", "mime_type", "_size"}, null, null, null)) {
            if (cur == null) throw new IOException("Cannot read the selected folder");
            while (cur.moveToNext()) docs.add(new Doc(cur.getString(0),cur.getString(1),cur.getString(2),cur.isNull(3)?0:cur.getLong(3)));
        }
        return docs;
    }
    static void importAssets(Context c, Uri tree, Progress progress) throws Exception {
        File base = root(c); mkdir(base);
        recover(c);
        File stage = new File(base, "assets.importing");
        delete(stage); mkdir(stage);
        try {
            // Only revision 0 is used. The raw dump's other revisions are 28 GB
            // of old catalogs, so they are skipped rather than copied.
            String revision = findRevisionZero(c, tree, DocumentsContract.getTreeDocumentId(tree));
            if (revision == null) throw new IOException("Choose the extracted game files: the folder that contains revisions/0");
            File revisionDir = new File(stage, "revisions/0");
            mkdir(revisionDir);
            // List everything first, so the copy can show how much is left.
            progress.fraction(-1);
            List<Entry> entries = new ArrayList<>();
            long total = scan(c,tree,revision,revisionDir,entries,progress,0,0);
            copyAll(c,entries,total,progress);
            install(c, stage, progress);
        } finally { delete(stage); }
    }
    /**
     * Imports revision 0 straight from the resource dump's .7z or a .zip of it.
     * The shared Go code decompresses only the blocks holding revision 0; this
     * polls its progress for the bar and passes on a cancel.
     */
    static void importArchive(Context c, Uri uri, Progress progress) throws Exception {
        File base = root(c); mkdir(base);
        recover(c);
        File stage = new File(base, "assets.importing");
        delete(stage); mkdir(stage);
        try (android.os.ParcelFileDescriptor descriptor = c.getContentResolver().openFileDescriptor(uri, "r")) {
            if (descriptor == null) throw new IOException("Cannot open the selected archive");
            // Native code reads the picked document through this descriptor.
            // Reopening it as /proc/self/fd/N is refused on Android 17.
            int fd = descriptor.getFd();
            String[] result = new String[1];
            Thread worker = new Thread(() -> result[0] = NativeBridge.importArchive(fd, stage.getAbsolutePath()), "lunar-archive");
            worker.start();
            Estimate estimate = null;
            progress.fraction(-1);
            progress.update("Opening the archive…");
            while (worker.isAlive()) {
                worker.join(500);
                if (progress.cancelled()) NativeBridge.cancelImport();
                org.json.JSONObject state = new org.json.JSONObject(NativeBridge.importProgress());
                long done = state.optLong("done"), total = state.optLong("total"), files = state.optLong("files");
                if (total <= 0) continue;
                if (estimate == null) estimate = new Estimate(state.optLong("totalFiles"), total);
                estimate.totalFiles = state.optLong("totalFiles"); estimate.totalBytes = total;
                double left = estimate.update(files, done), fraction = estimate.fraction(files, done, left);
                progress.fraction((int) (fraction * 1000));
                progress.update(progressText(c, "Unpacking", done, total, fraction, left));
            }
            if (result[0] == null || !result[0].isEmpty()) throw new IOException(result[0] == null ? "Cannot read the archive" : result[0]);
            progress.fraction(-1);
            progress.update("Finishing import…");
            install(c, stage, progress);
        } finally { delete(stage); }
    }
    /** Checks a staged assets folder and swaps it in, keeping the current master data and files until it succeeds. */
    static void install(Context c, File stage, Progress progress) throws Exception {
        File old = new File(root(c), "assets.previous");
        File index = new File(stage,"revisions/0/android/list.bin");
        if (index.length()==0 && new File(stage,"revisions/0/list.bin").length()==0)
            throw new IOException("Choose the extracted game files: revisions/0 has no list.bin");
        List<File> infos = new ArrayList<>();
        collect(new File(stage, "revisions/0"), "info.json", infos);
        for (File info : infos) checkSelfContained(info);
        File nextMaster = new File(stage,"release/"+MASTER);
        if (!nextMaster.exists() && master(c).isFile()) {
            mkdir(nextMaster.getParentFile());
            Files.copy(master(c).toPath(), nextMaster.toPath());
        }
        if (progress.cancelled()) throw new IOException("Import cancelled");
        delete(old);
        if (assets(c).exists()) move(assets(c),old);
        try { move(stage,assets(c)); } catch(Exception e) { if(old.exists()) move(old,assets(c)); throw e; }
        delete(old);
    }
    private static void collect(File folder, String name, List<File> found) {
        File[] children = folder.listFiles();
        if (children == null) return;
        for (File child : children) {
            if (child.isDirectory()) collect(child, name, found);
            else if (child.getName().equals(name)) found.add(child);
        }
    }
    /**
     * Finds revisions/0 in the chosen folder: the dump itself, a folder holding
     * "assets", or the "revisions" folder. Returns its document ID, or null.
     */
    static String findRevisionZero(Context c, Uri tree, String id) throws IOException {
        String[][] paths = {{"revisions","0"},{"assets","revisions","0"},{"0"}};
        for (String[] path : paths) {
            String current = id;
            for (String name : path) {
                String next = null;
                for (Doc d : children(c,tree,current)) if (d.directory() && d.name.equals(name)) { next = d.id; break; }
                current = next;
                if (current == null) break;
            }
            if (current != null) return current;
        }
        return null;
    }
    /** Refuses a dump whose revision 0 points at files kept in other revisions. */
    static void checkSelfContained(File info) throws IOException {
        byte[] key = "\"to-revision\"".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        try (InputStream in = new BufferedInputStream(new FileInputStream(info), 1 << 16)) {
            int matched = 0, b;
            while ((b = in.read()) != -1) {
                if (b != key[matched]) { matched = b == key[0] ? 1 : 0; continue; }
                if (++matched < key.length) continue;
                matched = 0;
                do { b = in.read(); } while (b == ' ' || b == ':' || b == '"');
                int after = in.read();
                if (b != '0' || (after >= '0' && after <= '9'))
                    throw new IOException("These game files use other revisions. Prepare them on a computer with scripts/prepare_assets.py");
            }
        }
    }
    static void recover(Context c) throws IOException {
        File old = new File(root(c),"assets.previous");
        if (!assets(c).exists() && old.exists()) move(old,assets(c));
    }
    /** Lists the folder into entries (null uri for folders) and returns the total size in bytes. */
    static long scan(Context c, Uri tree, String id, File dest, List<Entry> entries, Progress progress, int depth, long total) throws Exception {
        if (depth > 32) throw new IOException("Folder nesting is too deep");
        for (Doc d : children(c,tree,id)) {
            if (progress.cancelled()) throw new IOException("Import cancelled");
            if (d.name==null || d.name.equals(".") || d.name.equals("..") || d.name.contains("/") || d.name.contains("\\")) throw new IOException("Invalid file name in source");
            // This companion serves the Android client only.
            if (d.directory() && d.name.equals("ios") && dest.getParentFile()!=null && dest.getParentFile().getName().equals("revisions")) continue;
            File out = new File(dest,d.name);
            if (d.directory()) { entries.add(new Entry(null,out,0)); total = scan(c,tree,d.id,out,entries,progress,depth+1,total); }
            else {
                entries.add(new Entry(DocumentsContract.buildDocumentUriUsingTree(tree,d.id),out,d.size)); total += d.size;
                if (entries.size() % 500 == 0) progress.update("Reading the folder… " + entries.size() + " files · " + Formatter.formatFileSize(c,total));
            }
        }
        return total;
    }
    static void copyAll(Context c, List<Entry> entries, long total, Progress progress) throws Exception {
        long files = 0;
        for (Entry e : entries) if (e.uri != null) files++;
        Estimate estimate = new Estimate(files, total);
        long reported = 0, done = 0, copied = 0;
        for (Entry e : entries) {
            if (progress.cancelled()) throw new IOException("Import cancelled");
            if (e.uri == null) { mkdir(e.out); continue; }
            try (InputStream in = c.getContentResolver().openInputStream(e.uri); FileOutputStream stream = new FileOutputStream(e.out)) {
                if (in==null) throw new IOException("Cannot open " + e.out.getName());
                byte[] buffer = new byte[262144]; int n;
                while ((n=in.read(buffer))!=-1) {
                    if (progress.cancelled()) throw new IOException("Import cancelled");
                    stream.write(buffer,0,n); done+=n;
                }
                stream.getFD().sync();
            }
            copied++;
            long now = SystemClock.elapsedRealtime();
            if (now - reported > 500) {
                reported = now;
                double left = estimate.update(copied, done), fraction = estimate.fraction(copied, done, left);
                progress.fraction((int) (fraction * 1000));
                progress.update(progressText(c, "Copying", done, total, fraction, left));
            }
        }
        progress.fraction(-1);
        progress.update("Finishing import…");
    }
    static void copy(Context c, Uri uri, File out, Progress progress, String label) throws Exception {
        progress.update(label);
        try (InputStream in = c.getContentResolver().openInputStream(uri); FileOutputStream stream = new FileOutputStream(out)) {
            if (in==null) throw new IOException("Cannot open source file");
            byte[] buffer = new byte[262144]; int n; long total=0;
            while ((n=in.read(buffer))!=-1) {
                if (progress.cancelled()) throw new IOException("Import cancelled");
                stream.write(buffer,0,n); total+=n;
                if (total % (8L*1024*1024)<buffer.length) progress.update(label + " · " + (total/1024/1024) + " MB");
            }
            stream.getFD().sync();
        }
    }
    /** Replaces the saves with a chosen backup; the Go server checks and swaps it. */
    static void importSave(Context c, Uri source) throws Exception {
        File temp = new File(c.getCacheDir(), "save-import.tmp");
        try {
            try (InputStream in = c.getContentResolver().openInputStream(source); FileOutputStream out = new FileOutputStream(temp)) {
                if (in == null) throw new IOException("Cannot open the selected file");
                byte[] buffer = new byte[262144]; int n;
                while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
            }
            String error = NativeBridge.importSaves(data(c).getAbsolutePath(), temp.getAbsolutePath());
            if (error == null || !error.isEmpty()) throw new IOException(error == null ? "Cannot import the save" : error);
        } finally { temp.delete(); }
    }
    static void backup(Context c, Uri target) throws Exception {
        String error=NativeBridge.prepareBackup(data(c).getAbsolutePath());
        if(error==null||!error.isEmpty())throw new IOException(error==null?"Cannot prepare save backup":error);
        try (OutputStream raw=c.getContentResolver().openOutputStream(target,"wt")) {
            if(raw==null) throw new IOException("Cannot open backup destination");
            try (ZipOutputStream zip=new ZipOutputStream(raw)) {
                for(String name:new String[]{"game.db","auth.db","auth.key"}) {
                    File f=new File(data(c),name);
                    if(!f.isFile()) continue;
                    zip.putNextEntry(new ZipEntry(name));
                    try(InputStream in=new FileInputStream(f)){byte[] bytes=new byte[65536];int n;while((n=in.read(bytes))!=-1)zip.write(bytes,0,n);}
                    zip.closeEntry();
                }
                zip.putNextEntry(new ZipEntry("README.txt"));
                zip.write("Lunar Tear local saves. Keep game.db, auth.db and auth.key together. Contains account credentials; keep this backup private.\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                zip.closeEntry();
            }
        }
    }
    static void delete(File file) {
        // A folder used in place is linked, never owned: remove the link only.
        if (Files.isSymbolicLink(file.toPath())) { file.delete(); return; }
        File[] children=file.listFiles(); if(children!=null) for(File c:children) delete(c);
        file.delete();
    }
    /** The player's folder when the game files are used in place, or null when they were copied in. */
    static File linkedFolder(Context c) {
        java.nio.file.Path link = new File(assets(c), "revisions/0").toPath();
        try { return Files.isSymbolicLink(link) ? Files.readSymbolicLink(link).toFile() : null; }
        catch (IOException e) { return null; }
    }
    /** True when this app may read shared storage by path (All files access, Android 11+). */
    static boolean canUseInPlace() {
        return Build.VERSION.SDK_INT >= 30 && android.os.Environment.isExternalStorageManager();
    }
    /**
     * Uses the chosen folder's revisions/0 where it is, without copying: the
     * server reads it through a link. Needs All files access. The folder must
     * stay in place; the launcher asks for it again if it disappears.
     */
    static void linkAssets(Context c, Uri tree, Progress progress) throws Exception {
        if (!canUseInPlace()) throw new IOException("Allow All files access for NieR in Settings to use a folder in place, or copy it instead.");
        if (!"com.android.externalstorage.documents".equals(tree.getAuthority()))
            throw new IOException("Use in place works with folders on this phone's storage or SD card. Copy the folder instead.");
        String revision = findRevisionZero(c, tree, DocumentsContract.getTreeDocumentId(tree));
        if (revision == null) throw new IOException("Choose the extracted game files: the folder that contains revisions/0");
        // Document IDs look like "primary:Download/dump/revisions/0" or "1234-ABCD:dump/revisions/0".
        int colon = revision.indexOf(':');
        String volume = revision.substring(0, colon), relative = revision.substring(colon + 1);
        File base = "primary".equalsIgnoreCase(volume) ? android.os.Environment.getExternalStorageDirectory() : new File("/storage", volume);
        File folder = new File(base, relative);
        if (!folder.isDirectory() || folder.list() == null) throw new IOException("Cannot read " + folder + ". Allow All files access for NieR in Settings.");
        File root = root(c); mkdir(root);
        recover(c);
        File stage = new File(root, "assets.importing");
        delete(stage); mkdir(new File(stage, "revisions"));
        try {
            progress.fraction(-1);
            progress.update("Checking the folder…");
            Files.createSymbolicLink(new File(stage, "revisions/0").toPath(), folder.toPath());
            install(c, stage, progress);
        } finally { delete(stage); }
    }
}

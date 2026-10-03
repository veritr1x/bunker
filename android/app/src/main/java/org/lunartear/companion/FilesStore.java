package org.lunartear.companion;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
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
        final long totalFiles, totalBytes, started;
        long lastTime, lastFiles, lastBytes;
        double ff, fb, bb, ft, bt, shown;
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
            return Math.max(0, perFile * (totalFiles - files) + perByte * (totalBytes - bytes));
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
        File stage = new File(base, "assets.importing"), old = new File(base, "assets.previous");
        delete(stage); mkdir(stage);
        try {
            String id = DocumentsContract.getTreeDocumentId(tree);
            // Accept either the assets directory itself or its immediate parent.
            List<Doc> docs = children(c,tree,id);
            for (Doc d : docs) if (d.directory() && d.name.equals("assets")) { id=d.id; break; }
            // List everything first, so the copy can show how much is left.
            progress.fraction(-1);
            List<Entry> entries = new ArrayList<>();
            long total = scan(c,tree,id,stage,entries,progress,0,0);
            copyAll(c,entries,total,progress);
            File index = new File(stage,"revisions/0/android/list.bin");
            if (index.length()==0 && new File(stage,"revisions/0/list.bin").length()==0)
                throw new IOException("Select the extracted assets folder containing revisions/0/android/list.bin");
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
        } finally { delete(stage); }
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
        File[] children=file.listFiles(); if(children!=null) for(File c:children) delete(c);
        file.delete();
    }
}
